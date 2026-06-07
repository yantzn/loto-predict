# backtest_loto_prediction

`jobs/backtest_loto_prediction` は、ロト予想 strategy を過去データ上で比較するためのCLIです。
これは当選保証ではなく、過去データ上の参考評価として扱います。

## input data

ローカル検証では以下を使います。

```powershell
./local_storage/imported/loto7_history.jsonl
```

対象回そのものは学習データに含めず、`target_draw_no` より前の履歴だけで予想を生成します。

## mixed_v3 650-679 validation result

初期 `mixed_v3` を 650-679、history_limit 50/100/150/200、seed 1-300、5口で検証した結果です。

| metric | value |
| --- | ---: |
| total_runs | 36,000 |
| total_tickets | 180,000 |
| 1等相当 | 0 |
| 2等相当 | 0 |
| 3等相当 | 3 |
| 4等相当 | 218 |
| 5等相当 | 2,826 |
| 6等相当 | 4,309 |

profile別では `lane1_ema_hot_core` が最も良く、3等相当2件、4等相当64件でした。
一方で `lane2_pair_weighted_core` は pair 寄せの割に上位一致が弱く、`lane4_bonus_aware_balanced` も bonus 寄せが本数字一致に効きにくい結果でした。

この結果を受け、現在の `mixed_v3` では以下を修正しています。

- `lane1_ema_hot_core`: 維持。100回窓と50回探索を厚くする。
- `lane2_pair_weighted_core`: pair affinity をさらに下げ、本数字頻度とEMAを増やす。
- `lane3_long_200_balanced`: 200回窓を主軸から長期補助へ下げる。
- `lane4_bonus_aware_balanced`: bonus affinity をさらに弱め、hit4狙いの組合せfitを強める。
- `lane5_diversity_repair`: 探索枠は残すが、coverage重みを下げる。

追加の再改善では、`lane1` と `lane4` の top-k 探索幅を狭め、`lane5` は探索幅を広めに残しています。これにより、本線profileは上位候補に寄せ、探索profileは他ticketとの補完を担当します。

## validation commands

650-679 validation:

```powershell
python jobs/backtest_loto_prediction/main.py --lottery-type loto7 --target-draw-from 650 --target-draw-to 679 --history-limits 50,100,150,200 --prediction-count 5 --seed-from 1 --seed-to 300 --input-jsonl ./local_storage/imported/loto7_history.jsonl --output-jsonl ./local_storage/backtest/loto7_mixed_v3_650_679.jsonl --strategy mixed_v3
```

比較用 `mixed_v2`:

```powershell
python jobs/backtest_loto_prediction/main.py --lottery-type loto7 --target-draw-from 650 --target-draw-to 679 --history-limits 50,100,150,200 --prediction-count 5 --seed-from 1 --seed-to 300 --input-jsonl ./local_storage/imported/loto7_history.jsonl --output-jsonl ./local_storage/backtest/loto7_mixed_v2_650_679.jsonl --strategy mixed_v2
```

module実行:

```powershell
python -m jobs.backtest_loto_prediction.main --lottery-type loto7 --target-draw-from 650 --target-draw-to 679 --history-limits 50,100,150,200 --prediction-count 5 --seed-from 1 --seed-to 300 --input-jsonl ./local_storage/imported/loto7_history.jsonl --output-jsonl ./local_storage/backtest/loto7_mixed_v3_650_679.jsonl --strategy mixed_v3
```

675以降 holdout:

```powershell
python jobs/backtest_loto_prediction/main.py --lottery-type loto7 --target-draw-from 675 --target-draw-to 9999 --history-limits 50,100,150,200 --prediction-count 5 --seed-from 1 --seed-to 300 --input-jsonl ./local_storage/imported/loto7_history.jsonl --output-jsonl ./local_storage/backtest/loto7_mixed_v3_675_holdout.jsonl --strategy mixed_v3
```

## output

JSONL は ticket 単位で出力します。主な項目は以下です。

- `strategy`
- `strategy_version`
- `profile`
- `profile_role`
- `profile_learning_key`
- `seed_optimization_used`
- `target_draw`
- `history_limit`
- `seed`
- `ticket_index`
- `prediction`
- `score`
- `score_breakdown`
- `matched_main`
- `matched_bonus`
- `prize_equivalent`

## adoption policy

`mixed_v3` は、以下を満たす場合だけ本番予想候補にします。

- `mixed_v2` より 3等相当または4等相当が増える。
- `avg_best_score` が改善する。
- `hit4_or_more_rate` または `hit5_or_more_rate` が改善する。
- score分散やdraw偏りが大きく悪化しない。
- 650-679 validation だけでなく、675以降 holdout でも悪化しない。

650-679の初期結果では採用保留です。再調整後の `mixed_v3` を同条件で再検証してください。
