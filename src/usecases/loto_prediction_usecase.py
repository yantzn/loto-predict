import random
from datetime import datetime
from src.infrastructure.bigquery_client import bq_client
from src.infrastructure.line_client import line_client
from src.config.settings import get_settings
from src.domain.models import Prediction, PredictionRun
from src.utils.logger import get_logger

logger = get_logger()

LOTO6_MIN, LOTO6_MAX, LOTO6_PICK = 1, 43, 6
LOTO7_MIN, LOTO7_MAX, LOTO7_PICK = 1, 37, 7


def generate_and_notify_prediction(lottery_type: str) -> dict:
    """
    ユースケース: 予想番号を生成し、LINE通知・記録を行う（旧ロジック）
    - 責務: BigQueryから履歴取得、頻度集計、重み付き乱択、通知・記録

    Args:
        lottery_type (str): 'loto6' または 'loto7'

    Returns:
        dict: 予想結果サマリ
    """
    settings = get_settings()
    if lottery_type == 'loto6':
        table = 'loto6_history'
        pick_count = settings.lottery.loto6_pick_count
        number_min = settings.lottery.loto6_number_min
        number_max = settings.lottery.loto6_number_max
        history_limit = settings.lottery.stats_target_draws
    elif lottery_type == 'loto7':
        table = 'loto7_history'
        pick_count = settings.lottery.loto7_pick_count
        number_min = settings.lottery.loto7_number_min
        number_max = settings.lottery.loto7_number_max
        history_limit = settings.lottery.stats_target_draws
    else:
        logger.error('Invalid lottery_type')
        return None

    # 履歴取得
    rows = bq_client.fetch_history(table, history_limit)
    # 出現回数集計
    freq = {}
    for row in rows:
        for i in range(1, pick_count+1):
            n = row[f'n{i}']
            freq[n] = freq.get(n, 1) + 1
    # 重み付きランダム選択
    numbers = list(range(number_min, number_max+1))
    weights = [freq.get(n, 1) for n in numbers]
    predictions = []
    for _ in range(5):
        pick = random.choices(numbers, weights=weights, k=pick_count)
        pick = sorted(set(pick))
        while len(pick) < pick_count:
            # 重複なし
            pick.append(random.choice([n for n in numbers if n not in pick]))
            pick = sorted(pick)
        predictions.append(pick)
    # LINE通知
    msg = f"{lottery_type.upper()}予想\n" + '\n'.join([str(p) for p in predictions])
    line_client.notify(msg)
    # prediction_runs保存
    run = PredictionRun(
        lottery_type=lottery_type,
        draw_number=rows[0]['draw_number'] if rows else 0,
        predictions=[Prediction(lottery_type, rows[0]['draw_number'] if rows else 0, p, datetime.now().isoformat()) for p in predictions],
        created_at=datetime.now().isoformat()
    )
    bq_client.insert_prediction_run('prediction_runs', run.__dict__)
    return {'predictions': predictions}
