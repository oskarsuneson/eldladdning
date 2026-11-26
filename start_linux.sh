#!/bin/sh
# Starta spelet pa Linux:  ./start_linux.sh   (eller hogerklicka -> Kor som program)
cd "$(dirname "$0")" || exit 1

fail() {
  echo
  echo "$1"
  echo
  printf 'Tryck Enter for att stanga...'
  read -r _
  exit 1
}

# Gor terminalfonstret stort nog (minst 110x30) - ignoreras av terminaler som inte stoder det
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
Installera med:  sudo apt install python3     (Debian/Ubuntu/ChromeOS)
                 sudo dnf install python3     (Fedora)"

"$PY" -c "import curses" 2>/dev/null || \
  fail "Din Python saknar curses-modulen. Pa Debian/Ubuntu:  sudo apt install python3"

"$PY" eldledning.py
