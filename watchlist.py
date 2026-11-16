#!/usr/bin/env python3
"""Stock watchlist manager. Data is stored in watchlist.json.

Usage:
  python watchlist.py add CODE NAME [-m MEMO]
  python watchlist.py list [-s KEYWORD]
  python watchlist.py show CODE
  python watchlist.py update CODE [-n NAME] [-m MEMO]
  python watchlist.py remove CODE
"""
import argparse
import json
import os
import sys
import tempfile

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")


def load():
    if not os.path.exists(FILE):
        return []
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        sys.exit(f"Error: {FILE} is not valid JSON")


def save(items):
    # atomic write so a crash can't corrupt the file
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(FILE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FILE)


def find(items, code):
    code = code.upper()
    return next((s for s in items if s["code"] == code), None)


def update(items, code, name=None, memo=None):
    """Update name/memo of a stock in-place. Returns the updated item, or None
    if the code is not found (callers decide how to signal it)."""
    s = find(items, code)
    if not s:
        return None
    if name is not None:
        s["name"] = name
    if memo is not None:
        s["memo"] = memo
    return s


def cmd_add(a):
    items = load()
    if find(items, a.code):
        sys.exit(f"{a.code.upper()} already in watchlist (use update)")
    items.append({"code": a.code.upper(), "name": a.name, "memo": a.memo})
    save(items)
    print(f"Added {a.code.upper()} - {a.name}")


def cmd_list(a):
    items = load()
    if a.search:
        k = a.search.lower()
        items = [s for s in items if any(k in s[f].lower() for f in ("code", "name", "memo"))]
    if not items:
        print("(empty)")
        return
    w = max(len(s["code"]) for s in items)
    n = max(len(s["name"]) for s in items)
    print(f"{'CODE':<{w}}  {'NAME':<{n}}  MEMO")
    for s in sorted(items, key=lambda s: s["code"]):
        print(f"{s['code']:<{w}}  {s['name']:<{n}}  {s['memo']}")


def cmd_show(a):
    s = find(load(), a.code)
    if not s:
        sys.exit(f"{a.code.upper()} not found")
    print(f"Code: {s['code']}\nName: {s['name']}\nMemo: {s['memo']}")


def cmd_update(a):
    items = load()
    s = find(items, a.code)
    if not s:
        sys.exit(f"{a.code.upper()} not found")
    if a.name is None and a.memo is None:
        sys.exit("Nothing to update: pass -n and/or -m")
    if a.name is not None:
        s["name"] = a.name
    if a.memo is not None:
        s["memo"] = a.memo
    save(items)
    print(f"Updated {s['code']}")


def cmd_remove(a):
    items = load()
    s = find(items, a.code)
    if not s:
        sys.exit(f"{a.code.upper()} not found")
    items.remove(s)
    save(items)
    print(f"Removed {s['code']}")


def main():
    p = argparse.ArgumentParser(description="Stock watchlist manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add"); s.add_argument("code"); s.add_argument("name")
    s.add_argument("-m", "--memo", default=""); s.set_defaults(f=cmd_add)

    s = sub.add_parser("list"); s.add_argument("-s", "--search"); s.set_defaults(f=cmd_list)

    s = sub.add_parser("show"); s.add_argument("code"); s.set_defaults(f=cmd_show)

    s = sub.add_parser("update"); s.add_argument("code")
    s.add_argument("-n", "--name"); s.add_argument("-m", "--memo"); s.set_defaults(f=cmd_update)

    s = sub.add_parser("remove"); s.add_argument("code"); s.set_defaults(f=cmd_remove)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()

