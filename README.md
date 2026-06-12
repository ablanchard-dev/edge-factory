# edge-factory

A **systematic edge-validation machine** for quantitative trading research. It
generates candidate strategies, backtests them with realistic costs, and runs them
through a rigorous statistical **critic** whose entire purpose is to **kill false
edges before you ever believe in them**.

> ⚠️ **The honest headline:** across ~80+ tested hypotheses, this machine found **no
> robust, tradable edge** — and that is the point. Its value is the *discipline*: it
> has repeatedly killed strategies that looked profitable but were just noise. In
> quant research, a tool that reliably says "no" is worth more than one that flatters
> your ideas.

## What it does

- **Generates hypotheses** — a systematic generator plus an optional LLM agent that
  proposes strategies through a **safe DSL** (no arbitrary code execution).
- **Backtests realistically** — sourced slippage/borrow costs, `exec_lag=1` for
  live parity (no look-ahead, no free fills).
- **Judges with a 3-gate critic** — a strategy only "passes" if it survives all three:
  - **DSR** (Deflated Sharpe Ratio) — accounts for how many strategies were tried.
  - **Beta-neutrality** — the edge must not just be hidden market exposure.
  - **PBO / CSCV** — Probability of Backtest Overfitting via combinatorially-symmetric
    cross-validation.
- **Pulls real data** — adapters for Hyperliquid (perps) and equities (Yahoo, adj-close).

See [`CAHIER_DES_CHARGES.md`](CAHIER_DES_CHARGES.md) for the full spec and
[`FINDINGS.md`](FINDINGS.md) for what was tested and why each angle was refuted.

## Why it exists

Most retail "backtests" lie to you: multiple-testing, overfitting, hidden beta,
unrealistic fills. edge-factory was built to make self-deception *hard*. Roughly a
dozen strategy families (copy-trading, technical, new-listing, cross-sectional
momentum/reversal, lead-lag, funding…) were all refuted by the critic — including a
12-month-momentum signal that looked promising (t=1.69) but was killed by a clean
decisive test (t=0.88, PBO 0.84 → overfit).

## Stack

`Python` (pure, ~10k lines) · `numpy` · `pandas` · `httpx` ·
`hyperliquid-python-sdk` · custom-from-scratch GBM & ridge · no heavyweight ML deps

## Run

```bash
pip install -r requirements.txt
python hunt.py          # run the hunters / validation pipeline
python autonomous.py    # autonomous LLM-driven hypothesis loop (optional)
```

> Modules are flat at the repo root (`import adapter`, `from critic import ...`).
> Datasets are not included (`numerai_data/`, parquet files are gitignored).

## Layout

```
*.py                       # 110+ flat modules: generator, critic, backtest, gbm,
                           #   ridge, metrics, neutralize, hypothesis_dsl, llm_hypothesis,
                           #   adapters (hl, equities), signals (obi, funding, liq, …)
app/services/hl_api/       # vendored Hyperliquid data client (InfoClient)
CAHIER_DES_CHARGES.md      # full specification
FINDINGS.md                # tested hypotheses & refutations
```

---

*Solo project — autodidact. The deliverable is the machine and the discipline, not a P&L.*
