# DepOwl RQ1 reproduction kit

Reproduces RQ1 of Jia et al., "DepOwl: Detecting Dependency Bugs to Prevent Compatibility
Failures" (ICSE 2021) on 15 real failures in zlib, expat and SQLite.
Result: 13 of 15 prevented (paper: 35 of 38). Both misses come from compilation directives.

Needs Linux (Ubuntu 22.04/24.04, or WSL on Windows).

## Two ways to check
1. Quick check, ~1 minute, Python only, no downloads:
       cd depowl && python3 quick_check.py
   Reruns DepOwl from the shipped ABI models and app facts and checks the 13/15 result,
   the paper's two worked examples, and the authors' own ABI-Tracker output.
   Needs pyelftools only if you rebuild; the quick check itself needs plain Python 3.
2. Full reproduction, ~1 hour, rebuilds everything from git:
       bash setup.sh       # checks tools, clones zlib/expat/SQLite/pyelftools into src/
       bash build_all.sh   # builds 360 library releases into build/
       bash full_run.sh    # rebuilds apps, reproduces failures, reruns DepOwl, compares with expected/

