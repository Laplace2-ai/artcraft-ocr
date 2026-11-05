# SPDX-License-Identifier: Apache-2.0
"""Simplified ↔ traditional character conversion.

Table-driven, one character at a time, first candidate only. The data is OpenCC's
``STCharacters`` / ``TSCharacters``, shipped in ``CORE/data``.

Two decisions worth knowing:

* **First candidate wins.** The tables list several traditional forms per
  simplified character (``发`` → 發 / 髮). Choosing by context needs a word
  dictionary and a POS model; V1 takes the first entry, which is right more often
  than it is wrong and never produces something that is not a real character.
* **Characters only, no regional vocabulary.** 软件 / 軟體 is a wording change, not
  a script change, and rewriting a user's words is outside what this feature
  claims to do.

Deliberately not the Unicode Unihan variant table: it maps ``台`` to 台/檯/臺/颱 and
taking the first entry there leaves the character unchanged, which looks like the
conversion silently failed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("data")
TABLES = {"s2t": "STCharacters.txt", "t2s": "TSCharacters.txt"}


@lru_cache(maxsize=2)
def _table(direction: str) -> dict[str, str]:
    try:
        name = TABLES[direction]
    except KeyError as exc:
        raise ValueError(f"direction must be s2t or t2s, not {direction!r}") from exc

    path = DATA / name
    if not path.exists():
        raise FileNotFoundError(
            f"conversion table missing: {path}. It ships with the project; a build that "
            "dropped it cannot convert."
        )

    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            key, _, candidates = line.rstrip("\n").partition("\t")
            if not candidates:
                continue
            mapping[key] = candidates.split(" ")[0].strip()
    return mapping


def convert(text: str, direction: str = "s2t") -> tuple[str, int]:
    """Convert ``text``; returns the result and how many characters changed."""
    mapping = _table(direction)
    changed = 0
    out: list[str] = []
    for ch in text:
        target = mapping.get(ch)
        if target is not None and target != ch:
            changed += 1
            out.append(target)
        else:
            out.append(ch)
    return "".join(out), changed
