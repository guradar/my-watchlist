#!/usr/bin/env python3
"""Chart settings store. Data is stored in chart_settings.json.

Global chart parameters, shared by the candlestick / renko / zxc charts:
    interval   yfinance interval (K-line granularity), e.g. "1d", "1h", "1m"
    period     yfinance period (lookback), e.g. "6mo", "5d"
    atr_period renko brick size ATR length (block_size = ATR(atr_period))
    n          ZXC formula WMA period (ZXC := WMA((2*C+H+L)/4, N))

Defaults: interval="1d", period="6mo", atr_period=14, n=10.
"""
import json
import os
import tempfile

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart_settings.json")

DEFAULTS = {
    "interval": "1d",
    "period": "6mo",
    "atr_period": 14,
    "n": 10,
}

VALID_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk"]
VALID_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd"]


def _clean_int(v, default, lo=1, hi=999):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def sanitize(d):
    """Validate a raw settings dict (may be partial/invalid); fill defaults."""
    if not isinstance(d, dict):
        d = {}
    return {
        "interval": d.get("interval") if d.get("interval") in VALID_INTERVALS
                   else DEFAULTS["interval"],
        "period": d.get("period") if d.get("period") in VALID_PERIODS
                  else DEFAULTS["period"],
        "atr_period": _clean_int(d.get("atr_period"), DEFAULTS["atr_period"]),
        "n": _clean_int(d.get("n"), DEFAULTS["n"]),
    }


def load():
    if not os.path.exists(FILE):
        return dict(DEFAULTS)
    try:
        with open(FILE, encoding="utf-8") as f:
            return sanitize(json.load(f))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(d):
    # atomic write so a crash can't corrupt the file
    s = sanitize(d)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(FILE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FILE)
    return s
