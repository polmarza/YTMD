"""Translations. The English text in the code is the key; other languages live in ytmd/locales/<code>.py.

    tr("Add to queue")                     -> "Añadir a la cola" (when the language is Spanish)
    tr("Hello {name}", name="Pol")         -> formatted after translating
    trn(n, "{n} song", "{n} songs")        -> picks the singular/plural form, then translates it

The language is chosen once at start-up (Settings > Language relaunches the app), so strings can be
translated where they are built. A missing translation falls back to English.
"""
from __future__ import annotations

import importlib

LANGUAGES = {"en": "English", "es": "Español"}
DEFAULT = "en"

_table: dict[str, str] = {}
_lang = DEFAULT


def set_language(code: str) -> str:
    """Select the language; unknown codes fall back to English. Returns the one in use."""
    global _table, _lang
    _lang = code if code in LANGUAGES else DEFAULT
    _table = {} if _lang == DEFAULT else importlib.import_module(f"ytmd.locales.{_lang}").TEXTS
    return _lang


def language() -> str:
    return _lang


def tr(text: str, *args, **kwargs) -> str:
    s = _table.get(text, text)
    return s.format(*args, **kwargs) if (args or kwargs) else s


def trn(n: int, one: str, other: str, **kwargs) -> str:
    """Singular/plural: `n` is also available to the text as {n}."""
    return tr(one if n == 1 else other, n=n, **kwargs)
