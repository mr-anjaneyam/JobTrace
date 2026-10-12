#!/bin/bash
# Starts the JobTrace web UI.
cd "$(dirname "$0")" || exit 1
if [ -f run.sh ]; then
  eval "$(grep -E '^export (TELEGRAM|XKIRO|CURSOR|TYPESAFE|JOBTRACE)_' run.sh || true)"
fi
exec python3 -m jobtrace.main web "$@"
