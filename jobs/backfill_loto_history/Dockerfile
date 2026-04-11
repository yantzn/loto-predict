FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY jobs/backfill_loto_history/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY jobs/backfill_loto_history /app/jobs/backfill_loto_history

ENTRYPOINT ["python", "/app/jobs/backfill_loto_history/main.py"]
