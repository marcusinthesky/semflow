# Concepts

DVC owns the stage graph, command, input data, and outputs. `semflow` only
changes how the stage's first-party Python dependency is represented.

For each configured Typer command, `semflow` follows its reachable first-party
symbols, normalizes their Python syntax, and writes a deterministic JSON
fingerprint. Changes to comments or unrelated functions need not invalidate
the stage. Unresolved first-party references cause conservative whole-module
fallbacks, recorded in the JSON.

`check` detects stale DVC YAML or fingerprints without writing. `patch`
previews all needed changes; `patch --apply` writes them. `refresh --apply`
updates only JSON and refuses stale DVC instrumentation. The authored
`dvc.yaml` remains the source of truth.
