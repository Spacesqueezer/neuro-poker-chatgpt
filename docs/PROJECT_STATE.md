# Project State

## Current milestone

Phase 4 baseline Arena work is complete.

Current focus:
- player statistics foundation;
- persistent opponent memory architecture;
- preparation for dataset generation.

A first statistics model, collector, extraction pipeline and storage boundary exist. Agent-specific opponent memory architecture is introduced. SQLAlchemy 2.x provides the real persistence backend, and Alembic owns schema evolution with an initial revision for players, aggregate statistics and agent-specific memory. Repository round trips and migration upgrade/downgrade are covered by SQLite tests. An opt-in PostgreSQL integration test exercises the same Alembic migration and repository stack when `POKER_TEST_DATABASE_URL` is configured; the normal suite remains self-contained and skips that test otherwise. Real engine `HandHistory` events feed the statistics mapper/adapter directly, while the previous pre-aggregated dictionary input remains supported for compatibility. Tracker statistics are now opportunity-aware for 3-bet and fold-to-3-bet, continuation-bet opportunities/actions are derived from flop action order, and postflop aggressive-action/call counts provide aggression-factor inputs. VPIP, PFR and showdown outcomes remain derived from recorded history. Tracker numerators and denominators are persisted alongside the existing derived rates through SQLAlchemy and Alembic revision `0002_tracker_counters`, so stored statistics retain enough information for correct future aggregation. `StatisticsService.persist_collector()` now converts accumulated `StatisticsCollector` snapshots into persistence records through repository contracts, using an explicit player-name to stable-player-id mapping and preserving all raw counters plus derived rates. The collector remains storage-agnostic. Arena now sends every successfully accepted `HandHistory` through a fresh per-run `HandStatisticsAdapter`; `ArenaRunner` exposes the resulting collector and, when configured with a `StatisticsService` plus stable player IDs, automatically persists the run at completion. Persistence merges raw counters with prior stored history before recalculating derived rates, so repeated Arena runs build long-lived player profiles instead of overwriting them. Persistent player identity is now resolved by `StatisticsService` through repository-level name lookup and creation. Player names are unique in persistence, Arena can persist statistics without manually supplied IDs, and repeated runs reuse the same stable player records. Explicit ID mappings remain supported for controlled callers. Canonical table positions are now recorded directly in `HandHistory` for 2-9 handed tables. `StatisticsCollector` maintains VPIP/PFR/3-bet splits per position, and `StatisticsService` persists/merges those splits in normalized `player_position_statistics` storage through Alembic revision `0004_position_statistics`. Arena therefore builds both global and positional long-lived profiles automatically. Flop fold-to-cbet is now opportunity-aware: each opponent's first direct response to a genuine flop c-bet is tracked, and a raise closes the direct fold-to-cbet window for later players. Aggressive actions and calls are also split into flop/turn/river counters, with street-specific aggression factors derived from those counters. Alembic revision `0005_street_tracker_metrics` persists all new raw counters, and repeated Arena runs merge them into long-lived profiles. The tracker foundation is now exposed through a storage-agnostic opponent-profile boundary. `OpponentProfileProvider` resolves a stable player by name and combines persisted global tracker statistics, positional VPIP/PFR/3-bet splits, and optional agent-specific memory into an immutable `OpponentProfile`. `OpponentProfileEncoder` converts that snapshot into a fixed, named 22-feature tuple with a selected-position slice and agent-memory confidence fields. Learning/decision code therefore does not need repository or SQLAlchemy knowledge. `poker.learning.LearningObservationEncoder` now combines `HandStateView` with fixed card/street/table features and up to eight zero-padded opponent slots for 2-9 handed play. Opponent-profile information is explicitly scoped as `private`, `global` or `combined`; private mode exposes only that agent's memory fields and is the intended default for experiments that model individually observed knowledge. Cards use fixed 52-way one-hot encoding and the complete observation schema has a deterministic size/name ordering. `LearningActionEncoder` now maps `LegalActions` into a stable six-action mask ordered as fold/check/call/bet/raise/all-in plus normalized call/bet/raise sizing bounds. Chosen `ActionDecision` values are validated against the public legality boundary before becoming supervised targets. `LearningSampleBuilder` combines observation, legal-action mask/sizing and chosen action into versioned `LearningSample` records. `play_hand()` now exposes an optional decision observer invoked after public legality validation and before state mutation; Arena forwards this observer without importing learning code. `LearningDatasetCapture` uses that hook to build samples from real decisions, `LearningDatasetWriter` appends compact UTF-8 JSONL, and `LearningDatasetAnalyzer` validates sample version, target legality and schema sizes while reporting action/player/shape distributions. Arena only passes the observer keyword to `play_hand()` when a real observer is configured, preserving compatibility with existing tests and alternate callables that implement the historical play-hand signature. Dataset capture is therefore connected end-to-end through the public API without coupling the poker engine to dataset classes. `LearningDatasetGenerator` now provides reproducible large-scale generation from explicit baseline-agent specs, deterministic Arena and RandomAgent seeds, clean output directories, deterministic train/validation splitting, and a JSON manifest containing configuration, Arena failures and per-split dataset analysis. `RandomAgent` now emits legal BET/RAISE amounts inside the public `LegalActions` ranges instead of selecting an aggressive action with amount zero, eliminating a real Arena failure mode. `tools/generate_dataset.py` exposes the pipeline as a CLI. Generation aborts if Arena reports any failed hands instead of silently accepting a partial dataset. The standalone generator intentionally uses `profile_scope='global'` until persistent per-agent memory can be updated online during simulation; private-memory experiments must not silently produce all-zero memory features. No trainable policy is introduced yet. Before supervised training, the project now introduces an explicit teacher layer: `ExpertAgent` estimates showdown equity from public state through deterministic Monte-Carlo rollouts using the same seven-card evaluator as the engine, then combines equity, pot odds and legal sizing bounds into conservative value-oriented decisions. Dataset capture can filter acting players, and `LearningDatasetGenerator` defaults to an expert teacher playing against CallingStation/Nit opponents while recording only expert decisions. This prevents baseline-opponent actions from contaminating supervised labels. The expert is a heuristic rollout policy, not a solved/GTO strategy. `ExpertBenchmarkRunner` now measures teacher quality through reproducible expert-vs-baseline matchups. A benchmark is composed of multiple independent Arena sessions with fresh stacks and deterministic seeds; session ordering alternates so the same player does not always receive the first dealer position. Results aggregate actual completed hands, failed hands, Expert profit, bb/100, showdowns, uncontested wins and completion rate. `tools/benchmark_expert.py` exposes the benchmark as JSON/CLI output. Resetting stacks between benchmark sessions prevents one early bust from terminating the whole quality measurement while keeping ordinary Arena semantics unchanged. The first explicit opponent-range model is now integrated into Expert equity. `PositionRangeModel` assigns weighted two-card combinations from only unknown cards, tightening early-position ranges more strongly and allowing later-position ranges to remain wider. `MonteCarloEquityEstimator` samples each active opponent sequentially from that weighted range without card collisions, then samples the future board from the remaining unknown cards. `UniformRangeModel` remains available as a control/baseline. The public `HandStateView` now exposes an immutable `PublicActionView` sequence containing only actions already recorded before the current decision. Public player positions now use the same canonical 2-9 handed `positions_by_player()` mapping as hand history instead of the previous BTN/SB/BB-only helper. `PositionRangeModel` conditions its range tightness on the observed player's own public line: calls tighten slightly, bets/raises tighten materially, and all-ins tighten most strongly. Range inference now builds an explicit immutable `OpponentRangeState` from the public action line before sampling holdings. Preflop state distinguishes unopened/call/open-raise/3-bet/4-bet+/all-in by counting the public raise sequence, while flop/turn/river calls and aggressive actions are tracked separately. The position prior is then adjusted from this structured state, with later-street aggression treated as stronger evidence than early-street aggression. The range boundary is now combo-aware: `PositionRangeModel.combo_distribution()` returns every currently legal two-card combination with an explicit normalized probability, and Monte-Carlo sampling uses that distribution. Action class and street evidence therefore change inspectable probabilities for individual combinations rather than only an opaque sampling exponent. Combo probabilities now receive evidence-specific reweighting instead of relying only on a common strength exponent. `OpponentRangeState` records maximum public aggression sizing by street, and `PositionRangeModel` applies different multipliers to premium pairs, medium pairs, broadway hands, suited aces, suited connectors and weak offsuit holdings for calls, open-raises, 3-bets, 4-bets+ and all-ins. Larger observed aggression shifts relatively more mass toward premium/value-heavy classes and away from speculative holdings. Board-aware combo evidence is now part of the range boundary. `BoardInteraction` classifies each candidate holding against the public board as pair/two-pair+/trips+, overpair, straight, flush, straight draw and flush draw. Postflop calls and aggression then reweight individual combos by this interaction: made hands gain more probability under pressure, flop/turn draws retain semi-bluff weight, air is discounted, and incomplete draws are no longer treated as live draws on the river. Board cards also continue to remove impossible combinations through the available-card set. Persisted opponent tendencies can now feed the combo range boundary through the existing storage-agnostic `OpponentProfileProvider`. `PositionRangeModel` accepts an optional provider and agent id, resolves the current opponent profile by name, and scales profile influence by observed hand count so tiny samples do not dominate the public action evidence. Global/positional VPIP, PFR and 3-bet tendencies change preflop combo weights; street aggression changes the relative amount of made-hand versus draw/air probability after postflop aggression; optional agent-specific memory is blended only according to its confidence. `ExpertAgent` can receive the provider directly and constructs a profile-aware range model without importing persistence. This remains heuristic rather than a solver posterior: board-texture-specific frequencies, blocker effects beyond card removal, explicit Bayesian updates and action-tree EV are not yet modeled. The solver track has now started as a separate `poker.solver` boundary. A deterministic tabular `CFRTrainer` is implemented against a deliberately tiny `KuhnPokerGame`, with explicit information sets, regret matching, cumulative regrets, reach-weighted average-strategy accumulation and zero-sum terminal utilities. Tests cover normalization, determinism, all information sets and convergence near Kuhn poker's known game value. This is intentionally not wired into `ExpertAgent` or the production Hold'em engine yet: the purpose of this step is to prove the CFR machinery in isolation before introducing Hold'em state abstraction, action abstraction and MCCFR sampling. `PositionRangeModel` remains an opponent/exploit belief layer and must not be confused with equilibrium solving. The solver boundary now exposes a generic two-player extensive-form game interface with weighted initial chance nodes, dynamic legal actions and chance-weighted regret/average-strategy accumulation. `KuhnPokerGame` remains the correctness harness through that interface. A deliberately restricted `RestrictedHeadsUpHoldemGame` now adapts real Hold'em cards and the production seven-card evaluator into a finite heads-up push/fold game over an explicit weighted set of private deals and a fixed five-card board. Information sets contain only the acting player's canonicalized hole cards plus public board/action history, so opponent hole cards stay hidden. This adapter is still intentionally tiny and is not wired into `ExpertAgent` or the production hand loop. External-sampling MCCFR now traverses the generic solver boundary for both players and samples one initial chance node per iteration according to its configured probability, so explicit private-deal sets no longer have to be fully enumerated on every iteration. Opponent actions and initial chance selection are both reproducible from the solver seed. The next solver step is richer Hold'em state/action abstraction beyond the current fixed-board push/fold tree. A Russian user-facing command manual now lives in `docs/USER_GUIDE_RU.md`; `DEV_RULES.md` requires every future patch that adds or changes CLI commands, arguments, interactive commands, user-visible tools, environment variables or standard operational workflows to update that guide in the same patch.

## Current capabilities

### Poker hand engine

- 52-card deck, hole cards and community board.
- Seven-card Texas Hold'em evaluation and comparison.
- Dealer button, SB/BB, heads-up order and street progression.
- Check, call, bet, raise, fold and all-in actions.
- Minimum bet/full-raise sizing, short blinds and cumulative short-all-in reopen semantics.
- Per-player contributions, main/side pots, unmatched refunds, ties and deterministic odd chips.
- Automatic all-in runout, uncontested payout and showdown settlement.

### Table lifecycle

- Persistent `Table` with stable `Seat` objects.
- Explicit `ACTIVE`, `SITTING_OUT` and `BUSTED` seat states.
- `GameState.players` is the participant view for the current/next hand.
- Dealer button skips unavailable seats while preserving physical seat order.

### Public simulation boundary

`poker.api` is the supported boundary for agent/simulation code:

```text
HandStateView
+ LegalActions
+ ActionDecision
        |
        v
play_hand(agents, seed, dealer_name=...) -> HandHistory
```

- `HandStateView` exposes public table/hand state plus only the acting player's hole cards.
- `LegalActions` exposes call amount and legal bet/raise target ranges.
- Agent decisions are checked against `LegalActions` and then still processed by `HandController`.
- `play_hand()` owns the headless hand loop and returns completed `HandHistory`.
- `dealer_name` allows Arena to rotate position fairly across independent hands.
- `tools/stress_poker.py` now consumes this public API instead of `HandController` internals.

### Verification

- Deterministic named manual scenarios.
- Random default hands with reproducible seeds.
- Structured `HandHistory` and JSONL persistence.
- Interactive history viewer.
- Exact seed-based replay verification, including backward compatibility with histories recorded before player-position metadata was introduced.
- Structural verification fallback for scripted histories.
- Randomized stress runner using the public simulation API.

## Architecture snapshot

```text
Table / GameState / HandController
             |
             v
         poker.api
   ┌─────────┼──────────┐
   v         v          v
HandState  Legal     play_hand
  View     Actions       |
                        agents

HandHistory
├── viewer
├── replay verifier
└── stress verification
```

The poker engine does not import or depend on agents. Agent code depends only on `poker.api`.

## Known gaps

- Baseline strategy agents are implemented: RandomAgent, CallingStationAgent, NitAgent.
- Arena v1 execution exists and now has baseline opponents for evaluation.
- Arena reporting is being expanded with aggregated session statistics.
- Arena v1 accounting tracks session stacks, player profit and bb/100 evaluation foundations.
- `ArenaSession` is the explicit owner of multi-hand session state and hand-to-hand stack transitions.
- `ArenaRunner` is reduced to orchestration while session execution lives in `ArenaSession`.
- `play_hand()` accepts either a shared `starting_stack` or per-player `starting_stacks`; Arena uses the latter to preserve stacks across hands.
- Arena stops a session before starting another hand once any player has busted.
- Arena validates player identity, non-negative stacks and chip conservation before accepting a hand result.
- Scripted manual scenarios have no replay seed and therefore receive structural rather than exact replay verification.
- Table rebuy/top-up, joining/leaving seats and cash-room session rules remain intentionally out of scope.

## Active milestone — Arena v1

### 1. Baseline agents

Implement against `poker.api` only:
- `RandomAgent`;
- `CallingStationAgent`;
- `NitAgent`.

Agents must never inspect `GameState`, `HandController`, opponent hole cards or deck internals.

### 2. Arena runner

Direction:

```text
ArenaRunner
├── rotates dealer positions
├── assigns deterministic hand seeds
├── calls play_hand()
├── aggregates stack deltas
└── reports failures with exact seed
```

Initial statistics:
- hands;
- profit/loss;
- bb/100;
- showdown vs uncontested counts;
- chip conservation / crashes.

Do not add neural models or dataset generation yet.

### 3. Verification requirements

Before and after Arena work run:

```text
python -m pytest -q
python tools/stress_poker.py --hands 10000 --seed 42
python tools/verify_history.py
```

Any randomized failure must report its exact seed.

## Player statistics direction

The project will eventually maintain poker-tracker style statistics.

Required concepts:
- VPIP;
- PFR;
- 3-bet frequency;
- fold to 3-bet;
- continuation bet frequency;
- aggression factor;
- WTSD;
- W$SD;
- positional statistics.

Statistics are not only global player data. Neural agents require separate opponent memory:

```text
NeuralAgent A
    |
    +-- statistics about Player X


NeuralAgent B
    |
    +-- statistics about Player X
```

The same opponent may have different observed histories for different agents.

## AI bootstrap instructions

Before changing the project:

1. Read `docs/DEV_RULES.md`.
2. Read this file.
3. Read `docs/CURRENT_LIMITATIONS.md`.
4. Read `docs/ARCHITECTURE.md`.
5. Inspect the current source tree.

The repository is the source of truth. Do not rely on previous conversation history.

Every patch that changes architecture, capabilities, current focus or next steps MUST update this file.
