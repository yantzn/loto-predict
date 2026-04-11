
# シンプルなバッチエントリポイント
import argparse
def main():
    parser = argparse.ArgumentParser(description="Backfill Rakuten loto history")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    from src.usecases.data_sync_usecase import import_loto_csv_to_bq
    import_loto_csv_to_bq(args.bucket, args.name)

if __name__ == "__main__":
    main()
