#!/bin/bash
set -e

cd "$(dirname "$0")"

MODE="prod"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test|-t) MODE="test"; shift ;;
        --prod|-p) MODE="prod"; shift ;;
        *) echo "Usage: $0 [--test|-t|--prod|-p]"; exit 1 ;;
    esac
done

if [ ! -d venv ]; then
    echo "Creating virtualenv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

export AETHERFORGE_ENV="$MODE"

if [ "$MODE" = "test" ]; then
    export GATEWAY_PORT="${GATEWAY_PORT:-8001}"
    echo "Starting aetherforge [TEST mode] on http://127.0.0.1:${GATEWAY_PORT:-8001}"
    echo "  DB: data/test.db  Registry: data/test-registry.json"
else
    echo "Starting aetherforge on http://127.0.0.1:${GATEWAY_PORT:-8000}"
    echo "  DB: data/aetherforge.db  Registry: data/registry.json"
fi

python -m gateway.main
