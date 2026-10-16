#!/bin/bash
# Builds every release of zlib (1.2.0-1.3.1), expat (2.0.0-2.9.0) and SQLite (3.0.0-3.54.0)
# as debug shared libraries under ./build. Takes about 30-60 minutes; safe to rerun (skips finished builds).
R=$(cd "$(dirname "$0")" && pwd); cd "$R"
mkdir -p logs
J=$(nproc 2>/dev/null || echo 2)
echo "zlib ...";   git -C src/zlib tag --sort=creatordate | sed -n '/^v1.2.0$/,/^v1.3.1$/p' | grep -v pre | xargs -P$J -n1 scripts/build_zlib.sh | grep FAIL
echo "expat ...";  git -C src/libexpat tag --sort=creatordate | sed -n '/^R_2_0_0$/,/^R_2_9_0$/p' | xargs -P$J -n1 scripts/build_expat.sh | grep FAIL
echo "sqlite ... (the long one)"
git -C src/sqlite tag | grep -E '^version-3\.[0-9]+(\.[0-9]+)*$' | sort -V | sed -n '/^version-3.0.0$/,/^version-3.54.0$/p' > logs/sqlite_tags.txt
xargs -P$J -n1 scripts/build_sqlite.sh < logs/sqlite_tags.txt > logs/sqlite_build.txt
# a few old releases ship a stale ./configure; retry those after regenerating it
grep FAIL logs/sqlite_build.txt | awk '{print "version-"$2}' | while read t; do REGEN=1 scripts/build_sqlite.sh $t; done | grep FAIL
for lib in zlib expat sqlite; do echo "$lib: $(ls build/$lib/*/.ok 2>/dev/null | wc -l) versions built"; done
echo "Expected: zlib 51, expat 45, sqlite 264 (7 old SQLite tags do not build from git; none is used by an issue)."
echo "Next:  bash full_run.sh"
