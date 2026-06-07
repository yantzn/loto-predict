"""Grid-search helper for EMA recency parameters.

EMAのalpha/weight候補を小さな範囲で比較し、backtest前の当たりを付けるための実験補助ツールです。
"""

import json
import subprocess
from pathlib import Path
from statistics import mean

WORKDIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = WORKDIR / "local_storage" / "backtest"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

configs = [
    {
        "name": "default",
        "alpha_short": 0.20,
        "alpha_mid": 0.10,
        "alpha_long": 0.05,
        "short_weight": 0.45,
        "mid_weight": 0.35,
        "long_weight": 0.20,
        "include_bonus": False,
    },
    {
        "name": "mid_boost",
        "alpha_short": 0.18,
        "alpha_mid": 0.10,
        "alpha_long": 0.05,
        "short_weight": 0.30,
        "mid_weight": 0.45,
        "long_weight": 0.25,
        "include_bonus": False,
    },
    {
        "name": "long_blend",
        "alpha_short": 0.15,
        "alpha_mid": 0.08,
        "alpha_long": 0.03,
        "short_weight": 0.25,
        "mid_weight": 0.35,
        "long_weight": 0.40,
        "include_bonus": False,
    },
    {
        "name": "fast_short",
        "alpha_short": 0.30,
        "alpha_mid": 0.15,
        "alpha_long": 0.08,
        "short_weight": 0.50,
        "mid_weight": 0.30,
        "long_weight": 0.20,
        "include_bonus": False,
    },
    {
        "name": "include_bonus",
        "alpha_short": 0.20,
        "alpha_mid": 0.10,
        "alpha_long": 0.05,
        "short_weight": 0.45,
        "mid_weight": 0.35,
        "long_weight": 0.20,
        "include_bonus": True,
    },
]

base_cmd = [
    str(WORKDIR / ".venv" / "Scripts" / "python.exe"),
    str(WORKDIR / "jobs" / "backtest_loto_prediction" / "main.py"),
    "--lottery-type",
    "loto7",
    "--target-draw-from",
    "600",
    "--target-draw-to",
    "602",
    "--history-limits",
    "20,100",
    "--prediction-count",
    "5",
    "--seed-from",
    "1",
    "--seed-to",
    "20",
    "--input-jsonl",
    "./local_storage/imported/loto7_history.jsonl",
    "--strategy",
    "ema_recency",
]

summary_rows = []

for config in configs:
    output_file = OUTPUT_DIR / f"ema_recency_grid_{config['name']}.jsonl"
    cmd = base_cmd + [
        "--output-jsonl",
        str(output_file),
        "--ema-alpha-short",
        str(config["alpha_short"]),
        "--ema-alpha-mid",
        str(config["alpha_mid"]),
        "--ema-alpha-long",
        str(config["alpha_long"]),
        "--ema-short-weight",
        str(config["short_weight"]),
        "--ema-mid-weight",
        str(config["mid_weight"]),
        "--ema-long-weight",
        str(config["long_weight"]),
        "--ema-include-bonus",
        "true" if config["include_bonus"] else "false",
    ]

    print(f"Running {config['name']}...")
    subprocess.run(cmd, cwd=WORKDIR, check=True)

    runs = []
    prizes = {}
    with output_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            runs.append(row)
            for ticket in row.get("tickets", []):
                prize = ticket.get("prize", "該当なし")
                prizes[prize] = prizes.get(prize, 0) + 1

    avg_best_score = mean(row.get("best_near_miss_score", 0) for row in runs)
    third_prizes = prizes.get("3等相当", 0)
    second_prizes = prizes.get("2等相当", 0)
    summary_rows.append(
        {
            "name": config["name"],
            "avg_best_score": avg_best_score,
            "third_prizes": third_prizes,
            "second_prizes": second_prizes,
            "total_runs": len(runs),
            "prizes": prizes,
        }
    )

print(json.dumps(summary_rows, indent=2, ensure_ascii=False))
