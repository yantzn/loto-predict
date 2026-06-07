"""Summarize and compare backtest JSONL files.

大きなticket単位JSONLから等級別件数や一致数を抽出し、baselineとの差分を確認するための補助ツールです。
"""

import json
from pathlib import Path

def summarize_backtest_jsonl(path: str | Path) -> dict:
    """
    バックテストのJSONLファイルを読み込み、全体の統計とプロファイル別の統計を集計する。
    """
    total_runs = 0
    total_tickets = 0
    overall_prizes = {}
    profile_prizes = {}

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            
            row = json.loads(line)
            total_runs += 1
            
            tickets = row.get("tickets", [])
            total_tickets += len(tickets)
            
            for ticket in tickets:
                prize = ticket.get("prize", "該当なし")
                profile_name = ticket.get("profile_name", "unknown")
                
                # Overall stats
                overall_prizes[prize] = overall_prizes.get(prize, 0) + 1
                
                # Profile stats
                if profile_name not in profile_prizes:
                    profile_prizes[profile_name] = {}
                profile_prizes[profile_name][prize] = profile_prizes[profile_name].get(prize, 0) + 1

    return {
        "total_runs": total_runs,
        "total_tickets": total_tickets,
        "overall_prizes": overall_prizes,
        "profile_prizes": profile_prizes,
    }


def compare_summary(actual: dict, expected: dict) -> list[str]:
    """
    実際の集計結果と期待される集計結果を比較し、差異をリストで返す。
    """
    diffs = []
    
    if actual.get("total_runs") != expected.get("total_runs"):
        diffs.append(f"total_runs: expected {expected.get('total_runs')}, actual {actual.get('total_runs')}")
        
    if actual.get("total_tickets") != expected.get("total_tickets"):
        diffs.append(f"total_tickets: expected {expected.get('total_tickets')}, actual {actual.get('total_tickets')}")
        
    for prize, count in expected.get("overall_prizes", {}).items():
        actual_count = actual.get("overall_prizes", {}).get(prize, 0)
        if actual_count != count:
            diffs.append(f"overall_prizes[{prize}]: expected {count}, actual {actual_count}")
            
    for profile, expected_prizes in expected.get("profile_prizes", {}).items():
        for prize, count in expected_prizes.items():
            actual_count = actual.get("profile_prizes", {}).get(profile, {}).get(prize, 0)
            if actual_count != count:
                diffs.append(f"profile_prizes[{profile}][{prize}]: expected {count}, actual {actual_count}")
                
    return diffs

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        summary = summarize_backtest_jsonl(sys.argv[1])
        print(json.dumps(summary, indent=2, ensure_ascii=False))
