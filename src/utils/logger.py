import logging

def get_logger():
    """
    標準出力向けのロガーを生成・取得する。
    - 既存ハンドラがなければStreamHandlerを追加
    - ログフォーマット: [日時] レベル メッセージ
    Returns:
        logging.Logger: 共通ロガー
    """
    logger = logging.getLogger('loto_predict')
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
