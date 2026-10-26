#!/bin/sh
# Stop this checkout's local SIPI session, including workers and child servers.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x backend/.venv/bin/python ]; then
  sipi_python=backend/.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  sipi_python=python3
else
  echo "Для остановки нужен Python 3.11 или новее." >&2
  exit 1
fi
exec "$sipi_python" scripts/local_dev.py stop
