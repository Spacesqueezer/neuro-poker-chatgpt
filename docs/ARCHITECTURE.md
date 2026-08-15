# Neuro Poker Architecture

## System Layers

Computer Vision
        |
        v
State Extraction
        |
        v
Poker State Model
        |
        v
Strategy System
        |
        v
Decision Engine
        |
        v
Action Executor


## Separation Rules

Vision does not make decisions.

Poker engine does not know about AI.

AI does not depend on screenshots.

Every layer must be testable independently.

## AI Architecture

Recommended modular approach:

- State Encoder
- Hand Evaluation Module
- Opponent Model
- Strategy Network
- Decision Engine
- Memory System

## Poker Domain Ownership

Persistent seating and one-hand state are separate:

```text
Table
└── Seat[]
    ├── SeatStatus
    └── Player
        └── Hand

GameState
├── Table
├── Player[]  # participants in the current/next hand
├── Deck
├── Board
├── BettingState
├── RoundManager
└── TurnOrder
```

`Table` owns stable physical seats and dealer-button seat continuity between hands. `GameState.players` is a hand-participant projection derived from funded `ACTIVE` seats when a hand is prepared. Busted and sitting-out players remain seated but do not enter the next hand.

Hole cards are owned by `Player.hand`. Betting and action systems operate only on the current hand participant view.


## Hand Flow Coordination

`HandController` coordinates one active hand:

```text
HandController
├── Dealer
├── ActionResolver
├── BettingRound
│    └── Player[]
└── PotManager
```

Responsibilities:
- `HandController` owns betting-round lifecycle and street progression.
- `ActionResolver` applies a validated player action to Player state.
- `BettingRound` tracks who still owes action and reopens action after a bet increase.
- `TurnOrder` selects the acting Player and skips folded players.
- `BettingState` stores the accumulated pot and current street target bet.
- `PotManager` derives main/side pot layers from `Player.total_contribution` and settles each layer independently at showdown.

Completed betting rounds collect each `Player.current_bet` into the pot before the next street begins.


## Pot Accounting

Per-hand contribution is owned by `Player.total_contribution`; street-local commitment remains in `Player.current_bet`.

`PotManager` is the single settlement component for contested showdown money:

```text
Player.total_contribution[]
        |
        v
PotManager.build_layers()
        |
        +--> main pot
        +--> side pot 1
        +--> side pot N
        +--> unmatched refund
        |
        v
PotManager.settle()
```

Folded players still fund layers through their contribution but are removed from that layer's eligible winners. Ties are split per layer. Odd chips are assigned deterministically starting with the first tied winner left of the dealer button.

## HandHistory

`poker.game.hand_history` is the structured event record for a completed hand. `HandController` records domain events; persistence is handled separately by `HandHistoryStore`. Debug tooling may serialize histories to JSONL without making the poker engine depend on filesystem storage.

## Verification Layer

Verification tooling depends on the poker engine, never the reverse.

```text
HandHistory
    |
    +--> HandReplayVerifier
    |       +--> exact replay for seed-based hands
    |       +--> structural checks for scripted histories
    |
    +--> hand_history_viewer.py

HandController + Dealer
    |
    +--> stress_poker.py
            random legal actions
            invariant checks
```

`HandReplayVerifier` reconstructs seed-based hands from starting stacks, dealer position, blinds, seed and recorded actions. The replayed structured history must match the recorded history except for the generated hand id.

`stress_poker.py` is verification tooling, not an agent/Arena abstraction. Its legal-action policy must not become a dependency of the engine.

## Public Simulation Boundary

Agent and Arena code must use `poker.api`; it must not depend on hand-controller internals.

```text
Poker engine internals
        |
        v
poker.api
├── HandStateView
│   └── PublicActionView[]  # prior public actions only
├── PublicPlayerView
├── LegalActions
├── ActionDecision
└── play_hand()
        |
        v
Agents / Arena
```

`HandStateView` contains public state, canonical table positions, only the acting player's hole cards, and an immutable projection of prior public action events. `PublicActionView` is derived from the current `HandHistory` action events and never exposes future actions, hidden cards, deck state or controller internals. `LegalActions` contains action availability and sizing bounds. `play_hand()` validates an agent decision against that query surface and then delegates mutation to `HandController`, which remains the source of truth for action execution.

This boundary prevents Arena, baseline agents and future learning systems from duplicating poker legality rules.

## Statistics Persistence

Statistics consumers depend on repository contracts, not on SQLAlchemy directly:

```text
StatisticsService / future NeuralAgent opponent model
                    |
                    v
            repository contracts
             /             \
            v               v
      in-memory         SQLAlchemy
                        repositories
                            |
                            v
                     SQLAlchemy Session
                            |
                            v
          players / player_statistics / agent_memory
```

`PlayerRecord`, `PlayerStatisticsRecord` and `AgentMemoryRecord` remain transport/domain records at the repository boundary. SQLAlchemy models are persistence-only objects. `PlayerStatisticsRecord` persists both derived tracker rates and their raw numerators/denominators; the counters are the durable aggregation source of truth and prevent mathematically invalid averaging of percentages across sessions. Positional VPIP/PFR/3-bet data is stored separately in `player_position_statistics` with `(player_id, position)` as the key, avoiding a wide column-per-position schema. `AgentMemoryModel` uses `(agent_id, player_id)` as a composite primary key so each neural agent can maintain an independent view of the same opponent.

Completed engine histories feed statistics through a separate read-only mapping path:

```text
HandHistory
    |
    v
HandStatisticsMapper
    |
    v
per-player hand facts
    |
    v
HandStatisticsAdapter
    |
    v
StatisticsCollector
    |
    v
StatisticsService.persist_collector()
    |
    v
StatisticsRepository
```

`StatisticsCollector` remains an in-memory aggregation object and has no database dependency. `StatisticsService` is the persistence boundary: it resolves collector player names to stable `PlayerRecord` identities through `PlayerRepository`, creating missing roster entries when needed; explicit stable-id mappings remain available for controlled callers. It converts snapshots into `PlayerStatisticsRecord` values, merges raw counters with any existing stored record, recalculates derived rates from the merged counters, and writes through repository contracts. Player names are unique at the SQL schema boundary so repeated Arena/dataset sessions resolve the same logical player instead of creating duplicate identities. This allows the same flow to use memory repositories in tests and SQLAlchemy/PostgreSQL repositories in production.

Arena integrates at orchestration level rather than inside the poker engine:

```text
ArenaSession
    |
    +-- successful HandHistory
            |
            v
ArenaRunner
    |
    +-- HandStatisticsAdapter
    |       |
    |       v
    |   StatisticsCollector
    |
    +-- optional StatisticsService
            |
            v
      persistent player profile
```

`ArenaSession` only exposes an optional successful-hand observer and remains unaware of statistics or storage. Statistics/persistence failures are therefore not misclassified as poker-hand failures.

Canonical player position is written into each `HandHistory.players` entry by the poker domain when the hand starts. Position labels are derived from dealer-relative seat order for 2-9 handed tables, so downstream statistics do not need to reconstruct seat semantics.

The mapper derives facts only from recorded public hand events and the recorded player-position metadata; it does not inspect live `GameState` or `HandController`. For compatibility, already-aggregated player dictionaries are accepted and their existing flags are preserved. Opportunity-based metrics are derived from action order: a player acting after one preflop raise receives a 3-bet opportunity, an opener facing the second raise receives a fold-to-3-bet opportunity, and the final preflop aggressor receives a flop c-bet opportunity only when action reaches that player before a postflop bet. Once a c-bet occurs, each opponent's first direct response is a fold-to-cbet opportunity until an opponent raises, after which later action is no longer attributed directly to the original c-bet. Postflop bets/raises/all-ins and calls are counted globally and separately for flop/turn/river aggression-factor calculation. Raw counters remain the persistence source of truth. This keeps statistics reproducible from persisted histories without breaking the earlier statistics input contract.

Opponent-facing feature extraction sits above persistence:

```text
StatisticsFacade
      |
      v
OpponentProfileProvider
      |
      +--> global persisted tracker statistics
      +--> positional statistics
      +--> optional agent-specific memory
      |
      v
immutable OpponentProfile
      |
      v
OpponentProfileEncoder
      |
      v
fixed named feature tuple
      |
      v
LearningObservationEncoder
      |
      +--> HandStateView public/card/table features
      +--> zero-padded opponent slots (max 8)
      +--> explicitly scoped opponent-profile features
      |
      v
fixed LearningObservation
      |
      +----------------------+
      |                      |
      v                      v
LearningActionEncoder   chosen ActionDecision
      |                      |
      +----------+-----------+
                 |
                 v
        versioned LearningSample
                 |
                 v
       LearningDatasetCapture
                 |
                 v
       LearningDatasetWriter
                 |
                 v
              JSONL
                 |
                 v
       LearningDatasetAnalyzer
                 |
                 v
       LearningDatasetGenerator
          /             \
         v               v
    train.jsonl    validation.jsonl
         \               /
          +------v-------+
                 |
                 v
          future policy
```

Teacher policies remain ordinary public-API agents:

```text
HandStateView + LegalActions
          |
          v
      ExpertAgent
          |
          +--> MonteCarloEquityEstimator
          |       |
          |       +--> unknown-card rollout
          |       +--> engine seven-card evaluator
          |
          +--> pot odds / value thresholds
          +--> legal bet/raise sizing
          |
          v
    ActionDecision
```

The expert must not inspect engine internals, deck state or hidden opponent cards. Its Monte-Carlo deck is reconstructed only from publicly known cards. Opponent hole cards are sampled through a range-model boundary before future board cards are sampled:

```text
public opponent position
        |
        v
 PositionRangeModel
        |
        v
weighted legal two-card combos
        |
        v
MonteCarloEquityEstimator
        |
        +--> sample opponent cards without collisions
        +--> sample remaining board cards
        +--> seven-card evaluation
```

`PositionRangeModel` starts from a position prior and derives an immutable `OpponentRangeState` only from `HandStateView.action_history`. The state classifies the opponent's preflop line as unopened/call/open-raise/3-bet/4-bet+/all-in, tracks calls/aggression separately on flop, turn and river, and retains maximum public aggression sizing ratios for each street. `combo_distribution()` materializes every legal two-card combination and assigns a normalized probability to each. Preflop evidence reweights structural hand classes, while `BoardInteraction` classifies every postflop candidate against the public board as pair/two-pair+/trips+, overpair, straight, flush, straight draw or flush draw. An optional `OpponentProfileProvider` supplies storage-agnostic persisted evidence: position/global VPIP/PFR/3-bet and street aggression adjust combo weights with influence capped by hand-sample reliability; agent-specific memory can be blended by its confidence when an agent id is supplied. `ExpertAgent` only receives the provider abstraction and never repositories/SQLAlchemy. Monte-Carlo sampling consumes the resulting explicit distribution. `UniformRangeModel` remains a control. No range code may inspect hidden engine state. These probabilities are exploit-oriented heuristic beliefs, not a solved equilibrium; the solver layer remains a separate abstraction.

The first solver boundary is intentionally independent from the production Hold'em engine:

```text
KuhnPokerGame
     |
     v
 CFRTrainer
     |
     +--> regret matching
     +--> reach probabilities
     +--> cumulative regrets
     +--> average strategy
     |
     v
  CFRResult
```

`poker.solver` now separates CFR from individual games through `TwoPlayerSolverGame`. Games expose weighted initial chance nodes, player-to-act, terminal utility, information sets, legal actions and child transitions. `KuhnPokerGame` remains the deterministic correctness harness and still converges near the known Kuhn game value. `RestrictedHeadsUpHoldemGame` is the first Hold'em adapter: it accepts an explicit finite weighted deal set, a fixed five-card public board, either the backward-compatible equal `starting_stack` or explicit public `starting_stacks=(player0, player1)`, and a deliberately small preflop action tree with fold/call, one fixed 3x-big-blind raise and all-in. Showdown uses the production seven-card evaluator, while solver nodes explicitly track street, player-specific stack caps and commitments; information sets contain only the acting player's hole cards plus public board/action/commitment/stack state. Future board cards from the fixed deal are never exposed preflop. CFR accumulation includes chance reach so non-uniform deal weights remain mathematically meaningful. The adapter deliberately does not consume `HandStateView`, opponent profiles, `HandController` or hidden production engine state. External-sampling MCCFR and weighted initial chance sampling now sit on this boundary. Postflop street progression is modeled without importing the production hand loop: preflop call/raise-call enters the flop, each street supports check or a finite configured bet-size set, a bet may be folded, called or raised once, and check/check or bet/call advances to the next street. `HoldemActionAbstraction` owns the restricted tree's preflop raise size, ordered discrete postflop sizing tuple and one finite postflop raise increment. Each postflop size is encoded in action identity (`bet_Nbb`), so information sets expose distinct finite branches without importing production no-limit sizing rules. Solver nodes carry player-explicit public commitments; `matched_stake` is derived as the minimum commitment rather than being the accounting source of truth. Calls, bets, raises and all-ins are capped by the acting player's public starting stack. Fold and showdown utility use only matched commitments, so unmatched chips are effectively refunded when one player cannot cover the other. All-in handling is solver-local: once betting closes with either commitment at its stack cap, the node becomes a terminal fixed-board showdown runout; no synthetic later-street checks are inserted. Legal-action generation removes commitment-increasing branches that cannot increase the actor's commitment, deduplicates configured postflop bet sizes that collapse to the same capped target, suppresses raises/over-shoves when the opponent is already all-in, and prevents a raise against a bettor already at its stack cap. A big blind posted all-in still gives the small blind its real fold/call decision, while a small blind already exhausted by posting starts directly at runout. Re-raises remain excluded.

Solver strategy persistence is a separate boundary above the trainer result:

```text
ExternalSamplingMCCFR
        |
        v
   MCCFRResult
        |
        v
build_strategy_export()
        |
        v
versioned JSON strategy artifact
```

The export contains benchmark/configuration metadata plus sorted average-strategy entries. Information-set serialization is explicit rather than generic tuple serialization: only acting-player hole cards and solver-public fields are emitted. This preserves the solver's imperfect-information boundary and makes the artifact deterministic for equal inputs.

Artifact loading validates the complete versioned boundary before use. `StrategyLookup` then indexes entries by canonical JSON serialization of the explicit information-set object and performs exact lookup from live restricted-solver information sets. Missing entries return `None`; no nearest-neighbor or card abstraction happens at this layer.

`RestrictedSolverPolicy` sits above lookup but remains inside `poker.solver`. It asks the game for the current acting player, information set and legal actions, filters an exact stored strategy to those legal actions and renormalizes the remaining probability mass. Missing lookup entries or zero legal overlap produce an explicit uniform strategy over the current legal actions. Deterministic action selection uses argmax and preserves the game's legal-action order for ties. This adapter still does not implement `poker.api.Agent`.

Policy coverage is measured by a separate solver-local evaluation boundary. `evaluate_restricted_policy()` validates that artifact stacks, blinds and action abstraction match the evaluation game, then traverses every legal branch from every fixed initial chance node. It classifies each decision as exact action-set coverage, reconciled action-set coverage, missing-information fallback or zero-overlap fallback, while also counting unique information sets and deterministic policy selections. The harness does not train and does not use Arena, so artifact compatibility/coverage remains independently testable from MCCFR quality and production poker behavior.

The artifact smoke workflow composes existing boundaries rather than creating another solver abstraction:

```text
small MCCFR train
      |
      v
strategy export
      |
      v
write -> load -> validate
      |
      v
StrategyLookup
      |
      v
RestrictedSolverPolicy
      |
      v
full-tree coverage report
```

`tools/smoke_solver_artifacts.py` runs this sequence for explicit benchmark scenarios and writes per-scenario strategy artifacts plus one structural report. Its default training workload is intentionally tiny; solver convergence remains the responsibility of `benchmark_mccfr.py`, not the smoke workflow.

Benchmark chance space is also explicit. `equal` and `asymmetric` retain the original single deterministic AA-vs-KK deal. `weighted_multi` supplies three fixed deals with positive weights 5/3/2; `RestrictedHeadsUpHoldemGame.initial_nodes()` normalizes those weights to 0.5/0.3/0.2. Distinct chance nodes may intentionally collapse to the same information set when the acting player cannot distinguish them. In particular, two weighted benchmark deals share player 0's preflop AA while differing in opponent private cards and unrevealed board cards. This preserves imperfect-information semantics while exercising weighted external sampling over more than one initial chance state.

Strategy artifact format version 2 binds persistence to that hidden chance model. `chance_space_metadata()` canonicalizes the ordered deal list including both players' private cards, complete fixed board and raw weights, hashes the canonical JSON with SHA-256, and stores the identity together with deal count and normalized initial probabilities. These hidden cards are artifact metadata, not information-set data: they are used only to identify the training game and are never exposed through policy lookup. Loading validates the metadata shape, and policy evaluation requires the artifact identity to exactly match the live restricted game before strategy traversal.

Benchmark configuration is centralized in frozen `BenchmarkScenario` descriptors. A descriptor owns its stable name, public starting stacks and deal factory, constructs the restricted game with the canonical action abstraction, and exposes the resulting chance-space identity. The ordered `BENCHMARK_SCENARIOS` registry is therefore the single configuration boundary shared indirectly by benchmark, export, evaluation and smoke tooling while the CLI continues to pass plain scenario names.

Solver teacher records are a separate research boundary derived from validated strategy artifacts rather than production observations. The exporter reconstructs the exact benchmark game, traverses live restricted nodes and emits only information sets with stored legal probability mass. Each record contains the explicit serialized information set, the current legal solver actions, normalized probabilities restricted to those actions, and an exact/reconciled source marker. Missing lookup entries and zero legal overlap are diagnostics only and never become teacher labels. The export carries the complete source strategy benchmark/chance-space/action-abstraction metadata and remains independent from `poker.learning` and `poker.api`.

Teacher artifacts have their own strict read boundary. Structural validation rejects malformed records before use, while compatibility validation takes the original strategy artifact plus reconstructed benchmark game and requires exact source metadata equality after the strategy itself passes chance-space/game validation. Persistence validation therefore cannot manufacture solver semantics: a teacher artifact is accepted only when both its internal record contract and its provenance back to the exact source strategy remain intact.

Teacher quality is measured outside the agent:

```text
ExpertBenchmarkRunner
      |
      +--> session 1: Expert vs baseline
      +--> session 2: reset stacks, alternate first dealer
      +--> ...
      |
      v
aggregate actual hands
+ failures
+ Expert profit
+ bb/100
+ showdown/uncontested counts
+ completion rate
```

Each benchmark session creates fresh agent instances with deterministic derived seeds. Ordinary `ArenaSession` bust semantics remain unchanged; benchmark orchestration resets stacks by starting a new Arena session. This prevents one bust from truncating an entire teacher-quality experiment while preserving reproducibility.

`LearningDatasetGenerator` is orchestration above Arena and the dataset boundary. It constructs explicitly named agents, derives deterministic seeds for stochastic agents, can filter capture to one configured teacher, captures a clean raw JSONL dataset, performs a seeded deterministic sample-level train/validation split, analyzes every split and writes a manifest containing the generation configuration and Arena failure count. Generation fails if any Arena hand fails, preventing silent partial datasets. `RandomAgent` is required to obey the same `LegalActions` contract as every other agent, including legal BET/RAISE sizing. Generated data remains outside the poker engine and is safe to delete/rebuild. The standalone generator currently requires global profile scope because no online agent-memory updater exists yet; private-memory training must wait for an explicit observation-history update path rather than treating zero-filled memory as meaningful knowledge.

The public simulation loop owns the only decision-capture hook. `play_hand()` invokes an optional `decision_observer(view, legal, decision)` only after the agent decision has passed `LegalActions` validation and before `HandController` mutates state. Arena forwards the callback but remains unaware of learning/dataset classes. To preserve the historical Arena/session call contract, `ArenaSession` omits the `decision_observer` keyword entirely when no observer is configured. This keeps existing alternate `play_hand` callables and monkeypatch tests compatible. The dependency direction remains `poker.api` exposes observations/events while `poker.learning` subscribes from outside.

`LearningDatasetCapture` converts each validated decision into a versioned sample, `LearningDatasetWriter` appends one compact JSON object per line, and `LearningDatasetAnalyzer` rejects unsupported versions, malformed action masks and masked target actions before reporting dataset distributions.

`LearningActionEncoder` consumes the same public `LegalActions` contract used to validate agents. Its action order is fixed as fold/check/call/bet/raise/all-in, with a six-element legality mask and normalized call/bet/raise sizing bounds. `LearningSampleBuilder` validates the chosen `ActionDecision` against `LegalActions` before recording its action index and normalized amount, so invalid labels cannot silently enter a dataset. `LearningSample` is versioned and serializable without engine or persistence objects.

`LearningObservationEncoder` is the learning-facing state boundary. It consumes only `poker.api.HandStateView` plus `OpponentProfileProvider`; it does not import engine internals or persistence models. Hole cards and board cards use independent fixed 52-way one-hot sections, streets use one-hot encoding, chip/bet values are normalized by the total chips represented in the public state, and opponent slots preserve public player order with zero padding up to 9-max. Profile scope must be chosen explicitly: `private` masks all global tracker fields and exposes only agent-specific memory, `global` masks memory, and `combined` exposes both.

`OpponentProfileProvider` is the composition boundary for opponent snapshots. Strategy and learning code must not query SQLAlchemy models or repositories directly. `OpponentProfileEncoder` currently exposes a fixed 22-feature schema containing global rates, a selected-position slice, street aggression, showdown metrics and agent-memory estimates/confidence. Missing statistics, positions or memory are represented by zero-valued features so dimensionality remains stable. Global tracker history and agent-specific memory are deliberately represented as distinct concepts. Future live-agent integration must choose the permitted information scope explicitly instead of accidentally giving an agent global knowledge it could not have observed.

SQLite in-memory is the fast persistence test backend. PostgreSQL uses the same repository contracts and has an opt-in integration path driven by `POKER_TEST_DATABASE_URL`; that database must be disposable because the integration test resets it to Alembic `base` before upgrading to `head`. Alembic owns schema evolution through `migrations/`; `src/poker/statistics/database/migrations.py` is the programmatic upgrade/downgrade boundary. Runtime migration URLs may be supplied explicitly by callers or through `POKER_DATABASE_URL` in Alembic execution. Schema changes must be represented by revisions rather than leaking database concerns into statistics services.
