"""CLI strategy registration tests.

backtest CLIの--strategy choicesにmixed/mixed_v2/mixed_v3/triple_weightedが表示されることを確認します。
"""

import subprocess
import pytest

def test_cli_exposes_mixed_variants():
    # Run the main CLI with --help to capture the choices
    result = subprocess.run(
        ["python", "jobs/backtest_loto_prediction/main.py", "--help"],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0
    help_text = result.stdout
    
    # Ensure the choices are listed
    assert "{mixed,mixed_v2,mixed_v3,triple_weighted}" in help_text or "mixed, mixed_v2, mixed_v3, triple_weighted" in help_text
    
    # Ensure invalid choice is rejected
    result_invalid = subprocess.run(
        ["python", "jobs/backtest_loto_prediction/main.py", "--lottery-type", "loto7", "--strategy", "invalid"],
        capture_output=True,
        text=True,
    )
    assert result_invalid.returncode != 0
    assert "invalid choice" in result_invalid.stderr
