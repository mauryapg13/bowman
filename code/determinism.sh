#!/bin/sh
# Run the pipeline twice and prove the outputs are byte-identical.
set -e
cd "$(dirname "$0")/.."
python3 code/main.py --out /tmp/bowman_run1.csv >/dev/null
python3 code/main.py --out /tmp/bowman_run2.csv >/dev/null
a=$(shasum -a 256 /tmp/bowman_run1.csv | cut -d' ' -f1)
b=$(shasum -a 256 /tmp/bowman_run2.csv | cut -d' ' -f1)
echo "run1 $a"; echo "run2 $b"
[ "$a" = "$b" ] && echo "DETERMINISTIC" || { echo "MISMATCH"; exit 1; }
