#!/bin/bash
# Full reproduction from your own builds: re-extracts every ABI model into data/abi_cache_fresh,
# rebuilds each issue's app, reproduces each failure, runs DepOwl, then compares with expected/.
R=$(cd "$(dirname "$0")" && pwd); cd "$R/depowl"
export DEPOWL_CACHE="$R/data/abi_cache_fresh"; mkdir -p "$DEPOWL_CACHE"
python3 rq1.py || exit 1
echo; echo "Running each app against every library version (a few minutes) ..."
python3 version_truth.py || exit 1
echo; python3 compare.py
