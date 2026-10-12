"""Checks the translations: every tr()/trn() text must exist in ytmd/locales/<lang>.py, and vice versa.

    python tools/check_i18n.py          # check all languages
    python tools/check_i18n.py --keys   # print every translatable text (to start a new language)
"""
from __future__ import annotations

import ast
import importlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _strings(node) -> list[str]:
    """The literal text(s) of an argument: plain, concatenated (a + b) or conditional (a if c else b)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _strings(node.left), _strings(node.right)
        return [a + b for a in left for b in right] if left and right else []
    if isinstance(node, ast.IfExp):
        return _strings(node.body) + _strings(node.orelse)
    return []


def collect() -> dict[str, list[str]]:
    """text -> places where it is used"""
    found: dict[str, list[str]] = {}
    pkg = os.path.join(ROOT, "ytmd")
    files = [os.path.relpath(os.path.join(d, f), ROOT) for d, _s, fs in os.walk(pkg) for f in fs
             if f.endswith(".py") and "locales" not in d and f != "i18n.py"]
    for rel in sorted(files):
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id == "tr" and node.args:
                args = node.args[:1]
            elif node.func.id == "trn" and len(node.args) >= 3:
                args = node.args[1:3]
            else:
                continue
            for a in args:
                texts = _strings(a)
                if not texts:
                    found.setdefault("<NOT A LITERAL>", []).append(f"{rel}:{node.lineno}")
                for t in texts:
                    found.setdefault(t, []).append(f"{rel}:{node.lineno}")
    return found


def placeholders(s: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", s))


def main() -> int:
    keys = collect()
    if "--keys" in sys.argv:
        for k in sorted(keys):
            print(repr(k))
        return 0
    bad = 0
    if "<NOT A LITERAL>" in keys:
        print("tr() with a non-literal text (can't be translated):", keys.pop("<NOT A LITERAL>"))
        bad += 1
    from ytmd.i18n import LANGUAGES
    for code in LANGUAGES:
        if code == "en":
            continue
        texts = importlib.import_module(f"ytmd.locales.{code}").TEXTS
        missing = sorted(set(keys) - set(texts))
        unused = sorted(set(texts) - set(keys))
        wrong = [k for k in keys if k in texts and placeholders(k) != placeholders(texts[k])]
        print(f"[{code}] {len(keys)} texts, {len(texts)} translations")
        for k in missing:
            print("  missing :", repr(k), keys[k][:2])
        for k in unused:
            print("  unused  :", repr(k))
        for k in wrong:
            print("  {placeholders} differ:", repr(k), "->", repr(texts[k]))
        bad += len(missing) + len(unused) + len(wrong)
    print("OK" if not bad else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
