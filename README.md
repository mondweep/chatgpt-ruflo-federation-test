# Mondweep's rUv Learning Labs

Reproducible, local experiments for `@ruvector/typesafe` and Ruflo mods. The
experiments are intentionally isolated from shared repositories and Federation
claims.

## Lab 1 — Typesafe decision, calibration and abstention

Package: `@ruvector/typesafe@0.2.0` (native core reports `2.4.0`).

Run:

```bash
npm install
npm run typesafe
```

The script models enterprise work routing across `cloud`, `payments`, `ai` and
an out-of-scope `other` category. It compares an untrained engine with an engine
that has admitted 30 labelled examples, using:

- choice instructions;
- sigmoid abstention;
- a catch-all option and threshold;
- cross-fitted calibration;
- held-out accuracy, macro-F1, ECE, Brier score and latency.

### Observed result in this environment

- Native binding loaded successfully.
- All 30 labels were accepted into the example bank.
- `TrainReport` named a `linear-probe`, but live decisions remained on
  `nearest-prototype` and engine stats reported zero compiled questions.
- `calibrated` remained `false`.
- The catch-all dominated all nine held-out examples, yielding accuracy 0.333,
  macro-F1 0.125 and ECE 0.279.
- Median decision latency was under 0.11 ms in both runs.

This is a valid wiring and governance observation, not an accuracy benchmark.
The installed package defaults to `hash-bow-256@test-double`; its documentation
explicitly says that the hash embedder is not semantically meaningful and never
provides production calibration. It also demonstrates that admitting examples
is distinct from promoting a trained head through the optimization loop.

### Next rigorous step

Repeat with the pinned BGE ONNX model and a larger frozen train/calibration/test
split. Tune the catch-all threshold only on validation data. Do not tune against
the test split. Compare:

1. nearest-prototype baseline;
2. trained head before calibration;
3. trained head with cross-fitted calibration;
4. abstention coverage versus error rate at several thresholds.

## Lab 2 — Ruflo mod installation and execution

Pinned CLI: `ruflo@3.56.3`.

The sandbox is `ruflo-mod-lab/`. It was initialized using:

```bash
npx -y ruflo@3.56.3 init \
  --minimal \
  --no-global \
  --no-plugin-install \
  --no-signup \
  --no-skills-sh \
  --no-codex-detect
```

This successfully created the Ruflo runtime and enabled these project mods in
`.claude/settings.json`:

- `ruflo-mods@ruflo`;
- `ruflo-swarm@ruflo`;
- `ruflo-console@ruflo`.

Inspect the installation:

```bash
npx -y ruflo@3.56.3 mods status
npx -y ruflo@3.56.3 mods doctor
```

### Observed result in this environment

The project configuration and install record passed. Actual mod loading could
not be exercised because this execution environment has no Claude Code binary,
so the Ruflo marketplace was not cloned and function hooks could not start.

### Complete execution on the laptop

From `ruflo-mod-lab/`, using Claude Code 2.1.287 or later:

```bash
claude plugin marketplace add ruvnet/ruflo --scope project
claude plugin install ruflo-mods@ruflo --scope project
claude plugin install ruflo-swarm@ruflo --scope project
claude plugin install ruflo-console@ruflo --scope project
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

Start one trusted interactive Claude Code session in the directory, then run:

```bash
npx -y ruflo@3.56.3 mods status
npx -y ruflo@3.56.3 mods doctor
```

Success means the marketplace and all three plugins are loadable, function
hooks are enabled, and `last mod start` records a real start. Review mod source
before allowing it to run with account permissions.

## Interpretation

The two labs expose a common rUv design principle: activation is governed.
Typesafe separates label admission from promotion of a decision head; Ruflo
separates configuration from a trusted host actually loading and executing a
mod. In both cases, a successful installation is not the same as verified live
behaviour.
