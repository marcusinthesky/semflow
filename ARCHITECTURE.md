---
description: "Why semflow is a reusable package with a narrow DVC adapter, deterministic JSON boundary, and review-first patch workflow."
title: Semflow architecture
---

## Semflow architecture

### Boundary

`semflow` is a reusable Python package because semantic normalization and patch
planning are useful to the pipeline application and to a standalone console script.
The pipeline app depends on `semflow`; `semflow` has no static product imports or
product dependency. During planning, discovery loads the configured console-script
composition root, then all reachability work uses indexed source ASTs.

```text
pipeline CLI adapter ──▶ semflow public API ──▶ Typer command discovery
                                            ├─▶ static symbol closure
                                            ├─▶ AST normalizer
                                            └─▶ DVC dependency patch planner
```

Within the package, capability wins at the top level (`hashing`, `discovery`, `dvc`,
`config`, `tracking`), with static reachability under `analysis/` and immutable
cross-capability records in `model`. The public surface is the small
`semflow.__init__` re-export set; patch mechanics remain behind `semflow.dvc`.

### Decisions

| Decision | Why | Rejected alternative |
|---|---|---|
| `dvc.yaml` remains authored source of truth | Preserves DVC `cmd`, `params`, `outs`, `foreach`, `matrix`, cache, and frozen semantics | Python decorators compiling a second pipeline model |
| One JSON fingerprint per authored command entrypoint | A stage invalidates only when code reachable from that callback changes | One hash per raw source directory, which invalidates unrelated entrypoints |
| Typer registration-tree discovery first | Preserves the authored callback even when a custom Click command class wraps it | Treating Click's final callback wrapper as the source entrypoint |
| Identity-preserving optional `@track` | Supports explicit opt-in and closure seeds without changing Typer introspection or call behavior | Runtime wrapper decorators |
| Conservative static first-party closure | Reproducible without executing a stage; tracks functions, classes, globals, bindings, decorators, and defaults | Runtime tracing, whose coverage depends on the particular data and branch exercised |
| Explained whole-module fallback | Never silently drops an unresolved first-party edge | Guessing through dynamic dispatch or omitting the dependency |
| Standard-library `ast` canonicalization | Formatting and comments disappear by construction; no concrete-syntax dependency | LibCST, whose formatting-preserving features are unnecessary here |
| `check` + preview-first `patch` + JSON-only `refresh` | Makes generated changes inspectable, supports a pure DVC refresh producer, and keeps CI read-only | A `sync` command that rewrites implicitly |
| No backend/plugin registry in v0.1 | There is one consumer and one file format to prove | Entry points, Pluggy, or a DI container before a second backend exists |

### Three correctness layers

Command closure and semantic hashing answer different questions:

1. DVC decides *which command and non-code inputs* determine a stage.
2. `semflow` resolves that command to a callback and decides which first-party symbols
   are statically reachable.
3. AST normalization decides whether those symbols changed under the configured
   semantic policy.

The generated entrypoint JSON is the code-dependency boundary DVC hashes. The
root-owned DVC operator validates each canonical alias, authored command, callback,
schema, policy, digest shape, and source-root path by reading JSON and source ASTs as
data; it never imports semflow or product packages. The companion mandatory
`semflow check` hook recomputes semantic freshness. Both gates landed with the DVC/JSON
cutover so a stale proxy cannot silently suppress invalidation.

The optional DVC `semflow_refresh` stage is a pure producer for that JSON boundary.
It depends broadly on configured source roots, emits `.semflow/hashes` as a
`cache: false` directory output, and downstream stages depend on exact child JSON
files. `semflow refresh --apply` refuses to run when the authored YAML still needs
instrumentation changes; adding or repairing aliases remains the review-first
`semflow patch --apply` operation outside the graph. Configured control-stage names
are skipped during instrumentation discovery, preventing the producer from
instrumenting itself.

### Closure boundary

The analyzer indexes configured import roots without importing product modules. Typer
discovery separately loads only the installed application composition root so it can
recover the original registered callback. Reachability then operates on source ASTs:
an unrelated function in the same file or package is omitted, while referenced
first-party symbols are followed transitively. Typer callbacks and decorated functions
retain annotations because framework behavior may consume them at runtime.

String-based imports and general runtime dispatch are not guessed in v0.1. If an
ordinary static first-party reference cannot be resolved, its complete module semantic
hash is included and the fallback reason is serialized. This biases uncertainty toward
extra invalidation rather than silent staleness.

### Extension seams

The stable seams are `HashPolicy`, `EntrypointFingerprint`, `TrackSpec`, `PatchPlan`,
and the public `check`/`patch` functions. A later release can add qualified class-method
closure, richer command parsing, another language normalizer, explanation output, or
another pipeline-file adapter without changing the v0.1 CLI. A generic plugin system is
deferred until a second independently shipped backend demonstrates the interface it
actually needs.
