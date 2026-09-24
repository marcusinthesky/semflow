#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
example_dir="$(mktemp -d /tmp/semflow-quickstart.XXXXXX)"
trap 'rm -rf -- "$example_dir"' EXIT

cp -R "$repo_root/examples/quickstart/." "$example_dir/"
cd "$example_dir"

unset VIRTUAL_ENV
export UV_PROJECT_ENVIRONMENT="$example_dir/.venv"
uv add "$repo_root"

status=0
uv run semflow check || status=$?
test "$status" -eq 1
uv run semflow patch > "$example_dir/preview.diff"
grep -q 'entrypoints/example/greet.json' "$example_dir/preview.diff"
uv run semflow patch --apply
uv run semflow check
uv run example greet
grep -q 'Hello, Ada!' data/greeting.txt
