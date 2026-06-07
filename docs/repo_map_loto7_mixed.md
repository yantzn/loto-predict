# LOTO7 Mixed Strategy Repo Map

This document serves as the single source of truth for the implementation locations of the `mixed` strategy for LOTO7 backtesting and prediction.

## 1. CLI Entrypoint
- **File**: `jobs/backtest_loto_prediction/main.py`
- **Responsibility**: Parses CLI arguments (including `--strategy mixed`), manages batch execution across target draws, history limits, and seeds, and coordinates evaluation and serialization.

## 2. Mixed Strategy Factory/Registry
- **File**: `src/domain/prediction.py`
- **Functions**: 
  - `generate_predictions()` (Handles the `strategy="mixed"` branching)
  - `_loto7_profiles()` (Provides the 5 specific profiles)
  - `_build_mixed_depth_ticket()` / `_build_second_prize_oriented_ticket()` (Builds tickets based on profiles)
- **Responsibility**: Routing the `mixed` strategy to the specific profiles and constructing the prediction tickets.

## 3. 5 Profile Definitions
- **File**: `src/domain/prediction.py` (and profile mapping in `jobs/backtest_loto_prediction/main.py`)
- **Functions/Vars**: 
  - `src/domain/prediction.py`: `_loto7_profiles(prediction_count: int) -> list[Loto7Profile]` defines the weights, pool sizes, and temperatures for:
    - `main_hot`
    - `main_balanced`
    - `main_wide_bonus_hot`
    - `main5_bonus2_balanced`
    - `main5_bonus2_explore`
  - `jobs/backtest_loto_prediction/main.py`: `LOTO7_PROFILE_BY_TICKET_NO` maps ticket indices 1-5 to these profile names.

## 4. Ticket Score Calculation & Aggregation
- **File**: `jobs/backtest_loto_prediction/main.py`
- **Functions**: 
  - `_judge_loto7_prize()`: Determines the prize tier.
  - `_score_near_miss()`: Calculates the near-miss score.
  - `_evaluate_once()`: Evaluates matching against targets.
  - `_print_batch_summary()`, `_print_group_summary()`, `_print_ticket_summary()`: Aggregates metrics (`avg_best_score`, `best_prize`, etc.).
- **Responsibility**: Determining how well a generated ticket matched the actual winning numbers and scoring it.

## 5. JSONL Output Structure
- **File**: `jobs/backtest_loto_prediction/main.py`
- **Functions**: 
  - `_write_jsonl()`
  - The dictionary structure is defined in `_evaluate_once()` return value.
- **Responsibility**: Serializes the evaluation result of each run (target_draw, history_limit, seed combo) into a JSONL format containing metadata and a `tickets` array.

## 6. Pytest Root and Related Tests
- **Test Root**: `tests/`
- **Related Tests**: 
  - `tests/test_prediction.py` (Tests `generate_predictions` and underlying logic)
  - `tests/backtest/test_loto7_mixed_baseline_snapshot.py` (Validates the output JSONL summary matches the expected baseline metrics)
