#!/bin/sh
# Build code.zip for submission: code/ (with cache + evaluation), shared/, docs, tests, README.
# Excludes dataset/, .env, caches, virtualenvs, log.txt. Then greps the zip for key shapes.
set -e
cd "$(dirname "$0")/.."
rm -f code.zip
zip -qr code.zip code shared tests docs/project_spec.md docs/learnings.md docs/mvp_results.md docs/v1_log.md \
    README.md problem_statement.md .env.example \
    -x '*/__pycache__/*' '*.pyc' '*/.pytest_cache/*' 'code/evaluation/usage.jsonl'
if unzip -p code.zip | grep -aE 'sk-or-v1-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}' >/dev/null; then
  echo "SECRET FOUND IN ZIP"; rm code.zip; exit 1; fi
ls -la code.zip; unzip -l code.zip | tail -1
