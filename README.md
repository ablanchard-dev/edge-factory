# edge-factory

A **systematic edge-validation machine** for quantitative trading research. It
generates candidate strategies, backtests them with realistic costs, and runs them
through a rigorous statistical **critic** whose entire purpose is to **kill false
edges before you ever believe in them**.

> ⚠️ **The honest headline:** across the hypotheses it judged (66 verdicts are recorded in
> the committed research files), this machine found **no
> robust, tradable edge** — and that is the point. Its value is the *discipline*: it
> has repeatedly killed strategies that looked profitable but were just noise. In
> quant research, a tool that reliably says "no" is worth more than one that flatters
> your ideas.
>
> That headline is a test, not a claim: `test_readme_promises.py` reads the committed
> verdict files and fails if the count drifts, if any entry lacks a verdict, or if a
> single hypothesis ever comes back `pass: True` — in which case this paragraph has to be
> rewritten. A good result that leaves the README lying is still a README that lies.

## What it does

- **Generates hypotheses** — a systematic generator plus an optional LLM agent that
  proposes strategies through a **safe DSL** (no arbitrary code execution).
- **Backtests realistically** — sourced slippage/borrow costs, `exec_lag=1` for
  live parity (no look-ahead, no free fills).
- **Judges with a critic** (`verdict.evaluate_edge`) — a strategy passes only if every
  gate that ran says yes:
  - **Beta-neutrality** (always) — the edge must not just be hidden market exposure.
  - **DSR** (always) — Deflated Sharpe Ratio, deflated by the real number of hunters tried
    and by the measured variance of their Sharpe ratios (in the unit of the returns: a
    fixed variance made the gate unpassable on hourly bars).
  - **Convexity / tail** (always) — kills disguised short-volatility.
  - **Permutation test** — the strategy is re-run on bars whose returns are shuffled
    (timing destroyed); it must beat 95% of 200 shuffles. Run for every bar-based family
    (cross-sectional, lead-lag); funding and liquidation families are not bar-based.
  - **PBO / CSCV** — only when a hunter supplies a trial matrix. Every verdict records
    `gates_applied`, so a pass never implies a gate that did not run.
- **Pulls real data** — adapters for Hyperliquid (perps) and equities (Yahoo, adj-close).

See [`CAHIER_DES_CHARGES.md`](CAHIER_DES_CHARGES.md) for the full spec and
[`FINDINGS.md`](FINDINGS.md) for what was tested and why each angle was refuted.

## Why it exists

Most retail "backtests" lie to you: multiple-testing, overfitting, hidden beta,
unrealistic fills. edge-factory was built to make self-deception *hard*. Roughly a
dozen strategy families (copy-trading, technical, new-listing, cross-sectional
momentum/reversal, lead-lag, funding…) were all refuted by the critic — including a
cross-sectional 12-month-momentum signal that looked promising in early hand-picked
runs but collapsed on a clean decisive test over the real S&P 600 universe
(`xsm_120_0.33` in `_xs_research.json`: t_alpha=-0.44, DSR=0.27 vs the 0.95 gate).
The CSCV/PBO matrices for that run are gitignored, so only the gate outputs are
persisted (`pbo` is `null` in the committed records).

## Stack

`Python` (pure, ~10k lines) · `numpy` · `pandas` · `httpx` ·
`hyperliquid-python-sdk` · custom-from-scratch GBM & ridge · no heavyweight ML deps

## Run

```bash
pip install -r requirements.txt pytest
python selftest.py        # proof the critic works, offline, < 1 s (see below)
python -m pytest -q       # the test suite, no network
python run_hunt.py        # full hunt on the live Hyperliquid perp universe (60 days, 1h)
python run_autonomous.py  # optional: LLM proposes DSL hypotheses (needs the claude CLI)
```

`selftest.py` judges 200 pure-noise strategies and keeps the best one (maximal data
mining), then a planted edge and a realistic, partly market-exposed one. The block below is
not a transcript: a test runs `selftest.py` and fails if its output stops matching, so the
published result cannot drift away from the program:

```json
{
  "best_of_noise_rejected": true,
  "noise_survivor_rate": 0.0,
  "planted_edge_detected": true,
  "realistic_edge_detected": true,
  "pass": true
}
```

It fails both ways: a critic that passes everything lets noise through (`noise_survivor_rate`
1.0), one that rejects everything misses the planted edge. Both mutations were run.

`hunt.py` and `autonomous.py` are the libraries behind these entry points; running them
directly does nothing. Without a Coinalyze key in `~/.coinalyze_key`, the hunt skips the
liquidation and open-interest families and judges the rest.

A run on 17 Sept 2026 (60 days of 1h bars, 10 families): 0 survivors. All nine bar-based
families also failed the permutation test. The closest, delta-neutral funding carry, had a
significant residual alpha (t = 4.27) and a DSR of 0.93, just under the 0.95 gate.

> Modules are flat at the repo root (`import adapter`, `from critic import ...`).
> Datasets are not included (`numerai_data/`, parquet files are gitignored).

## Layout

```
*.py                       # 75 modules + 44 test files (checked by tests, not by hand): generator, critic, backtest, gbm,
                           #   ridge, metrics, neutralize, hypothesis_dsl, llm_hypothesis,
                           #   adapters (hl, equities), signals (obi, funding, liq, …)
app/services/hl_api/       # vendored Hyperliquid data client (InfoClient)
CAHIER_DES_CHARGES.md      # full specification
FINDINGS.md                # tested hypotheses & refutations
```

---

*Solo project — autodidact. The deliverable is the machine and the discipline, not a P&L.*
