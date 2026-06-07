# prediction strategy

## mixed_loto6

`mixed_loto6` はロト6向けの5口strategyです。ロト7向けの `mixed_v3` をそのまま流用せず、ロト6の本数字6個・ボーナス1個の性質に合わせて、頻度、直近傾向、未出現間隔、組合せ補正、5口間の重複抑制を軽く組み合わせます。

profileは以下の5つです。

- `l6_hot_100_core`: 100回窓を主軸にした本線hot profile
- `l6_balanced_150`: 150回窓を使う安定枠
- `l6_recent_50`: 50回窓と直近30回を重視する短期傾向枠
- `l6_gap_repair`: 未出現間隔を補正し、0頻度数字を完全排除しない枠
- `l6_diverse_explore`: 他4口と重複しにくい探索枠

LINE通知のロト6予想は、明示strategyが指定されない場合 `mixed_loto6` を使います。過去データ上の参考評価であり、当選保証ではありません。

## mixed_v3

`mixed_v3` は `mixed_v2` を壊さずに追加したロト7向け strategy です。
目的は当選保証ではなく、過去データ上の検証で profile ごとの役割を比較しやすくし、seed 固定ではなく profile/window の勝ち筋を評価できるようにすることです。

650-679 validation では、初期 `mixed_v3` は 3等相当3件、4等相当218件でした。3等相当は draw 674/679 に偏り、`lane1_ema_hot_core` が最も良く、`lane2_pair_weighted_core` と `lane4_bonus_aware_balanced` は上位一致に弱い傾向でした。

この結果を受けて、現在の `mixed_v3` は以下の方針に再調整しています。

- `lane1_ema_hot_core` は維持し、100回窓と50回探索を厚くする。
- `lane2_pair_weighted_core` は pair affinity をごく弱い補助に下げ、本数字頻度とEMAへ戻す。
- `lane3_long_200_balanced` は 200回窓を主軸ではなく長期補助にする。
- `lane4_bonus_aware_balanced` は bonus affinity をさらに弱め、hit4狙いの本数字・組合せfit profileに寄せる。
- `lane5_diversity_repair` は探索枠として残すが、coverage 寄せを弱める。

## profiles

| index | profile | role |
| --- | --- | --- |
| 1 | `lane1_ema_hot_core` | 100回窓の本数字頻度とEMAを中心に、50回窓の探索も使う本線profile |
| 2 | `lane2_pair_weighted_core` | pair affinity は弱いtiebreakerに留め、frequency/EMAを主軸にするprofile |
| 3 | `lane3_long_200_balanced` | 100回窓を主軸、200回窓を長期補助として使うbalanced profile |
| 4 | `lane4_bonus_aware_balanced` | bonus affinityをかなり弱い補助に留め、hit4向けの自然な組合せを狙うprofile |
| 5 | `lane5_diversity_repair` | 50回窓の探索と軽いcoverage repairで他profileを補完するprofile |

## history window

- `100`: 主軸。650-679では avg_best_score が高く、lane1/lane2/lane3/lane4 の中心に置く。
- `50`: 探索枠。650-679では ticket単位の hit4+ / hit5+ が最も高く、lane1/lane5で残す。
- `150`: 補助。単独固定ではなく、medium windowとして参照する。
- `200`: 長期補助。650-679ではやや弱かったため、主軸ではなくsecondary/longとして扱う。

## score components

- `primary_frequency`: profile の主window内での本数字頻度。
- `secondary_frequency`: 補助window内での本数字頻度。
- `recent_frequency`: 直近寄りの頻度。
- `ema_recent`: 直近出現をなめらかに反映するEMA score。
- `pair_affinity`: 既に選んだ数字との共起傾向。現在は補助信号として弱めに使う。
- `bonus_affinity`: bonus数字としての傾向。現在は最大0.08程度の弱い補助。
- `coverage_gap`: 既存ticketで使われていない数字の補完。現在は探索枠でも強くしすぎない。
- `gap`: 最後に出てからの間隔。
- `trend`: recent と primary frequency の差分。
- `combination_fit`: 奇偶、合計値、連番、レンジ、ticket間重複の軽い補正。

## profile-specific exploration width

`mixed_v3` は profile ごとに top-k stochastic selection の探索幅を変えます。
`lane1_ema_hot_core` と `lane4_bonus_aware_balanced` は少し狭くして本線寄りにし、`lane5_diversity_repair` は広くして探索枠を維持します。

## seed policy

seed は再現性のために使いますが、特定seedを本番ロジックに固定しません。
JSONL の `seed_optimization_used` は `false` とし、profile / draw / history window の傾向を優先して評価します。

## adoption policy

`mixed_v3` は以下を満たす場合だけ本番予想候補にします。

- `mixed_v2` より 3等相当または4等相当が増える。
- `avg_best_score` が改善する。
- draw 674/679 など特定回だけに偏っていない。
- seed分散が大きく悪化していない。
- 650-679 validation だけでなく、675以降または680以降 holdout でも悪化しない。

現時点では、650-679の初期 `mixed_v3` は採用保留です。今回の再調整後に、同条件で再検証してください。
