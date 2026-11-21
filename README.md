# BlankSlate Valuation Calculator

**Live application → https://blankslate-valuation-triamirullah.streamlit.app**

A company-agnostic valuation calculator. It holds no company-specific logic: any listed company is
valued by filling one standard input template, which the application itself provides. It combines a
discounted cash-flow model and a relative valuation, chooses between them through written decision
rules, and produces a fair-value range, an upside against the market price, a recommendation, and a
risk register stating the level at which each recommendation would reverse.

Built for MM6026 Digital Business Valuation, SBM ITB — Tri Amirullah, 29125361.

---

## What it does

- **Two methods, run independently.** A ten-year FCFF discounted cash-flow model, and a relative
  valuation on EV/Revenue, EV/EBITDA, P/E and P/B. Enterprise values are converted to equity
  through the same claims bridge in both, so the two are comparable.
- **A financial-firm mode that switches itself on.** For a bank, FCFF and WACC are disabled, equity
  is valued with an excess-return model, and the EV multiples are dropped.
- **Six measured rules choose the weighting.** Each factor tilts from −2, favouring multiples, to
  +2, favouring intrinsic value, from measured data rather than judgement. The weight on intrinsic
  value is `clip(50% + 5% × total tilt, 20%, 80%)`.
- **Peers are filtered by rule.** Non-positive denominators are dropped; for P/E, a peer whose net
  income exceeds its EBIT is dropped because the earnings carry a one-off gain; outliers beyond
  1.5 × IQR go; a multiple needs three valid peers to be used. Every exclusion is shown with its
  reason.
- **Thirty validation checks** run on every calculation, covering missing inputs, unit errors,
  implausible terminal growth, invalid multiples and the enterprise-to-equity reconciliation.
- **A risk register that solves for break-evens** — the level at which each driver alone reverses
  the recommendation — rather than listing risks without quantities.

## Five companies are preloaded

ICBP (PT Indofood CBP Sukses Makmur) and BBCA (PT Bank Central Asia), both valued at
30 September 2026 from reconciled filings, plus three synthetic cases: a stable consumer-staples
firm, a loss-making platform and a bank. Switching between them in the sidebar shows the method
weighting changing by itself, with no figure altered by hand.

Any other company is valued by downloading the blank input template from the sidebar, filling it,
and uploading it.

## How the engine is validated

The valuation logic exists twice, written separately as Excel formulas and as Python. A parity test
runs both on identical inputs and compares 47 outputs per company for a non-financial firm and 41
for a bank, across six cases. The comparison covers the derived history, discount rates, assumption
defaults, scenario values, the relative valuation, the six decision tilts and resulting weights, the
fair-value range, upside, recommendation, confidence, which validation checks fire, and the stated
reason for every multiple. The last run returned every output identical in every case.

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Python 3.10 or later. No account, API key or subscription is needed, and this route runs entirely
offline, so the same input file always reproduces the same valuation.

## Layout

| Path | Contents |
|---|---|
| `app.py` | The application: eleven tabs from data entry to export |
| `engine/` | The calculation engine — `core.py` (valuation), `checks.py` (validation), `risks.py` (break-evens), `io.py` (template read and write) |
| `data/` | The two reported companies as plain data, with a source note on every input |
| `excel/` | The second implementation: the workbook generator and its VBA module |
| `examples.py` | The preloaded cases |
| `docs/USER_GUIDE.md` | Operating instructions, also shown in the application's Guide tab |

The full specification of every default, threshold and formula, the validation report and the AI
disclosure accompany the submitted package.
