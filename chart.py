#!/usr/bin/env python3
"""Plot candlestick charts (with MA5/MA20) for every stock in watchlist.json.

Usage: python chart.py [-p PERIOD] [-i INTERVAL] [-o OUTDIR]
                       [--renko | --zxc] [--n N] [--atr-period A]
Output: <OUTDIR>/<CODE>.png          (candlesticks)
        <OUTDIR>/<CODE>_renko.png    (--renko, brick size = ATR(atr_period, 默认 14))
        <OUTDIR>/<CODE>_zxc.png      (--zxc, 通达信 ZXC 副图, 参数 N 默认 10)
"""
import argparse
import json
import os
import sys
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import mplfinance as mpf
import numpy as np
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))

INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "1h", "2h", "4h", "90m"}

def has_chinese(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s))

def xfmt(interval):
    """Date tick label format: intraday intervals show time as well."""
    return "%m-%d %H:%M" if interval in INTRADAY_INTERVALS else "%Y-%m-%d"


def plot(code, name, df, path, interval="1d"):
    df = df.copy()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, (_, r) in enumerate(df.iterrows()):
        up = r["Close"] >= r["Open"]
        color = "#26a69a" if up else "#ef5350"
        ax.plot([i, i], [r["Low"], r["High"]], color=color, lw=1)
        ax.add_patch(Rectangle((i - 0.3, min(r["Open"], r["Close"])), 0.6,
                               max(abs(r["Close"] - r["Open"]), 1e-9),
                               facecolor=color, edgecolor=color))
    x = range(len(df))
    ax.plot(x, df["MA5"], color="orange", lw=1.2, label="MA5")
    ax.plot(x, df["MA20"], color="royalblue", lw=1.2, label="MA20")
    step = max(len(df) // 10, 1)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels([d.strftime(xfmt(interval)) for d in df.index[::step]], rotation=30)
    ax.set_xlim(-1, len(df))
    if has_chinese(name):
        name="A Market"
    ax.set_title(f"{code} - {name} (interval={interval})")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=120, format="png")
    plt.close(fig)


UP, DOWN = "#26a69a", "#ef5350"  # same up/down palette as plot()


def plot_renko(code, name, df, path, atr_period=14, interval="1d"):
    """Plot a renko (brick) chart with mplfinance's built-in renko support.

    brick_size='atr' with atr_length=14 makes the brick size ATR(14), as
    requested by the readme (reference: attached yahoo.py):
        mpf.plot(data, type='renko',
                 renko_params={'brick_size': 'atr', 'atr_length': 14})
    """
    data = df[["Open", "High", "Low", "Close"]].copy()
    if "Volume" in df.columns:
        data["Volume"] = df["Volume"]
    marketcolors = mpf.make_marketcolors(
        up=UP, down=DOWN,
        edge={"up": UP, "down": DOWN},
        wick={"up": UP, "down": DOWN},
        volume={"up": UP, "down": DOWN},
    )
    if has_chinese(name):
        name="A Market"
    mpf.plot(
        data,
        type="renko",        
        renko_params={"brick_size": "atr", "atr_length": atr_period},
        title=f"{code} - {name} (Renko, block_size=ATR({atr_period}), interval={interval})",
        figsize=(12, 6),
        style=mpf.make_mpf_style(
            base_mpl_style="default",
            marketcolors=marketcolors,
            facecolor="white",
            gridcolor="#cccccc",
        ),
        savefig=dict(fname=path, dpi=120, format="png"),
    )


def wma(s, n):
    """通达信 WMA(X,N)：线性加权移动平均，权重 1..N（旧->新，最新权重 N）。"""
    w = np.arange(1, n + 1, dtype=float)
    wsum = w.sum()
    return s.rolling(n).apply(lambda x: np.dot(x, w) / wsum, raw=True)


def compute_zxc(df, n):
    """ZXC := WMA((2*C+H+L)/4, N)"""
    price_rep = (2 * df["Close"] + df["High"] + df["Low"]) / 4
    return wma(price_rep, n)


def plot_zxc(code, name, df, path, n=10, interval="1d"):
    """通达信 ZXC 副图（只实现 ZXC 子图部分）：
        ZXC := WMA((2*C+H+L)/4, N);
        ZXO := REF(ZXC, 1);
        STICKLINE(ZXO>ZXC, ZXC, ZXO, 4, 1), COLORGREEN;
        STICKLINE(ZXO<ZXC, ZXC, ZXO, 4, 1), COLORRED;
    红柱: 今值>昨值 (ZXO<ZXC, 上升); 绿柱: 今值<昨值 (ZXO>ZXC, 下降)。
    """
    zxc = compute_zxc(df, n)
    zxo = zxc.shift(1)  # REF(ZXC, 1)
    valid = (~zxc.isna()) & (~zxo.isna())
    if int(valid.sum()) < 2:
        raise ValueError(f"not enough data for ZXC (need >= {n + 1} bars)")
    zxc_v = zxc.to_numpy()[valid.to_numpy()]
    zxo_v = zxo.to_numpy()[valid.to_numpy()]
    x_v = np.arange(len(df))[valid.to_numpy()]

    stick = np.abs(zxc_v - zxo_v)
    stick_bot = np.minimum(zxc_v, zxo_v)
    flat = stick < 1e-9
    up_bar = (zxc_v > zxo_v) & ~flat   # ZXO < ZXC -> COLORRED
    dn_bar = (zxc_v < zxo_v) & ~flat   # ZXO > ZXC -> COLORGREEN

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x_v[up_bar], stick[up_bar], bottom=stick_bot[up_bar],
           width=0.92, color="red", edgecolor="none")
    ax.bar(x_v[dn_bar], stick[dn_bar], bottom=stick_bot[dn_bar],
           width=0.92, color="green", edgecolor="none")
    if flat.any():  # 平值画短横线
        ax.hlines(stick_bot[flat], x_v[flat] - 0.4, x_v[flat] + 0.4,
                  color="gray", linewidth=0.8)

    lo, hi = float(stick_bot.min()), float(stick_bot.max()) + float(stick.max())
    pad = (hi - lo) * 0.06 + 1e-9
    ax.set_ylim(lo - pad, hi + pad)

    step = max(len(df) // 10, 1)
    ax.set_xticks(np.arange(len(df))[::step])
    ax.set_xticklabels([d.strftime(xfmt(interval)) for d in df.index[::step]], rotation=30)
    ax.set_xlim(-1, len(df))
    if has_chinese(name):
        name="A Market"
    ax.set_title(f"{code} - {name} (ZXC, N={n}, interval={interval})")
    ax.set_xlabel("Date")
    ax.set_ylabel("ZXC")
    ax.grid(alpha=0.3)
    ax.text(0.005, 0.02,
            "ZXC:=WMA((2*C+H+L)/4,N);  ZXO:=REF(ZXC,1);  "
            "red: ZXO<ZXC (up)   green: ZXO>ZXC (down)",
            transform=ax.transAxes, fontsize=9, color="dimgray")
    fig.tight_layout()
    fig.savefig(path, dpi=120, format="png")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--period", default="6mo", help="yfinance period (default 6mo)")
    p.add_argument("-i", "--interval", default="1d", help="yfinance interval (default 1d)")
    p.add_argument("-o", "--outdir", default=os.path.join(HERE, "charts"))
    p.add_argument("--renko", action="store_true",
                   help="plot renko charts (block size = ATR(14)) instead of candlesticks")
    p.add_argument("--zxc", action="store_true",
                   help="plot ZXC sub-panel charts (通达信 ZXC 公式) instead of candlesticks")
    p.add_argument("--n", type=int, default=10,
                   help="ZXC formula parameter N, WMA period (default 10)")
    p.add_argument("--atr-period", type=int, default=14,
                   help="Renko block_size ATR length, ATR(N) (default 14)")
    a = p.parse_args()
    if a.renko and a.zxc:
        p.error("--renko and --zxc are mutually exclusive")

    with open(os.path.join(HERE, "watchlist.json"), encoding="utf-8") as f:
        items = json.load(f)
    if not items:
        sys.exit("watchlist is empty")
    os.makedirs(a.outdir, exist_ok=True)

    for s in items:
        code = s["code"]
        try:
            df = yf.Ticker(code).history(period=a.period, interval=a.interval,
                                          auto_adjust=False)
            if df.empty:
                print(f"{code}: no data, skipped")
                continue
            if a.renko:
                fname, draw = f"{code}_renko.png", lambda: plot_renko(code, s["name"], df, path, atr_period=a.atr_period, interval=a.interval)
            elif a.zxc:
                fname, draw = f"{code}_zxc.png", lambda: plot_zxc(code, s["name"], df, path, n=a.n, interval=a.interval)
            else:
                fname, draw = f"{code}.png", lambda: plot(code, s["name"], df, path, interval=a.interval)
            path = os.path.join(a.outdir, fname)
            draw()
            print(f"{code}: saved {path}")
        except Exception as e:
            print(f"{code}: failed ({e})")


if __name__ == "__main__":
    main()

