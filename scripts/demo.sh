#!/usr/bin/env bash
# One-command demo: data (if missing) -> one full agent run -> review UI.
set -e
cd "$(dirname "$0")/.."
if [ ! -f data/longview.db ] || [ "$(python -c \
  \"import sqlite3;print(sqlite3.connect('data/longview.db').execute('SELECT COUNT(*) FROM raw_events').fetchone()[0])\")" = "0" ]; then
  python -m datagen.generate --seed 42 --learners 80
fi
python -m agent.run --learner L002 --simulate --no-llm
echo ""
echo "Starting the teacher review UI on http://localhost:8080  (Ctrl+C to stop)"
python -m ui.app
