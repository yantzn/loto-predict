FROM python:3.12-slim

WORKDIR /app

# Backfillジョブはsrc配下の実装を使うため、リポジトリ全体をコンテナへ配置する。
COPY . /app

# Cloud Run Jobで必要な依存をインストールする。
RUN pip install --no-cache-dir -r requirements-base.txt

# 実行時の引数はTerraform/Cloud Run Job側で渡す。
CMD ["python", "jobs/backfill_loto_history/main.py"]
