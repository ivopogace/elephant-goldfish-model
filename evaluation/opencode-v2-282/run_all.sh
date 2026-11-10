#!/usr/bin/env bash
# Repeat the whole evaluation. Model calls use the OpenCode login already stored on this
# machine; nothing but the fake fixture and the EGM bundle is sent.
#
#   ./run_all.sh <new-output-dir> <checkout-of-candidate-commit>
#
# Optional environment: INSTALL (default /opt/egm-v2), OPENCODE, MODEL, UPSTREAM.
set -euo pipefail
OUT=$(realpath -m "${1:?output directory}")
SOURCE=$(realpath "${2:?checkout of the candidate commit}")
HERE=$(cd "$(dirname "$0")" && pwd)
INSTALL=${INSTALL:-/opt/egm-v2}
OPENCODE=${OPENCODE:-/opt/opencode-2.2.6/node_modules/.bin/opencode}
MODEL=${MODEL:-opencode-go/longcat-2.5-free}
UPSTREAM=${UPSTREAM:-https://opencode.ai/inference/go/openai/v1}
mkdir -p "$OUT"
drive() { # drive <run-name> <workflow> [driver options...]
  local name=$1 workflow=$2; shift 2
  python3 "$HERE/harness/driver.py" "$workflow" --output "$OUT/$name" --install "$INSTALL" \
    --opencode "$OPENCODE" --model "$MODEL" --upstream "$UPSTREAM" "$@" > "$OUT/$name.log" 2>&1 \
    || echo "run $name did not complete; see $OUT/$name.log"
}

# 1. Installation and offline checks (no model).
python3 "$HERE/harness/record_environment.py" --install "$INSTALL" --source "$SOURCE" \
  --opencode "$OPENCODE" --model "$MODEL" > "$OUT/environment.json"
python3 "$HERE/harness/verify_install.py" --install "$INSTALL" --source "$SOURCE" > "$OUT/install-check.json"
python3 "$SOURCE/tests/integration/opencode_v2_native_probe.py" --source "$SOURCE" \
  --opencode "$OPENCODE" --output "$OUT/native-probe" > "$OUT/native-probe.log"

# 2. Live workflows. The chain feeds each stage's output into the next one.
( drive chain-1-brainstorm brainstorm
  drive chain-2-draft draft --project-from "$OUT/chain-1-brainstorm"
  drive chain-3-review review --project-from "$OUT/chain-2-draft" ) &
drive review-1 review &
( drive brainstorm-2 brainstorm --record-tui --preapprove-writes ) &
wait

# 3. Targeted live probes.
drive probe-hostile-design review_stage5 --inject &
drive probe-long-design review_stage5 --long-design &
drive probe-no-guard brainstorm --without-guard --end-after-gate-turn &
wait
drive probe-cancelled-gate brainstorm --cancel-first-gate &
drive probe-parent-symlink parent_symlink_probe &
drive probe-foreign-agent foreign_dispatch_probe --agent build &
wait

# 4. Analysis.
RUNS=()
for run in "$OUT"/*/; do [ -f "$run/run.json" ] && RUNS+=("${run%/}"); done
python3 "$HERE/harness/analyze.py" "${RUNS[@]}" > /dev/null
python3 "$HERE/harness/summarize.py" "${RUNS[@]}" --json "$OUT/summary.json" --markdown "$OUT/summary.md"
