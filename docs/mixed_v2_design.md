# mixed_v2 Design

## 目的

`mixed_v2` は、既存 `mixed` の本線 profile を壊さず、過去データ上の参考評価をもとに 5 口の役割を分けるための strategy です。当選保証ではなく、validation / holdout で比較可能な予想ロジックにすることを目的にしています。

## 今回の調整方針

- `history_limit=100` を主軸として扱う。
- `lane3_pair_weighted` は平均点は高い一方で上位一致に弱いため、pair score の比率を下げる。
- `lane1` / `lane2` / `lane4` は 3 等相当実績があるため維持する。
- `lane5_diverse_explore` は探索枠として残すが、探索の強さは下げる。
- seed の最適化ではなく、profile ごとの勝ち筋を draw ごとに学習・比較できる JSONL を残す。

## 5 lane 構成

1. `lane1_ema_hot_or_main_hot`
   - `history_limit=100` では `main_hot` を維持する。
   - 深い履歴では EMA hot に切り替えるが、閾値は `200` として早すぎる切り替えを避ける。

2. `lane2_main_balanced_or_ema_balanced`
   - `history_limit=100` では `main_balanced` を維持する。
   - 深い履歴では EMA balanced を使う。

3. `lane3_pair_weighted`
   - pair co-occurrence は補助扱いにする。
   - 通常時の blend は `base=0.62`, `ema=0.25`, `pair=0.08`, `explore=0.05`。
   - pair support が少ない場合は `base=0.74`, `ema=0.23`, `explore=0.03` に fallback する。

4. `lane4_bonus2_balanced`
   - 5 main + 2 bonus の bonus-aware lane として維持する。
   - 本数字を主軸にし、bonus は補助として扱う。

5. `lane5_diverse_explore`
   - 探索枠として残す。
   - 候補プールを広げすぎず、bonus 寄りと quality 加点を下げて、他 lane の本線を邪魔しにくくする。

## profile 学習

backtest JSONL には以下を出力します。

- `profile`
- `profile_learning_key`
- `profile_learning_candidate`
- `seed_optimization_used`
- `score_breakdown`

これにより、seed 単体の当たり外れではなく、`draw_no x profile x history_limit` の傾向を後続分析で追えるようにします。
