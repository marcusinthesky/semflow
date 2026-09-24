# Getting started

`semflow` requires Python 3.13. Install it in the same environment as your
Typer application so it can discover the application's console script:

```bash
uv add git+ssh://git@github.com/marcusinthesky/semflow.git
```

For a complete example, copy the files from the
[quickstart project](https://github.com/marcusinthesky/semflow/tree/main/examples/quickstart)
into a new directory. It contains an installable `example` command, one DVC
stage, input data, and `semflow.toml`. Run `uv add` above in that directory; uv
will install both the local application and `semflow` into one environment.

`dvc.yaml` initially names a raw Python dependency:

```yaml
stages:
  greet:
    cmd: example greet
    deps:
      - src/example/stage.py
      - data/name.txt
    outs:
      - data/greeting.txt
```

Run the review sequence:

```bash
uv run semflow check          # exit 1: the fingerprint is missing
uv run semflow patch          # preview the proposed YAML and JSON changes
uv run semflow patch --apply  # accept the reviewed changes
uv run semflow check          # exit 0: the fingerprint is current
```

The patch replaces the Python dependency with a generated entrypoint JSON
fingerprint. The input data dependency remains in DVC. Commit the updated
`dvc.yaml` and `.semflow/hashes` files, and make `semflow check` part of your
project's CI before relying on fingerprints for DVC invalidation.

After a semantic source edit, `uv run semflow refresh --apply` updates only the
fingerprint JSON. If DVC instrumentation itself changes, preview and apply a
full `patch` again. For pip environments, use
`python -m pip install 'git+ssh://git@github.com/marcusinthesky/semflow.git'`
in the application's environment. GitHub access to the private repository is
required; pin a Git commit or tag for reproducibility.
