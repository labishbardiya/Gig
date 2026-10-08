#!/bin/bash
set -eu
cd "$(dirname "$0")"
umask 077
exec .venv/bin/python -m uvicorn gig_backend.api:create_app --factory --host 127.0.0.1 --port 8765 --no-access-log
