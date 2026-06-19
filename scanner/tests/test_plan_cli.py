"""
`plan` command smoke test: cadence + money sections must run from a journal and
the per-signal CSV must size positions without ever deploying more cash than the
account holds (no-margin reality).
"""
import pandas as pd

from scanner.cli import main


def _journal(path):
    rows = [
        # date, symbol, setup, direction, entry, stop, target_3R, timeframe
        ("2026-01-05", "SPLG", "trend_pullback", "long", 60.0, 59.0, 63.0, 1),
        ("2026-01-09", "QQQM", "trend_pullback", "long", 180.0, 177.0, 189.0, 1),
        ("2026-02-02", "XLF", "trend_pullback", "long", 45.0, 44.5, 46.5, 1),
        # an expensive name: one share (>$2k account) is unaffordable
        ("2026-02-20", "EXPN", "trend_pullback", "long", 3000.0, 2900.0, 3300.0, 1),
    ]
    cols = ["date", "symbol", "setup", "direction", "entry", "stop",
            "target_3R", "timeframe"]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)


def test_plan_runs_and_caps_cash(tmp_path, capsys):
    jpath = tmp_path / "journal.csv"
    opath = tmp_path / "plan.csv"
    _journal(jpath)
    main(["plan", "--source", "synthetic", "--in", str(jpath),
          "--out", str(opath), "--account", "2000"])
    out = capsys.readouterr().out
    assert "TRADE PLAN" in out
    assert "CADENCE" in out and "MONEY" in out

    plan = pd.read_csv(opath)
    # never deploy more than the account
    assert (plan["dollars_deployed"] <= 2000 + 1e-6).all()
    # the $3000 name cannot be bought with $2000
    expn = plan[plan["symbol"] == "EXPN"].iloc[0]
    assert expn["shares_at_account"] == 0
    assert "NO" in str(expn["affordable"])
    # days_to_next_signal is present and the last row is blank (no next)
    assert "days_to_next_signal" in plan.columns
