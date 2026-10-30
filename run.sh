#!/bin/sh
# Resolve paths relative to this script, not the caller's working directory.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export LD_LIBRARY_PATH="$ROOT/libfreenect2/install/lib:$ROOT/.local-deps/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

if [ -x "$ROOT/.venv/bin/python" ]; then
    exec "$ROOT/.venv/bin/python" "$ROOT/app/main.py" "$@"
elif command -v micromamba >/dev/null 2>&1; then
    exec micromamba run -n kinectv2-dev python "$ROOT/app/main.py" "$@"
else
    echo 'Falta el entorno Python. Consulta «Primera instalación» en README.md.' >&2
    exit 1
fi
