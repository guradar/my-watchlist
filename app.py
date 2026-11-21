#!/usr/bin/env python3
"""Watchlist web site. Run: .venv/bin/python app.py  (serves on :8080)"""
import io

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
import os
import yfinance as yf

import chart_settings as cfg
import watchlist as wl
from chart import plot, plot_renko, plot_zxc

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    # browser default favicon path (browsers request /favicon.ico at the root)
    return send_from_directory(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
        "favicon.ico")


# ---------------- chart settings ----------------

@app.get("/settings")
def settings_page():
    return render_template("settings.html",
                           settings=cfg.load(),
                           intervals=cfg.VALID_INTERVALS,
                           periods=cfg.VALID_PERIODS,
                           defaults=cfg.DEFAULTS)


@app.get("/api/settings")
def get_settings():
    return jsonify(cfg.load())


@app.post("/api/settings")
def save_settings():
    # merge over current settings so partial updates (e.g. the daily/30min
    # quick buttons on the home page, which only send interval+period)
    # keep the existing atr_period/n
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(cfg.save({**cfg.load(), **d}))


# ---------------- helpers ----------------

def _fetch(code, st):
    return yf.Ticker(code).history(period=st["period"], interval=st["interval"],
                                   auto_adjust=False)


def _png(buf):
    buf.seek(0)
    resp = send_file(buf, mimetype="image/png")
    # settings (interval/period/atr_period/n) can change at any time;
    # the browser must never serve a stale chart from cache
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------- chart images ----------------

@app.get("/api/chart/<code>.png")
def chart(code):
    s = wl.find(wl.load(), code)
    st = cfg.load()
    try:
        df = _fetch(code, st)
        if df.empty:
            raise ValueError("no data")
        buf = io.BytesIO()
        plot(code.upper(), s["name"] if s else code, df, buf,
             interval=st["interval"])
    except Exception as e:
        return jsonify(error=str(e)), 404
    return _png(buf)


@app.get("/api/renko/<code>.png")
def renko(code):
    s = wl.find(wl.load(), code)
    st = cfg.load()
    try:
        df = _fetch(code, st)
        if df.empty:
            raise ValueError("no data")
        buf = io.BytesIO()
        plot_renko(code.upper(), s["name"] if s else code, df, buf,
                   atr_period=st["atr_period"], interval=st["interval"])
    except Exception as e:
        return jsonify(error=str(e)), 404
    return _png(buf)


@app.get("/api/zxc/<code>.png")
def zxc(code):
    s = wl.find(wl.load(), code)
    st = cfg.load()
    try:
        df = _fetch(code, st)
        if df.empty:
            raise ValueError("no data")
        buf = io.BytesIO()
        plot_zxc(code.upper(), s["name"] if s else code, df, buf,
                 n=st["n"], interval=st["interval"])
    except Exception as e:
        return jsonify(error=str(e)), 404
    return _png(buf)


# ---------------- watchlist ----------------

@app.get("/api/stocks")
def list_stocks():
    return jsonify(wl.load())


@app.post("/api/stocks")
def add_stock():
    d = request.get_json(force=True)
    code = (d.get("code") or "").strip().upper()
    name = (d.get("name") or "").strip()
    if not code:
        return jsonify(error="Code is required"), 400
    items = wl.load()
    if wl.find(items, code):
        return jsonify(error=f"{code} already exists"), 409
    if not name:  # try to look the name up
        try:
            info = yf.Ticker(code).info
            name = info.get("shortName") or info.get("longName") or ""
        except Exception:
            pass
    items.append({"code": code, "name": name or code, "memo": (d.get("memo") or "").strip()})
    wl.save(items)
    return jsonify(items[-1]), 201


@app.delete("/api/stocks/<code>")
def delete_stock(code):
    items = wl.load()
    s = wl.find(items, code)
    if not s:
        return jsonify(error="not found"), 404
    items.remove(s)
    wl.save(items)
    return jsonify(ok=True)


@app.patch("/api/stocks/<code>")
@app.put("/api/stocks/<code>")
def update_stock(code):
    d = request.get_json(force=True, silent=True) or {}
    items = wl.load()
    s = wl.update(items, code, name=d.get("name"), memo=d.get("memo"))
    if not s:
        return jsonify(error="not found"), 404
    if d.get("name") is None and d.get("memo") is None:
        return jsonify(error="nothing to update: send name and/or memo"), 400
    wl.save(items)
    return jsonify(s)


@app.get("/api/price/<code>")
def price(code):
    try:
        h = yf.Ticker(code).history(period="5d", auto_adjust=False)["Close"].dropna()
        if h.empty:
            raise ValueError("no data")
        last = float(h.iloc[-1])
        prev = float(h.iloc[-2]) if len(h) > 1 else last
        if code[7:] in ['SS','SZ','ss','sz'] and code[:2] in ['51','15','16','50','52','53','55','56','58']:
            return jsonify(price=round(last, 3), change=round((last / prev - 1) * 100, 2))
        else:
            return jsonify(price=round(last, 2), change=round((last / prev - 1) * 100, 2))
    except Exception as e:
        return jsonify(error=str(e)), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
