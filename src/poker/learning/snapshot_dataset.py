"""Reproducible public-state imitation samples, split by whole simulation seeds."""

import hashlib
import json
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from pathlib import Path

from poker.api import play_hand
from poker.learning.snapshot_actions import target
from poker.learning.snapshot_contract import MIXED_RULESET, RULESET, from_dict, from_public_state
from poker.learning.snapshot_encoding import LAYOUT_SHA256, encode, layout_for, layout_hash
from poker.strategy.ranges import PositionRangeModel

SAMPLE_VERSION = "snapshot-sample/1"
DATASET_VERSION = "snapshot-dataset/1"
DATASET_VERSION_V2 = "snapshot-dataset/2"
SCENARIOS = ("standard-v1", "mixed-bomb-v1")
SPLITS = ("train", "validation", "test")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*.py"))}


def bomb_candidate(seed: int) -> bool:
    return random.Random(seed ^ 0xB04B).randrange(2) == 0


class UnselectedFocusHand(Exception):
    """Abort an extra train candidate before the expensive teacher estimate."""


class CachedTeacherRanges(PositionRangeModel):
    """Same combo weights and RNG order; cache only inside one immutable public view.

    Monte Carlo removes different unavailable cards on each trial. The weight
    of a remaining combo does not change, so only normalization is repeated.
    Each teacher owns this cache; no player profiles or cross-state reuse.
    """

    def __init__(self):
        super().__init__()
        self._state = None
        self._by_player = {}
        self._active = {}

    def combo_distribution(self, available, player, state):
        if state is not self._state:
            self._state = state
            self._by_player = {}
        self._active = self._by_player.setdefault(player, {})
        return super().combo_distribution(available, player, state)

    def _combo_weight(self, combo, state, range_state, exponent, profile):
        if combo not in self._active:
            self._active[combo] = super()._combo_weight(
                combo, state, range_state, exponent, profile
            )
        return self._active[combo]


def focus_hero_cards(hole_cards):
    from poker.agents.expert import parse_card

    cards = [parse_card(card) for card in hole_cards]
    ranks = sorted(card.rank.value for card in cards)
    return (
        (ranks[0] == ranks[1] and ranks[0] >= 10)
        or ranks == [13, 14]
        or (ranks == [12, 14] and cards[0].suit == cards[1].suit)
    )


def generate_hand(job, *, decision_observer=None):
    """Pure per-seed job; workers return records, only the parent writes files."""
    from poker.agents import CallingStationAgent, ExpertAgent, NitAgent, RandomAgent, TAGAgent

    hand_seed, equity_samples, focused, *scenario_values = job
    scenario = scenario_values[0] if scenario_values else "standard-v1"
    if scenario not in SCENARIOS or len(scenario_values) > 1:
        raise ValueError("Unsupported generation scenario")
    variant_rng = random.Random(hand_seed ^ 0xB04B)
    bomb = scenario == "mixed-bomb-v1" and bomb_candidate(hand_seed)
    feature_set = "variants-v3" if scenario == "mixed-bomb-v1" else "raw-v1"

    class FocusedExpert:
        def __init__(self, **kwargs):
            self.teacher = ExpertAgent(**kwargs)

        def choose_action(self, state, legal):
            # Only the acting hero's public API view is inspected; no opponent cards.
            if not focus_hero_cards(state.hole_cards):
                raise UnselectedFocusHand
            return self.teacher.choose_action(state, legal)

    samples, rejections = [], Counter()
    rng = random.Random(hand_seed ^ 0x9123)
    count, bb = rng.randint(2, 3 if focused else 7), rng.choice((2, 4, 10))
    names = [f"seat_{i}" for i in range(count)]
    hero = names[rng.randrange(count)]
    agents = {}
    for i, name in enumerate(names):
        agent_seed = hand_seed * 19 + i
        if name == hero:
            teacher = FocusedExpert if focused else ExpertAgent
            kwargs = {"range_model": CachedTeacherRanges()} if scenario == "mixed-bomb-v1" else {}
            agents[name] = teacher(seed=agent_seed, equity_samples=equity_samples, **kwargs)
        else:
            style = rng.randrange(4)
            agents[name] = (
                CallingStationAgent()
                if style == 0
                else NitAgent()
                if style == 1
                else TAGAgent(seed=agent_seed)
                if style == 2
                else RandomAgent(seed=agent_seed)
            )
    stacks = {name: rng.choice((20, 50, 100, 200)) * bb for name in names}
    sequence = 0

    def observer(
        state,
        legal,
        decision,
        *,
        hero=hero,
        hand_seed=hand_seed,
        bb=bb,
        rng=rng,
    ):
        nonlocal sequence
        if state.acting_player != hero:
            return
        sequence += 1
        snapshot = from_public_state(
            state,
            legal,
            hand_id=f"sim:{hand_seed}",
            observation_id=str(sequence),
            big_blind=bb,
            ruleset=MIXED_RULESET if scenario == "mixed-bomb-v1" else RULESET,
        )
        reasons = snapshot.blocking_reasons()
        if reasons:
            rejections.update(reasons)
            if set(reasons) - {"existing_all_in_unsupported"}:
                raise ValueError(f"Unexpected engine refusal: {reasons}")
            return
        # Missing optional evidence is explicit. Critical state is never corrupted.
        snapshot.history, snapshot.history_complete = [], False
        for player in snapshot.players:
            player.name, player.position = None, None
            if rng.random() < 0.5:
                player.hand_contribution = None
            if player.folded and rng.random() < 0.5:
                player.stack = None
        action = decision.action.value
        amount = decision.amount if action in ("bet", "raise") else None
        target(snapshot, action, amount)
        encode(snapshot, feature_set=feature_set)
        sample = {
            "schema_version": SAMPLE_VERSION,
            "deal_seed": hand_seed,
            "observation": snapshot.to_dict(),
            "target": {"action": action, "amount_to": amount},
            "teacher": "ExpertAgent_heuristic_not_optimal",
        }
        samples.append(sample)
        if decision_observer is not None:
            # The audit sees only the acting hero's public view. Protect saved
            # records from callback mutation; the simulation/RNG is not exposed.
            from copy import deepcopy

            decision_observer(state, legal, decision, deepcopy(sample))

    try:
        play_hand(
            agents,
            hand_seed,
            small_blind=bb // 2,
            big_blind=bb,
            starting_stacks=stacks,
            dealer_name=rng.choice(names),
            decision_observer=observer,
            bomb_pot_ante=variant_rng.choice((3, 4, 5)) * bb if bomb else None,
        )
    except UnselectedFocusHand:
        if samples:
            raise AssertionError("Focus selection must precede all observations") from None
        return [], {"focused_candidate_unselected": 1}
    return samples, dict(rejections)


def prepare(
    output,
    *,
    hands=3000,
    seed=71000,
    equity_samples=128,
    extra_train_hands=0,
    workers=1,
    progress=None,
    scenario="standard-v1",
):
    values = (hands, seed, equity_samples, extra_train_hands, workers)
    if any(type(v) is not int for v in values) or hands < 30 or equity_samples < 1:
        raise ValueError("Need at least 30 hands, positive equity_samples and integer parameters")
    if extra_train_hands < 0 or not 1 <= workers <= 32:
        raise ValueError("Nonnegative extra hands and 1..32 workers required")
    if scenario not in SCENARIOS or (scenario == "mixed-bomb-v1" and extra_train_hands):
        raise ValueError("Supported scenario required; mixed hands do not use focused enrichment")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    sources = source_hashes()
    indices = list(range(hands))
    random.Random(seed ^ 0x57A17).shuffle(indices)
    held_out = max(1, hands // 10)
    assignments = {n: "train" for n in range(hands + extra_train_hands)}
    assignments.update(dict.fromkeys(indices[:held_out], "test"))
    assignments.update(dict.fromkeys(indices[held_out : 2 * held_out], "validation"))
    if scenario == "mixed-bomb-v1":
        assignments = dict.fromkeys(range(hands), "train")
        for bomb in (False, True):
            cohort = [i for i in indices if bomb_candidate(seed + i) == bomb]
            if len(cohort) < 3:
                raise ValueError("Need at least three candidate hands of each variant")
            held_out = max(1, len(cohort) // 10)
            assignments.update(dict.fromkeys(cohort[:held_out], "test"))
            assignments.update(dict.fromkeys(cohort[held_out : 2 * held_out], "validation"))
    jobs: list[tuple[int, int, bool] | tuple[int, int, bool, str]] = [
        (seed + index, equity_samples, index >= hands) for index in assignments
    ]
    if scenario != "standard-v1":
        jobs = [(seed + index, equity_samples, index >= hands, scenario) for index in assignments]
    rows, rejections, labels, streets, cohorts = (Counter() for _ in range(5))
    variants: Counter[str] = Counter()
    seen_hands = {name: set() for name in SPLITS}
    with ExitStack() as opened:
        files = {
            name: opened.enter_context((output / f"{name}.jsonl").open("w", encoding="utf-8"))
            for name in SPLITS
        }
        if workers == 1:
            results = map(generate_hand, jobs)
        else:
            executor = opened.enter_context(ProcessPoolExecutor(max_workers=workers))
            results = executor.map(generate_hand, jobs, chunksize=4)
        # map preserves input order regardless of completion order and worker count.
        for index, (samples, rejected) in enumerate(results):
            split = assignments[index]
            rejections.update(rejected)
            for sample in samples:
                observation = sample["observation"]
                files[split].write(json.dumps(sample, ensure_ascii=False) + "\n")
                rows[split] += 1
                seen_hands[split].add(sample["deal_seed"])
                action = sample["target"]["action"]
                labels[split + ":" + action] += 1
                streets[split + ":" + observation["street"]] += 1
                variants[split + ":" + observation.get("hand_variant", "standard")] += 1
                cohorts[("focused_train" if index >= hands else "natural") + ":" + action] += 1
            if progress and (index + 1) % 100 == 0:
                progress(index + 1, dict(rows))
    if source_hashes() != sources:
        raise ValueError("Source files changed during generation; dataset left incomplete")
    manifest = {
        "schema_version": DATASET_VERSION,
        "layout_sha256": LAYOUT_SHA256,
        "generator_version": "snapshot-generator/2",
        "config": {
            "hands": hands,
            "seed": seed,
            "equity_samples": equity_samples,
            "extra_train_hands": extra_train_hands,
            "workers": workers,
        },
        "teacher": "ExpertAgent_heuristic_not_optimal",
        "split_method": "seeded_whole_hand_80_10_10_before_generation",
        "enrichment": "extra_seeds_2_to_3_players_TTplus_AK_AQs_train_only",
        "assigned_seeds": {
            name: [seed + index for index, split in assignments.items() if split == name]
            for name in SPLITS
        },
        "samples": dict(rows),
        "hands_with_samples": {k: len(v) for k, v in seen_hands.items()},
        "labels": dict(labels),
        "streets": dict(streets),
        "cohort_labels": dict(cohorts),
        "rejections": dict(rejections),
        "split_sha256": {name: digest(output / f"{name}.jsonl") for name in SPLITS},
        "source_sha256": sources,
        "training_run": False,
        "player_db_written": False,
    }
    if scenario == "mixed-bomb-v1":
        manifest.update(
            schema_version=DATASET_VERSION_V2,
            layout_sha256=layout_hash("variants-v3"),
            generator_version="snapshot-generator/3",
            split_method="seeded_whole_hand_80_10_10_stratified_by_variant_before_generation",
            enrichment="none; seeded_half_bomb_candidates; not_live_frequency",
            variants=dict(variants),
        )
        manifest["config"]["scenario"] = scenario
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def load_split(path, *, feature_set="raw-v1"):
    layout_for(feature_set)
    rows, identities, seeds = [], set(), set()
    with Path(path).open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            raw = json.loads(line)
            if set(raw) != {"schema_version", "deal_seed", "observation", "target", "teacher"}:
                raise ValueError(f"Unexpected sample fields at line {line_number}")
            if raw["schema_version"] != SAMPLE_VERSION or type(raw["deal_seed"]) is not int:
                raise ValueError("Unsupported sample schema or seed")
            observation = from_dict(raw["observation"])
            if observation.source != "engine" or observation.hand_id != f"sim:{raw['deal_seed']}":
                raise ValueError("Expected identified public simulation data")
            identity = (observation.hand_id, observation.observation_id)
            if identity in identities:
                raise ValueError("Duplicate observation")
            identities.add(identity)
            seeds.add(raw["deal_seed"])
            if not isinstance(raw["target"], dict) or set(raw["target"]) != {"action", "amount_to"}:
                raise ValueError("Invalid target fields")
            index, fraction, sizing = target(
                observation, raw["target"]["action"], raw["target"]["amount_to"]
            )
            rows.append(
                {
                    "observation": observation,
                    "encoded": encode(observation, feature_set=feature_set),
                    "action_index": index,
                    "sizing_fraction": fraction,
                    "sizing_mask": sizing,
                    "amount_to": raw["target"]["amount_to"],
                }
            )
    if not rows:
        raise ValueError(f"Empty split: {path}")
    return rows, seeds


def load_dataset(directory, *, feature_set="raw-v1"):
    layout_for(feature_set)
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    variant = feature_set == "variants-v3"
    if manifest.get("schema_version") != (
        DATASET_VERSION_V2 if variant else DATASET_VERSION
    ) or manifest.get("layout_sha256") != (layout_hash(feature_set) if variant else LAYOUT_SHA256):
        raise ValueError("Incompatible dataset")
    data, seed_sets = {}, {}
    for name in SPLITS:
        path = directory / f"{name}.jsonl"
        if digest(path) != manifest["split_sha256"][name]:
            raise ValueError("Dataset hash mismatch: " + name)
        data[name], seed_sets[name] = load_split(path, feature_set=feature_set)
        if len(data[name]) != manifest["samples"].get(name):
            raise ValueError("Dataset sample count mismatch: " + name)
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if seed_sets[left] & seed_sets[right]:
            raise ValueError("Simulation seed leakage across splits")
    if "assigned_seeds" in manifest:
        assigned = manifest["assigned_seeds"]
        if not isinstance(assigned, dict) or set(assigned) != set(SPLITS):
            raise ValueError("Invalid seed assignments")
        seen = set()
        for name in SPLITS:
            values = assigned[name]
            if not isinstance(values, list) or any(type(v) is not int for v in values):
                raise ValueError("Invalid assigned seeds")
            declared = set(values)
            if len(declared) != len(values) or seen & declared:
                raise ValueError("Duplicate or overlapping seed assignments")
            if not seed_sets[name] <= declared:
                raise ValueError("Observed seed outside assigned split")
            seen.update(declared)
    return data, manifest
