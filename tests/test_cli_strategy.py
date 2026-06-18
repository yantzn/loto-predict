"""CLI strategy registration tests.

backtest CLIの--strategy choicesに主要な比較strategyが表示されることを確認します。
"""

import subprocess
import sys

import pytest

def test_cli_exposes_mixed_variants():
    # Run the main CLI with --help to capture the choices
    result = subprocess.run(
        [sys.executable, "jobs/backtest_loto_prediction/main.py", "--help"],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0
    help_text = result.stdout
    
    # Ensure the choices are listed
    assert "mixed_loto6" in help_text
    assert "mixed_v2" in help_text
    assert "mixed_v3" in help_text
    assert "high_tier_v1" in help_text
    assert "triple_weighted" in help_text
    
    # Ensure invalid choice is rejected
    result_invalid = subprocess.run(
        [sys.executable, "jobs/backtest_loto_prediction/main.py", "--lottery-type", "loto7", "--strategy", "invalid"],
        capture_output=True,
        text=True,
    )
    assert result_invalid.returncode != 0
    assert "invalid choice" in result_invalid.stderr
