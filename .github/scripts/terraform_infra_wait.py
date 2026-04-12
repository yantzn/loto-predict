import json
import os
import sys
import time
import subprocess

def get_blocking_count(repo, branch, current_run_id, gh_token):
    # gh apiコマンドでworkflow_runsを取得
    result = subprocess.run([
        "gh", "api",
        "-H", "Accept: application/vnd.github+json",
        f"/repos/{repo}/actions/runs?branch={branch}&per_page=100"
    ], capture_output=True, text=True, env={**os.environ, "GH_TOKEN": gh_token})
    data = json.loads(result.stdout)
    count = 0
    for run in data.get("workflow_runs", []):
        if str(run.get("id")) == current_run_id:
            continue
        if run.get("name") != "Terraform Infra":
            continue
        if run.get("head_branch") != branch:
            continue
        status = run.get("status")
        if status in {"queued", "in_progress", "pending", "waiting", "requested"}:
            count += 1
    return count

def main():
    repo = os.environ["REPO"]
    branch = os.environ["BRANCH"]
    current_run_id = str(os.environ["CURRENT_RUN_ID"])
    gh_token = os.environ["GH_TOKEN"]
    while True:
        blocking_count = get_blocking_count(repo, branch, current_run_id, gh_token)
        if blocking_count == 0:
            print("No running Terraform Infra workflow found.")
            break
        print(f"Terraform Infra is still running ({blocking_count} run(s)). Sleep 15s...")
        time.sleep(15)

if __name__ == "__main__":
    main()
