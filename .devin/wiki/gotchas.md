# Gotchas — eu-cra-context-packs

2026-10 security audit: scanned; oversized `recitals.md`/`README.md` skipped by scanner — tracked at https://github.com/biofool/EU-CRA-context-packs/issues/2 .

## Standing rules
- Never commit secrets (`.env`, `*.key`, `credentials*.json` are gitignored).
- Never read or log secret values — key names and lengths only.
- Security fixes land reviewed-but-uncommitted first, then roll dev → main.
