#!/usr/bin/env python3
"""Normalize heading and ID-placement conventions across all CRA context packs.

Canonical format (Chapter I / VI style):

  - Chapter containers:  ``## CRA-CHAP-<roman> — CHAPTER <roman> — TITLE``
  - Article-level units: ``### CRA-ART-<n> — Article <n> — Title``
  - Paragraph-level units: ``### `CRA-ART-<n>-PARA-<p>``
  - Recital units: ``### `CRA-REC-<n>` ``
  - Annex container: ``## CRA-ANNEX-<roman> — ANNEX <roman>``
  - Annex part: ``### CRA-ANNEX-<roman>-PART-<roman> — Part <roman>``
  - Annex point: ``### CRA-ANNEX-<roman>-PT-<n>``

Rules:
  - ``##`` for chapter/annex containers, ``###`` for article/annex-part/point units.
  - Stable ID goes FIRST in the heading, separated by `` — `` (em dash, space-separated).
  - No backtick-wrapped bracketed IDs (`` `[CRA-ART-13]` ``) in headings.
  - No standalone ``**Stable ID:**`` or ``**`CRA-ART-N`**`` lines after headings.
  - Stable IDs themselves are never changed — only surrounding markup.
  - Legal wording is never changed.

Usage::

    python3 scripts/normalize_pack_headings.py          # apply in place
    python3 scripts/normalize_pack_headings.py --check   # exit 1 if changes needed
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files to process (all pack files, not README)
PACK_FILES = [
    REPO_ROOT / "recitals.md",
    *sorted((REPO_ROOT / "chapters").glob("chapter-*.md")),
    *sorted((REPO_ROOT / "annexes").glob("annex-*.md")),
]

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

ROMAN = r"[IVXLCDM]+"
ART_NUM = r"\d+"

# Chapter container heading patterns (## level)
# Matches: ## CHAPTER N — TITLE, ## CHAPTER N — TITLE `[CRA-CHAP-N]`,
#          ## CRA-CHAP-N — CHAPTER N — TITLE, ## CRA-CHAP-N — CHAPTER N: TITLE
RE_CHAP_PLAIN = re.compile(rf"^## CHAPTER ({ROMAN}) — (.+)$")
RE_CHAP_WITH_ID = re.compile(rf"^## CHAPTER ({ROMAN}) — (.+?)\s*`\[CRA-CHAP-{ROMAN}\]`\s*$")
RE_CHAP_ID_FIRST = re.compile(rf"^## (CRA-CHAP-({ROMAN})) — CHAPTER {ROMAN}[:—] (.+)$")

# Standalone chapter ID lines to remove
RE_CHAP_STANDALONE_BACKTICK = re.compile(rf"^`CRA-CHAP-{ROMAN}`\s*$")
RE_CHAP_STANDALONE_BOLD = re.compile(rf"^\*\*`CRA-CHAP-{ROMAN}`\*\*\s*$")
RE_CHAP_STABLE_ID = re.compile(rf"^\*\*Stable ID:\*\* `CRA-CHAP-{ROMAN}`\s*$")

# Article heading patterns
# ## Article N — Title `[CRA-ART-N]`  (ID last, backticked, bracketed)
RE_ART_ID_LAST = re.compile(rf"^## Article ({ART_NUM}) — (.+?)\s*`\[CRA-ART-{ART_NUM}\]`\s*$")
# ## Article N — Title  (no ID on heading)
RE_ART_NO_ID = re.compile(rf"^## Article ({ART_NUM}) — (.+)$")
# ### Article N — Title `[CRA-ART-N]`  (already ###, ID last)
RE_ART_ID_LAST_H3 = re.compile(rf"^### Article ({ART_NUM}) — (.+?)\s*`\[CRA-ART-{ART_NUM}\]`\s*$")
# ### CRA-ART-N — Article N: Title  (ID first, colon separator — chapter VI)
RE_ART_ID_FIRST_COLON = re.compile(rf"^### (CRA-ART-({ART_NUM})) — Article {ART_NUM}:\s*(.+)$")
# ### CRA-ART-N — Article N — Title  (already canonical)
RE_ART_CANONICAL = re.compile(rf"^### CRA-ART-{ART_NUM} — Article {ART_NUM} — .+$")

# Standalone article ID lines to remove
RE_ART_STANDALONE_BOLD = re.compile(rf"^\*\*`CRA-ART-{ART_NUM}`\*\*\s*$")
RE_ART_STABLE_ID = re.compile(rf"^\*\*Stable ID:\*\* `CRA-ART-{ART_NUM}`\s*$")

# Chapter VII paragraph headings: #### `[CRA-ART-N-PARA-P]` Paragraph P (...)
RE_PARA_HEADING_H4 = re.compile(
    r"^#### `\[CRA-ART-(\d+)-PARA-(\d+)\]` Paragraph \d+(.*)$"
)

# Chapter VIII paragraph headings: ### `CRA-ART-N-PARA-P` (already fine, but
# ensure no bracket form)
RE_PARA_HEADING_H3 = re.compile(rf"^### `CRA-ART-(\d+)-PARA-(\d+)`\s*$")

# Inline bold paragraph IDs (chapters I-VI) — standalone on their own line
# **CRA-ART-N-PARA-M**  or  **`CRA-ART-N-PARA-M`**
RE_PARA_BOLD_STANDALONE = re.compile(rf"^\*\*`?CRA-ART-(\d+)-PARA-(\d+)`?\*\*\s*$")
# Inline bold paragraph IDs with text on the same line
# **CRA-ART-N-PARA-M** text...  or  **`CRA-ART-N-PARA-M`** text...
RE_PARA_BOLD_INLINE = re.compile(rf"^\*\*`?CRA-ART-(\d+)-PARA-(\d+)`?\*\*\s+(.+)$")
# Continuation paragraphs: **CRA-ART-N-PARA-M (continuation, unlettered)** text...
RE_PARA_BOLD_CONTINUATION = re.compile(
    r"^\*\*`?(CRA-ART-\d+-PARA-\d+ \(continuation, unlettered\))`?\*\*\s+(.+)$"
)

# Sub-point IDs (always inline with legal text) — standardize to **`ID`** form
# **CRA-ART-N-PARA-M-PT-X** (a) text...  →  **`CRA-ART-N-PARA-M-PT-X`** (a) text...
RE_SUBPT_BOLD_NO_BT = re.compile(
    r"^\*\*(CRA-ART-\d+-PARA-\d+-PT-[A-Z0-9]+(?:-SUBPT-[A-Z0-9]+)?)\*\*\s+(.*)$"
)
# **`[CRA-ART-N-PARA-M-PT-X]`** (a) text...  →  **`CRA-ART-N-PARA-M-PT-X`** (a) text...
RE_SUBPT_BOLD_BT_BRACKET = re.compile(
    r"^\*\*`\[(CRA-ART-\d+-PARA-\d+-PT-[A-Z0-9]+(?:-SUBPT-[A-Z0-9]+)?)\]`\*\*\s+(.*)$"
)

# Recital headings: ### `CRA-REC-N` (already canonical after defect-2 cleanup)
RE_RECITAL_HEADING = re.compile(r"^### `CRA-REC-\d+`\s*$")

# ---------------------------------------------------------------------------
# Annex heading patterns
# ---------------------------------------------------------------------------

ANNEX_ROMAN = r"[IVXLCDM]+"

# Annex container headings — normalize to: ## CRA-ANNEX-<R> — ANNEX <R> — TITLE
# Matches: ## CRA-ANNEX-V — ANNEX V: EU DECLARATION OF CONFORMITY (colon)
RE_ANNEX_CONTAINER_COLON = re.compile(
    rf"^## (CRA-ANNEX-({ANNEX_ROMAN})) — ANNEX {ANNEX_ROMAN}:\s*(.+)$"
)
# Matches: ## CRA-ANNEX-V — ANNEX V — TITLE (already canonical with —)
RE_ANNEX_CONTAINER_DASH = re.compile(
    rf"^## CRA-ANNEX-{ANNEX_ROMAN} — ANNEX {ANNEX_ROMAN} — .+$"
)
# Matches: ## CRA-ANNEX-III — ANNEX III  (canonical without title — title may follow)
RE_ANNEX_CONTAINER_NO_TITLE = re.compile(
    rf"^## (CRA-ANNEX-({ANNEX_ROMAN})) — ANNEX {ANNEX_ROMAN}\s*$"
)
# Matches: ## CRA-ANNEX-II  (bare ID, no title)
RE_ANNEX_CONTAINER_BARE = re.compile(rf"^## (CRA-ANNEX-({ANNEX_ROMAN}))\s*$")
# Matches: ## `CRA-ANNEX-IV`  (backticked bare ID)
RE_ANNEX_CONTAINER_BACKTICK = re.compile(rf"^## `CRA-ANNEX-({ANNEX_ROMAN})`\s*$")
# Matches: ## ANNEX VIII  (no ID)
RE_ANNEX_CONTAINER_NO_ID = re.compile(rf"^## ANNEX ({ANNEX_ROMAN})\s*$")
# Matches: ### CRA-ANNEX-I — ANNEX I  (wrong depth, should be ##)
RE_ANNEX_CONTAINER_H3 = re.compile(
    rf"^### (CRA-ANNEX-({ANNEX_ROMAN})) — ANNEX {ANNEX_ROMAN}\s*$"
)
# Matches: ### CRA-ANNEX-VI — ANNEX VI: TITLE  (wrong depth, colon)
RE_ANNEX_CONTAINER_H3_COLON = re.compile(
    rf"^### (CRA-ANNEX-({ANNEX_ROMAN})) — ANNEX {ANNEX_ROMAN}:\s*(.+)$"
)

# Annex container with title on separate lines: ### ANNEX II / ### TITLE
# These need special handling — merge into one ## heading
RE_ANNEX_SUBTITLE = re.compile(rf"^### ANNEX ({ANNEX_ROMAN})\s*$")
RE_ANNEX_TITLE_LINE = re.compile(r"^### ([A-Z][A-Z\s]+)\s*$")
# Title at ## depth following annex container (annex III style)
RE_ANNEX_TITLE_H2 = re.compile(r"^## ([A-Z][A-Z\s]+)\s*$")

# Annex part headings — normalize to: ### CRA-ANNEX-<R>-PART-<R> — Part <R> ...
# Matches: ### `CRA-ANNEX-VIII-PART-I` — Part I ...
RE_ANNEX_PART_BACKTICK = re.compile(
    rf"^### `CRA-ANNEX-({ANNEX_ROMAN})-PART-({ANNEX_ROMAN})` — (.+)$"
)
# Matches: #### CRA-ANNEX-I-PART-I — Part I  (wrong depth)
RE_ANNEX_PART_H4 = re.compile(
    rf"^#### (CRA-ANNEX-({ANNEX_ROMAN})-PART-({ANNEX_ROMAN})) — (.+)$"
)
# Already canonical: ### CRA-ANNEX-<R>-PART-<R> — Part <R> ...
RE_ANNEX_PART_CANONICAL = re.compile(
    rf"^### CRA-ANNEX-{ANNEX_ROMAN}-PART-{ANNEX_ROMAN} — .+$"
)

# Annex point headings — normalize to: ### CRA-ANNEX-<R>-PT-<N>
# Matches: ### `CRA-ANNEX-IV-PT-1`  (backticked)
RE_ANNEX_PT_BACKTICK = re.compile(rf"^### `CRA-ANNEX-({ANNEX_ROMAN})-PT-(\d+)`\s*$")
# Matches: ### CRA-ANNEX-II-PT-1  (already canonical, no backticks)
RE_ANNEX_PT_CANONICAL = re.compile(rf"^### CRA-ANNEX-{ANNEX_ROMAN}-PT-\d+\s*$")
# Matches: #### CRA-ANNEX-VII-PT-1  (wrong depth, should be ###)
RE_ANNEX_PT_H4 = re.compile(rf"^#### CRA-ANNEX-({ANNEX_ROMAN})-PT-(\d+)\s*$")
# Matches: #### CRA-ANNEX-II-PT-8-SUBPT-A  (wrong depth for sub-point)
# Sub-points under annex points: keep at #### if under a ### point
RE_ANNEX_SUBPT_H4 = re.compile(rf"^#### CRA-ANNEX-{ANNEX_ROMAN}-PT-\d+-SUBPT-[A-Z]\s*$")
RE_ANNEX_SUBPT_H5 = re.compile(rf"^##### CRA-ANNEX-{ANNEX_ROMAN}-PT-\d+-SUBPT-[A-Z]\s*$")

# Standalone annex ID lines to remove
RE_ANNEX_STANDALONE_BACKTICK = re.compile(rf"^`CRA-ANNEX-{ANNEX_ROMAN}`\s*$")

# Inline annex point IDs (annex I, III, VIII style) — convert to headings
# Pattern: CRA-ANNEX-<R>[-PART-<R>][-CLASS-<R>]-PT-<n>[-SUBPT-<n|letter>][-PT-<letter>]
_ANNEX_PT_ID = rf"CRA-ANNEX-{ANNEX_ROMAN}(?:-PART-{ANNEX_ROMAN})?(?:-CLASS-[IVXLCDM]+)?-PT-\d+(?:-SUBPT-[A-Z0-9]+)?(?:-PT-[A-Z])?"
# `CRA-ANNEX-VIII-PART-I-PT-1`  (standalone backtick line)
RE_ANNEX_PT_INLINE_STANDALONE = re.compile(rf"^`({_ANNEX_PT_ID})`\s*$")
# `CRA-ANNEX-VIII-PART-I-PT-2` 2\. text...  (inline backtick with text)
# Exclude table rows (text starting with "|") — those are summary-table entries
RE_ANNEX_PT_INLINE_WITH_TEXT = re.compile(rf"^`({_ANNEX_PT_ID})`\s+([^|].+)$")
# **CRA-ANNEX-I-PART-I-PT-1**  (standalone bold line)
RE_ANNEX_PT_BOLD_STANDALONE = re.compile(rf"^\*\*({_ANNEX_PT_ID})\*\*\s*$")
# **CRA-ANNEX-I-PART-I-PT-1** text...  (bold with text — rare but handle it)
RE_ANNEX_PT_BOLD_WITH_TEXT = re.compile(rf"^\*\*({_ANNEX_PT_ID})\*\*\s+(.+)$")


# ---------------------------------------------------------------------------
# Normalization logic
# ---------------------------------------------------------------------------

def _normalize_chapter_heading(line: str) -> str | None:
    """Return normalized chapter heading or None if not a chapter heading."""
    # Already canonical: ## CRA-CHAP-N — CHAPTER N — TITLE
    m = RE_CHAP_ID_FIRST.match(line)
    if m:
        chap_id = m.group(1)
        title = m.group(3).strip()
        # Normalize colon to em-dash separator
        return f"## {chap_id} — CHAPTER {m.group(2)} — {title}"

    # ## CHAPTER N — TITLE `[CRA-CHAP-N]`
    m = RE_CHAP_WITH_ID.match(line)
    if m:
        roman = m.group(1)
        title = m.group(2).strip()
        return f"## CRA-CHAP-{roman} — CHAPTER {roman} — {title}"

    # ## CHAPTER N — TITLE  (no ID — need to add one, but we need the roman)
    m = RE_CHAP_PLAIN.match(line)
    if m:
        roman = m.group(1)
        title = m.group(2).strip()
        return f"## CRA-CHAP-{roman} — CHAPTER {roman} — {title}"

    return None


def _normalize_article_heading(line: str) -> str | None:
    """Return normalized article heading or None if not an article heading."""
    # Already canonical
    if RE_ART_CANONICAL.match(line):
        return line

    # ### CRA-ART-N — Article N: Title  (colon separator)
    m = RE_ART_ID_FIRST_COLON.match(line)
    if m:
        art_id = m.group(1)
        title = m.group(3).strip()
        return f"### {art_id} — Article {m.group(2)} — {title}"

    # ## Article N — Title `[CRA-ART-N]`  or  ### Article N — Title `[CRA-ART-N]`
    m = RE_ART_ID_LAST.match(line)
    if m:
        num = m.group(1)
        title = m.group(2).strip()
        return f"### CRA-ART-{num} — Article {num} — {title}"

    m = RE_ART_ID_LAST_H3.match(line)
    if m:
        num = m.group(1)
        title = m.group(2).strip()
        return f"### CRA-ART-{num} — Article {num} — {title}"

    # ## Article N — Title  (no ID — ID will come from the standalone line below)
    m = RE_ART_NO_ID.match(line)
    if m:
        num = m.group(1)
        title = m.group(2).strip()
        # We return a placeholder; the actual ID is on the next standalone line.
        # The caller handles merging.
        return f"### CRA-ART-{num} — Article {num} — {title}"

    return None


def _is_standalone_id_line(line: str) -> bool:
    """Check if a line is a standalone stable-ID line that should be removed."""
    return bool(
        RE_ART_STANDALONE_BOLD.match(line)
        or RE_ART_STABLE_ID.match(line)
        or RE_CHAP_STANDALONE_BACKTICK.match(line)
        or RE_CHAP_STANDALONE_BOLD.match(line)
        or RE_CHAP_STABLE_ID.match(line)
        or RE_ANNEX_STANDALONE_BACKTICK.match(line)
    )


def _normalize_annex_container(line: str) -> str | None:
    """Normalize annex container heading to ## CRA-ANNEX-<R> — ANNEX <R> — TITLE."""
    # Already canonical with title
    if RE_ANNEX_CONTAINER_DASH.match(line):
        return line

    # ## CRA-ANNEX-III — ANNEX III  (canonical without title — title may follow)
    m = RE_ANNEX_CONTAINER_NO_TITLE.match(line)
    if m:
        return line

    # ## CRA-ANNEX-V — ANNEX V: TITLE  (colon separator)
    m = RE_ANNEX_CONTAINER_COLON.match(line)
    if m:
        annex_id = m.group(1)
        roman = m.group(2)
        title = m.group(3).strip()
        return f"## {annex_id} — ANNEX {roman} — {title}"

    # ## CRA-ANNEX-II  (bare ID, no title — title may be on following lines)
    m = RE_ANNEX_CONTAINER_BARE.match(line)
    if m:
        annex_id = m.group(1)
        roman = m.group(2)
        return f"## {annex_id} — ANNEX {roman}"

    # ## `CRA-ANNEX-IV`  (backticked bare ID)
    m = RE_ANNEX_CONTAINER_BACKTICK.match(line)
    if m:
        roman = m.group(1)
        return f"## CRA-ANNEX-{roman} — ANNEX {roman}"

    # ## ANNEX VIII  (no ID)
    m = RE_ANNEX_CONTAINER_NO_ID.match(line)
    if m:
        roman = m.group(1)
        return f"## CRA-ANNEX-{roman} — ANNEX {roman}"

    # ### CRA-ANNEX-I — ANNEX I  (wrong depth, should be ##)
    m = RE_ANNEX_CONTAINER_H3.match(line)
    if m:
        annex_id = m.group(1)
        roman = m.group(2)
        return f"## {annex_id} — ANNEX {roman}"

    # ### CRA-ANNEX-VI — ANNEX VI: TITLE  (wrong depth, colon)
    m = RE_ANNEX_CONTAINER_H3_COLON.match(line)
    if m:
        annex_id = m.group(1)
        roman = m.group(2)
        title = m.group(3).strip()
        return f"## {annex_id} — ANNEX {roman} — {title}"

    return None


def _normalize_annex_part(line: str) -> str | None:
    """Normalize annex part heading to ### CRA-ANNEX-<R>-PART-<R> — Part <R> ..."""
    # Check for duplicated "Part <roman> Part <roman>" and fix
    m = re.match(
        rf"^### (CRA-ANNEX-({ANNEX_ROMAN})-PART-({ANNEX_ROMAN})) — Part {ANNEX_ROMAN} (.+)$",
        line,
    )
    if m:
        part_id = m.group(1)
        part_roman = m.group(3)
        title = m.group(4).strip()
        # If title starts with "Part <roman> ", it's duplicated
        if title.startswith(f"Part {part_roman} "):
            return f"### {part_id} — {title}"
        # If title is exactly "Part <roman>", it's duplicated (bare)
        if title == f"Part {part_roman}":
            return f"### {part_id} — Part {part_roman}"

    # Already canonical (and no duplication)
    if RE_ANNEX_PART_CANONICAL.match(line):
        return line

    # ### `CRA-ANNEX-VIII-PART-I` — Part I ...  (backticked)
    m = RE_ANNEX_PART_BACKTICK.match(line)
    if m:
        annex_roman = m.group(1)
        part_roman = m.group(2)
        title = m.group(3).strip()
        # Title already starts with "Part <roman>" — don't duplicate
        if title.startswith(f"Part {part_roman}"):
            return f"### CRA-ANNEX-{annex_roman}-PART-{part_roman} — {title}"
        return f"### CRA-ANNEX-{annex_roman}-PART-{part_roman} — Part {part_roman} {title}"

    # #### CRA-ANNEX-I-PART-I — Part I  (wrong depth)
    m = RE_ANNEX_PART_H4.match(line)
    if m:
        part_id = m.group(1)
        part_roman = m.group(3)
        title = m.group(4).strip()
        if title.startswith(f"Part {part_roman}"):
            return f"### {part_id} — {title}"
        return f"### {part_id} — Part {part_roman} {title}"

    return None


def _normalize_annex_point(line: str) -> str | None:
    """Normalize annex point heading to ### CRA-ANNEX-<R>-PT-<N>."""
    # Already canonical
    if RE_ANNEX_PT_CANONICAL.match(line):
        return line

    # ### `CRA-ANNEX-IV-PT-1`  (backticked)
    m = RE_ANNEX_PT_BACKTICK.match(line)
    if m:
        annex_roman = m.group(1)
        pt_num = m.group(2)
        return f"### CRA-ANNEX-{annex_roman}-PT-{pt_num}"

    # #### CRA-ANNEX-VII-PT-1  (wrong depth, should be ###)
    m = RE_ANNEX_PT_H4.match(line)
    if m:
        annex_roman = m.group(1)
        pt_num = m.group(2)
        return f"### CRA-ANNEX-{annex_roman}-PT-{pt_num}"

    return None


def _normalize_annex_subpoint(line: str) -> str | None:
    """Normalize annex sub-point headings to #### depth."""
    # ##### CRA-ANNEX-VII-PT-1-SUBPT-A  (wrong depth, should be ####)
    m = RE_ANNEX_SUBPT_H5.match(line)
    if m:
        return line.replace("#####", "####", 1)
    return None


def _normalize_para_heading(line: str) -> str | None:
    """Normalize paragraph-level headings (chapter VII style)."""
    m = RE_PARA_HEADING_H4.match(line)
    if m:
        art_num = m.group(1)
        para_num = m.group(2)
        suffix = m.group(3).strip()
        if suffix:
            return f"### `CRA-ART-{art_num}-PARA-{para_num}` {suffix}"
        return f"### `CRA-ART-{art_num}-PARA-{para_num}`"
    return None


def _normalize_inline_para_id(line: str) -> list[str] | None:
    """Convert inline bold paragraph IDs to heading + text.

    Handles chapters I-VI style:
      **CRA-ART-N-PARA-M**           → ### `CRA-ART-N-PARA-M`
      **`CRA-ART-N-PARA-M`**         → ### `CRA-ART-N-PARA-M`
      **CRA-ART-N-PARA-M** text...   → ### `CRA-ART-N-PARA-M`  +  ""  +  text...
      **`CRA-ART-N-PARA-M`** text... → same

    Returns a list of replacement lines (may be 1 or 3 lines), or None.
    """
    # Standalone (no text on same line)
    m = RE_PARA_BOLD_STANDALONE.match(line)
    if m:
        art_num = m.group(1)
        para_num = m.group(2)
        return [f"### `CRA-ART-{art_num}-PARA-{para_num}`"]

    # Continuation paragraphs: **CRA-ART-N-PARA-M (continuation, unlettered)** text...
    m = RE_PARA_BOLD_CONTINUATION.match(line)
    if m:
        sid = m.group(1)
        text = m.group(2).strip()
        return [f"### `{sid}`", "", text]

    # Inline with text on same line
    m = RE_PARA_BOLD_INLINE.match(line)
    if m:
        art_num = m.group(1)
        para_num = m.group(2)
        text = m.group(3).strip()
        return [f"### `CRA-ART-{art_num}-PARA-{para_num}`", "", text]

    return None


def _normalize_subpoint_id(line: str) -> str | None:
    """Standardize sub-point IDs to **`ID`** form (bold, backtick, no bracket).

    **CRA-ART-N-PARA-M-PT-X** text...        → **`CRA-ART-N-PARA-M-PT-X`** text...
    **`[CRA-ART-N-PARA-M-PT-X]`** text...    → **`CRA-ART-N-PARA-M-PT-X`** text...
    """
    # Bracket form: **`[ID]`** text...
    m = RE_SUBPT_BOLD_BT_BRACKET.match(line)
    if m:
        sid = m.group(1)
        text = m.group(2)
        return f"**`{sid}`** {text}"

    # No-backtick form: **ID** text...
    m = RE_SUBPT_BOLD_NO_BT.match(line)
    if m:
        sid = m.group(1)
        text = m.group(2)
        return f"**`{sid}`** {text}"

    return None


def _normalize_annex_inline_point(line: str) -> list[str] | None:
    """Convert inline annex point IDs to heading + text.

    `CRA-ANNEX-...-PT-N`             → ### `CRA-ANNEX-...-PT-N`
    `CRA-ANNEX-...-PT-N` text...     → ### `CRA-ANNEX-...-PT-N`  +  ""  +  text...
    **CRA-ANNEX-...-PT-N**           → ### `CRA-ANNEX-...-PT-N`
    **CRA-ANNEX-...-PT-N** text...   → ### `CRA-ANNEX-...-PT-N`  +  ""  +  text...

    Returns a list of replacement lines, or None.
    """
    # Standalone bold
    m = RE_ANNEX_PT_BOLD_STANDALONE.match(line)
    if m:
        sid = m.group(1)
        return [f"### `{sid}`"]

    # Bold with text
    m = RE_ANNEX_PT_BOLD_WITH_TEXT.match(line)
    if m:
        sid = m.group(1)
        text = m.group(2).strip()
        return [f"### `{sid}`", "", text]

    # Standalone backtick
    m = RE_ANNEX_PT_INLINE_STANDALONE.match(line)
    if m:
        sid = m.group(1)
        return [f"### `{sid}`"]

    # Backtick with text
    m = RE_ANNEX_PT_INLINE_WITH_TEXT.match(line)
    if m:
        sid = m.group(1)
        text = m.group(2).strip()
        return [f"### `{sid}`", "", text]

    return None


def normalize_lines(lines: list[str]) -> list[str]:
    """Apply all heading normalizations to a list of lines."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()

        # Try chapter heading
        chap = _normalize_chapter_heading(stripped)
        if chap is not None:
            result.append(chap)
            # Skip following standalone ID lines (and blank lines between)
            j = i + 1
            while j < len(lines):
                nxt = lines[j].rstrip()
                if nxt == "":
                    # Peek past blank line — keep it if there's content after
                    # but don't consume standalone ID lines
                    if j + 1 < len(lines) and _is_standalone_id_line(lines[j + 1].rstrip()):
                        j += 1
                        continue
                    break
                if _is_standalone_id_line(nxt):
                    j += 1
                    continue
                break
            i = j
            continue

        # Try article heading
        art = _normalize_article_heading(stripped)
        if art is not None:
            result.append(art)
            # Skip following standalone ID lines
            j = i + 1
            while j < len(lines):
                nxt = lines[j].rstrip()
                if nxt == "":
                    if j + 1 < len(lines) and _is_standalone_id_line(lines[j + 1].rstrip()):
                        j += 1
                        continue
                    break
                if _is_standalone_id_line(nxt):
                    j += 1
                    continue
                break
            i = j
            continue

        # Try sub-point ID normalization (must come before inline para —
        # sub-point IDs like CRA-ART-1-PARA-1-PT-A contain PARA-1)
        subpt = _normalize_subpoint_id(stripped)
        if subpt is not None:
            result.append(subpt)
            i += 1
            continue

        # Try paragraph heading (chapter VII #### style)
        para = _normalize_para_heading(stripped)
        if para is not None:
            result.append(para)
            i += 1
            continue

        # Try inline bold paragraph ID (chapters I-VI style)
        inline_para = _normalize_inline_para_id(stripped)
        if inline_para is not None:
            result.extend(inline_para)
            i += 1
            continue

        # Try annex container heading
        annex_ctr = _normalize_annex_container(stripped)
        if annex_ctr is not None:
            result.append(annex_ctr)
            # Skip following standalone ID lines and subtitle/title lines
            j = i + 1
            while j < len(lines):
                nxt = lines[j].rstrip()
                if nxt == "":
                    if j + 1 < len(lines) and (
                        _is_standalone_id_line(lines[j + 1].rstrip())
                        or RE_ANNEX_SUBTITLE.match(lines[j + 1].rstrip())
                        or RE_ANNEX_TITLE_LINE.match(lines[j + 1].rstrip())
                        or RE_ANNEX_TITLE_H2.match(lines[j + 1].rstrip())
                    ):
                        j += 1
                        continue
                    break
                if _is_standalone_id_line(nxt):
                    j += 1
                    continue
                # Skip ### ANNEX II / ### TITLE / ## TITLE subtitle lines
                if RE_ANNEX_SUBTITLE.match(nxt) or RE_ANNEX_TITLE_LINE.match(nxt) or RE_ANNEX_TITLE_H2.match(nxt):
                    j += 1
                    continue
                break
            i = j
            continue

        # Try annex part heading
        annex_part = _normalize_annex_part(stripped)
        if annex_part is not None:
            result.append(annex_part)
            i += 1
            continue

        # Try annex point heading
        annex_pt = _normalize_annex_point(stripped)
        if annex_pt is not None:
            result.append(annex_pt)
            i += 1
            continue

        # Try inline annex point ID (annex I, III, VIII style)
        inline_annex_pt = _normalize_annex_inline_point(stripped)
        if inline_annex_pt is not None:
            result.extend(inline_annex_pt)
            i += 1
            continue

        # Try annex sub-point heading (fix depth)
        annex_subpt = _normalize_annex_subpoint(stripped)
        if annex_subpt is not None:
            result.append(annex_subpt)
            i += 1
            continue

        # Remove orphan standalone ID lines that weren't consumed above
        # (safety net — shouldn't normally trigger if heading logic is correct)
        if _is_standalone_id_line(stripped):
            i += 1
            continue

        result.append(line)
        i += 1

    return result


def normalize_file(path: Path) -> bool:
    """Normalize a single file. Returns True if changed."""
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    normalized = normalize_lines(lines)
    new_content = "\n".join(normalized)
    if new_content != original:
        path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any file would change; don't modify files.",
    )
    args = parser.parse_args()

    changed: list[str] = []
    for pack_file in PACK_FILES:
        if not pack_file.exists():
            continue
        original = pack_file.read_text(encoding="utf-8")
        lines = original.split("\n")
        normalized = normalize_lines(lines)
        new_content = "\n".join(normalized)
        if new_content != original:
            changed.append(str(pack_file.relative_to(REPO_ROOT)))
            if not args.check:
                pack_file.write_text(new_content, encoding="utf-8")

    if changed:
        if args.check:
            print("Files needing normalization:")
            for f in changed:
                print(f"  {f}")
            return 1
        else:
            print(f"Normalized {len(changed)} file(s):")
            for f in changed:
                print(f"  {f}")
    else:
        print("All pack headings already normalized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
