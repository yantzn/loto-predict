import json
import os
import time
import subprocess

# =============================================
# Terraform Infraワークフローの競合防止スクリプト
# 他の同名ワークフローが同一ブランチで動作中の場合、完了まで待機する
# ---------------------------------------------
# 利用環境変数:
#   REPO: 対象GitHubリポジトリ (例: yantzn/loto-predict)
#   BRANCH: 対象ブランチ名
#   CURRENT_RUN_ID: 現在のGitHub Actions Run ID
#   GH_TOKEN: GitHub APIトークン (gh cli用)
#
# gh cliが必要です（https://cli.github.com/）
# =============================================
import json

def get_blocking_count(repo, branch, current_run_id, gh_token):
    """
    指定リポジトリ・ブランチで同時に走っているTerraform Infraワークフロー数を取得
    - gh cliでActions APIを叩く
    - 現在のrun_idは除外
    - queued/in_progress/pending/waiting/requestedのみカウント

    Args:
        repo (str): "owner/repo" 形式のリポジトリ名
        branch (str): ブランチ名
        current_run_id (str): 現在のGitHub Actions Run ID
        gh_token (str): GitHubトークン
    Returns:
        int: ブロック中のワークフロー数（API失敗時は-1）
    """
    # gh cliでActionsのワークフロー一覧を取得
    result = subprocess.run([
        "gh", "api",
        "-H", "Accept: application/vnd.github+json",
        f"/repos/{repo}/actions/runs?branch={branch}&per_page=100"
    ], capture_output=True, text=True, env={**os.environ, "GH_TOKEN": gh_token})
    if result.returncode != 0 or not result.stdout:
        print("Failed to call gh api:", result.stderr)
        return -1
    try:
        data = json.loads(result.stdout)
    except Exception as e:
        print("Failed to parse gh api response:", e)
        return -1
    count = 0
    # ワークフロー一覧から、同名・同ブランチ・未完了のものをカウント
    for run in data.get("workflow_runs", []):
        if str(run.get("id")) == current_run_id:
            continue  # 自分自身は除外
        if run.get("name") != "Terraform Infra":
            continue
        if run.get("head_branch") != branch:
            continue
        status = run.get("status")
        if status in {"queued", "in_progress", "pending", "waiting", "requested"}:
            count += 1
    return count

def main():
    """
    他のTerraform Infraワークフローが終わるまで待機する
    - CI/CDの競合防止用
    """
    # 必須環境変数の取得
    try:
        repo = os.environ["REPO"]  # "owner/repo" 形式
        branch = os.environ["BRANCH"]
        current_run_id = str(os.environ["CURRENT_RUN_ID"])
        gh_token = os.environ["GH_TOKEN"]
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
        exit(1)

    max_wait = 60  # 最大60回(=15分)待機
    for i in range(max_wait):
        blocking_count = get_blocking_count(repo, branch, current_run_id, gh_token)
        if blocking_count == 0:
            print("No running Terraform Infra workflow found.")
            break  # 他に動作中のワークフローなし
        if blocking_count < 0:
            print("API error. Exiting.")
            break  # APIエラー
        print(f"Terraform Infra is still running ({blocking_count} run(s)). Sleep 15s...")
        time.sleep(15)  # 15秒待機して再チェック
    else:
        print("Timeout waiting for Terraform Infra workflow.")
        # 15分経過しても終わらなければタイムアウト


# スクリプトのエントリーポイント
if __name__ == "__main__":
    main()
