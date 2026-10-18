#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
${CC:-gcc} -std=gnu11 -Wall -Wextra -Werror -g \
  -fsanitize=address,undefined tests/test_module.c -o "$tmp/test_module"
ASAN_OPTIONS=detect_leaks=0 "$tmp/test_module"
python3 tests/test_runner.py
python3 tests/test_install.py
for file in run.sh install.sh boot.sh collect.sh tests/run-tests.sh; do bash -n "$file"; done
sh -n build.sh
echo 'PASS: shell syntax'
