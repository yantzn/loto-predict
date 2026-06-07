# Loto7 Ranking Model Experiments

This folder contains experimental pipeline code for training and evaluating a learning-based Loto7 ranking model.

These files are intentionally isolated from production logic and are meant for research only.

## Setup

Install the experimental dependencies:

```bash
pip install -r requirements-experiments.txt
```

## Usage

Build a dataset from historical Loto7 CSV data:

```bash
python experiments/build_loto7_dataset.py --input-csv data_samples/loto7_history_sample.csv
```

Train a ranker with time-aware cross-validation:

```bash
python experiments/train_loto7_ranker.py \
  --input-csv data_samples/loto7_history_sample.csv \
  --output-model experiments/loto7_ranker.pkl \
  --history-limit 180 \
  --min-history-draws 50
```

Evaluate the trained model against `mixed_v2` on the final holdout range:

```bash
python experiments/evaluate_loto7_ranker.py \
  --input-csv data_samples/loto7_history_sample.csv \
  --model-path experiments/loto7_ranker.pkl
```
