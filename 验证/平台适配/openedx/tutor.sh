#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export TUTOR_ROOT="$PWD/.runtime/tutor"
export TUTOR_PLUGINS_ROOT="$PWD/.runtime/plugins"
exec .runtime/venv/bin/tutor "$@"
