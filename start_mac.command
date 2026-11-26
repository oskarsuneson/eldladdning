#!/bin/sh
# Dubbelklicka i Finder for att starta spelet pa macOS.
cd "$(dirname "$0")" || exit 1

fail() {
  echo
  echo "$1"
  echo
  printf 'Tryck Enter for att stanga...'
  read -r _
  exit 1
}

# Gor terminalfonstret stort nog (minst 110x30)
printf '\033[8;38;124t'

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && \
     "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$c"
    break
  fi
done
[ -n "$PY" ] || fail "Hittade ingen Python 3.9 eller nyare.
Installera fran https://www.python.org/downloads/ eller med:  brew install python"

"$PY" -c "import curses" 2>/dev/null || \
  fail "Din Python saknar curses-modulen. Installera Python fran python.org eller:  brew install python"

"$PY" eldledning.py
