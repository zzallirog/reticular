#!/bin/sh
# Demo one-liner: generate the synthetic corpus and serve Reflect over it.
# Open http://127.0.0.1:${RETICULAR_PORT:-8899}/fires  (attention plane)
#  and http://127.0.0.1:${RETICULAR_PORT:-8899}/       (sessions plane)
# Port busy (another Reflect already running)? RETICULAR_PORT=8901 sh demo/run.sh
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/gen.py"
export RETICULAR_GLADOS_DIR="$HERE/glados"
export RETICULAR_PROJECTS_DIR="$HERE/projects"
export RETICULAR_STATE_DIR="$HERE/.state"
cd "$HERE/../reflect"
exec python3 server.py
