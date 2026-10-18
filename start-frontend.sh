#!/bin/sh
# Kept for existing local launch instructions. Both services now start together.
set -eu
exec "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/start.sh"
