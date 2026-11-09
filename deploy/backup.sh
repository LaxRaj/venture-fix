#!/usr/bin/env bash
# Nightly consistent copy of the SQLite database (ledger, approvals, prospects).  Keeps the newest 7.
set -euo pipefail
DB=/opt/venture-fix/runs/fleet.db
OUT=/opt/venture-fix/runs/backups
mkdir -p "$OUT"
python3 - "$DB" "$OUT/fleet-$(date +%F).db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)  # safe while the app is writing
dst.close(); src.close()
PY
ls -1t "$OUT"/fleet-*.db | tail -n +8 | xargs -r rm --
