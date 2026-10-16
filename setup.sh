#!/bin/bash
# One-time setup: checks tools, then downloads library histories and pyelftools into ./src.
# Run from anywhere:  bash setup.sh
set -e
R=$(cd "$(dirname "$0")" && pwd); cd "$R"
missing=""
for c in gcc clang git make autoconf automake libtoolize python3 tclsh; do command -v $c >/dev/null || missing="$missing $c"; done
if [ -n "$missing" ]; then
  echo "Missing tools:$missing"
  echo "On Ubuntu/WSL run:  sudo apt update && sudo apt install -y build-essential clang git autoconf automake libtool tcl python3"
  exit 1
fi
mkdir -p src
clone() {
  [ -d "src/$2/.git" ] && { echo "src/$2 already present"; return; }
  for try in 1 2 3; do
    echo "cloning $1 (attempt $try) ..."
    rm -rf "src/$2"
    git clone -q "https://github.com/$1.git" "src/$2" && return
    sleep 5
  done
  echo "Could not download $1. Check your internet connection and run setup.sh again."; exit 1
}
clone madler/zlib zlib
clone libexpat/libexpat libexpat
clone sqlite/sqlite sqlite          # large: a few hundred MB
clone eliben/pyelftools pyelftools
git -C src/pyelftools checkout -q v0.33
python3 -c "import sys; sys.path.insert(0,'src/pyelftools'); import elftools; print('pyelftools', elftools.__version__)"
echo "Setup done. Next:  bash build_all.sh"
