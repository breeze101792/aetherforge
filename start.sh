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

if [ ! -f aetherforge.toml ]; then
    echo "No aetherforge.toml found, copying from aetherforge.example.toml"
    cp aetherforge.example.toml aetherforge.toml
fi

export AETHERFORGE_ENV="$MODE"

if [ "$MODE" = "test" ]; then
    echo "Starting Aether Forge [TEST mode] (see aetherforge.toml [test] section)"
else
    echo "Starting Aether Forge (see aetherforge.toml [server] section)"
fi

mkdir -p data

python -m gateway.main
