# Technology underpinnings — EU CRA Context Packs

This repository stores the consolidated EU Cyber Resilience Act as a set of precisely addressable Markdown files. The implementation is intentionally simple: static Markdown, stable identifiers, and a small Python normalisation script.

## Source text and parse approach

The source is Regulation (EU) 2024/2847, CELEX 32024R2847. The text in this repository was parsed from a third-party PDF mirror (`raw.githubusercontent.com/cra-compliance-lab/awesome-cra-compliance/main/docs/eu/cra-regulation-2024-2847.pdf`) because EUR-Lex was unreachable when the pack was built. The parser mechanically split the printed structure into chapters, articles, paragraphs, points, recitals, and annexes, then assigned a stable identifier to each unit.

## Stable identifier scheme

Every legal unit has a machine-readable stable ID derived from its printed numbering.

| Unit type | Pattern | Example |
|---|---|---|
| Recital | `CRA-REC-<n>` | `CRA-REC-10` |
| Chapter | `CRA-CHAP-<roman>` | `CRA-CHAP-II` |
| Article | `CRA-ART-<n>` | `CRA-ART-13` |
| Paragraph | `CRA-ART-<n>-PARA-<m>` | `CRA-ART-13-PARA-2` |
| Point | `...-PT-<x>` | `CRA-ART-13-PARA-2-PT-A` |
| Sub-point | `...-SUBPT-<y>` | `CRA-ART-13-PARA-2-PT-A-SUBPT-i` |
| Annex | `CRA-ANNEX-<roman>` | `CRA-ANNEX-I` |
| Annex part | `CRA-ANNEX-<roman>-PART-<roman>` | `CRA-ANNEX-I-PART-II` |
| Annex point | `CRA-ANNEX-<roman>...-PT-<n>` | `CRA-ANNEX-I-PART-II-PT-3` |

The numbering is not invented: it mirrors the article, paragraph, and point numbers printed in the regulation. Annex I uses `-PART-<roman>` because its two parts both restart point numbering at (1).

## File and heading conventions

- One file per chunk: [`recitals.md`](recitals.md), one file per chapter under [`chapters/`](chapters/), and one file per annex under [`annexes/`](annexes/).
- Container headings (chapters and annexes) use `##` and put the stable ID first: `## CRA-CHAP-I — CHAPTER I — GENERAL PROVISIONS`.
- Unit headings (articles, paragraphs, points, parts, recitals) use `###` and put the stable ID first or as a backticked subheading.
- Legal wording is never changed by the tooling. Only the surrounding Markdown markup is normalised.

## Maintenance tooling

[`scripts/normalize_pack_headings.py`](scripts/normalize_pack_headings.py) is the only operational script. It is a Python 3 stdlib-only program that:

- Reads every pack file listed in `PACK_FILES`.
- Uses regular expressions to detect headings and standalone stable-ID lines.
- Converts headings to the canonical format (ID first, correct heading depth, em-dash separators).
- Removes redundant standalone ID lines.

Run it in place:

```bash
python3 scripts/normalize_pack_headings.py
```

Run it in check mode, for example in continuous integration:

```bash
python3 scripts/normalize_pack_headings.py --check
```

[`scripts/normalize_pack_headings.py`](scripts/normalize_pack_headings.py) makes no semantic changes. It only fixes Markdown structure around the legal text.

## Rendering and integration

The repository has no runtime dependencies, no build step, and no server-side code. You can:

- Open any `.md` file in a Markdown viewer, editor, or GitHub/GitLab web interface.
- Link directly to a heading when citing a provision.
- Search the corpus with `grep`, `rg`, or an editor's search tool.
- Include specific units as context for a language model by copying the relevant section.

## Quality and security tooling

- [`.claude/hooks/post_edit_lint.py`](.claude/hooks/post_edit_lint.py) runs lightweight post-edit checks on changed files. It uses tools already present on the machine (for example `ruff`, `python -m py_compile`, `php -l`, `node --check`) and exits with a warning if it finds problems.
- [`.devin/config.json`](.devin/config.json) declares the `biofool/magic-compact-devin` plugin for agent sessions.
- [`.gitignore`](.gitignore) excludes `.ai-context/` generation artifacts.

## Caveats and limits

- The source is a static snapshot, not a live feed from EUR-Lex.
- The 2024-12-05 and 2025-07-02 corrigenda were not checked against this text.
- Paragraph, point, and chapter boundaries are a mechanical parse and have not had legal review.
- This is not legal advice. Always verify the exact wording on [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2847) before relying on a provision for compliance.
