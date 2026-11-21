# BlankSlate Valuation Calculator — User Guide

A company-agnostic valuation calculator. It holds no company-specific logic: any listed company is
valued by filling one standard input template. The same calculation rules run in two places — an
Excel/VBA workbook and a web application — and the two are tested against each other.

---

## 1. Setup

### Option A — Excel workbook (no installation beyond Excel)

1. Open `1_Excel/BlankSlate_Valuation.xlsm` and allow macros when prompted.
2. If macros are blocked: right-click the file, Properties, tick **Unblock**, then reopen.
3. On the **Dashboard**, run the macro `SetupButtons` once (Developer > Macros) to place the
   buttons. Afterwards everything is driven by those buttons.

Requires Microsoft Excel for Windows or macOS. VBA does not run in Excel on the web or in Google
Sheets. The VBA source is also supplied as readable text in `1_Excel/BlankSlateMacros.bas`.

### Option B — Web application

```bash
cd 2_Aplikasi
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Requires Python 3.10 or later.

### Access, subscriptions and connectivity

| Item | Requirement |
|---|---|
| Subscription | **None.** No paid data service, no licence beyond Excel. |
| API keys | **None.** |
| Internet | **Not required.** Both the workbook and the application compute entirely offline. |
| Optional only | A helper script that pre-fills peer data from a free, unofficial market-data library needs internet. The model never depends on it; peer data can always be typed into the template. |

Because nothing is fetched at run time, results are reproducible: the same input file always
produces the same valuation.

---

## 2. Inputs

Inputs live in six places, kept deliberately separate from the calculations.

| Sheet / tab | What goes in it |
|---|---|
| **Company** | Name, ticker, sector, financial-firm flag, currency, unit, shares outstanding, share price, valuation date, and the date the peer market values were taken |
| **Financials** | 3–6 periods of income statement, balance sheet and cash-flow lines, oldest on the left |
| **Market** | Risk-free rate, equity risk premium, country risk premium, beta and beta method, credit spread, tax rate, target D/V |
| **Peers** | Up to 15 comparable companies, in the same currency and unit as the target |
| **Assumptions** | Overrides only. Leave blank to use the engine's own default |
| **Risks** | Risks only the analyst can know: customers, regulation, FX, supply, key people |

Three rules that prevent most errors:

1. **One unit for every figure.** Set it once on the Company sheet (`unit`, e.g. 1e9 for billions)
   and use it for the company and every peer.
2. **Leave a cell blank when a figure is unknown.** Never type 0 — the model treats 0 as a real
   zero and blank as "not available".
3. **Fill the Source column.** Each input line has one; it is carried into the exported results.

The valuation date, the share price and the shares outstanding decide the comparison with the
market price, so they are editable directly in the application as well as in the template.

Two fields are easy to skip and both change what the model is allowed to conclude:

- **`peers_as_of` (Company).** The date the peer market capitalisations were read. It must equal the
  valuation date. Market data pages quote today's price, so a peer set pulled a few weeks after the
  valuation date carries whatever the sector did in between straight into the peer medians. The
  model compares the two dates and warns when they differ. To fix it, scale each peer's market
  capitalisation by its own closing price on the valuation date over its closing price on the date
  you read it; share counts rarely move enough to matter over a few weeks.
- **`goodwill_intangibles` (Financials).** Goodwill plus other intangible assets. Nothing in the
  valuation uses it directly; it exists so the model can test whether P/B means anything for this
  company. P/B only compares like with like when the target and its peers carry intangibles on the
  same basis, and a book built by acquisition has an inflated denominator, which inflates the value
  P/B returns. Above 30% of book equity the model says so and reports the tangible book per share.
  Leave it blank and the model will tell you the test could not be run, rather than passing
  silently.

---

## 3. Updates

The calculation structure never has to be rebuilt. Updating means replacing data, not formulas.

### In the workbook

| Button | What it does |
|---|---|
| **Import template** | Loads a filled standard template for any company |
| **New company** | Clears every input — the blank calculator |
| **Refresh all** | Recalculates, solves what the price implies, rebuilds the sensitivity grids and the break-even cells, stamps the time |
| **Bear / Base / Bull** | Switches the scenario shown on the dashboard |
| **Validate inputs** | Highlights missing required inputs and summarises the checks |
| **Key risks** | Rebuilds the break-even cells on the Key risks sheet |
| **Export summary** | Saves a PDF and a values-only workbook, and appends a row to the Log |

### In the application

Upload a filled template in the sidebar, or pick a built-in example. Price, shares and valuation
date are editable on the **Data & history** tab; assumptions on the **Assumptions** tab. Every
change recalculates immediately — valuations, scenarios, sensitivity, dashboard and recommendation.

Use **Save project** on the Export tab to write the current inputs and overrides back to a
template, and **Open project** in the sidebar to resume from it later.

---

## 4. Calculations

Full rules are in `4_Dokumen/SPEC.md`. In outline:

**Intrinsic value.** Non-financial firms: a 10-year FCFF discounted cash-flow model. Revenue growth
fades from year 1 to the terminal rate; the EBIT margin moves to its target by year 5; reinvestment
is derived from growth and the sales-to-capital ratio; the terminal value uses a reinvestment rate
of g ÷ ROIC. Enterprise value is bridged to equity by adding cash and non-operating assets and
deducting debt, leases and minority interest. Financial firms switch to an excess-return model on
book value, and FCFF and WACC are not used.

**Relative value.** Peer multiples (EV/Revenue, EV/EBITDA, P/E, P/B; equity multiples only for
financial firms). A peer is excluded when its denominator is not positive; with five or more valid
values, outliers beyond 1.5 × IQR are excluded; a multiple needs at least three valid peers and a
positive target metric before it is used. EV multiples are converted to equity with exactly the
same net claims as the DCF.

**Method selection.** Six factors are measured from the data — industry, maturity and growth,
profitability and cash-flow stability, information availability, peer availability, capital
structure — each tilting from −2 (favour relative) to +2 (favour intrinsic). The total tilt sets
the proposed weight. The model proposes; the analyst may override the weights and the override is
shown beside the proposal.

**Defaults.** Every assumption starts from a value derived from the company's own data (for
example, year-1 growth from the historical CAGR, bounded). The rule behind each default is
displayed, and any override is recorded.

---

## 5. Outputs

| Output | Where |
|---|---|
| Value by method, with ranges | Dashboard football field |
| Fair-value range and central estimate | Dashboard |
| Comparison with the market price on the valuation date | Dashboard |
| Implied upside or downside | Dashboard |
| Recommendation with its decision criteria | Dashboard (BUY / HOLD / SELL, thresholds adjustable) |
| Key risks with break-even levels | Key risks |
| Method-selection trace | Method selection / Decision |
| Validation checks | Checks |

**Exports.** The application writes a results workbook, a saved project file, a full JSON record,
and an Excel engine pre-filled with the current company. The workbook writes a PDF of the
dashboard, a values-only workbook, and one row per export in the Log sheet.

**Errors block the recommendation.** When any check is at ERROR severity, the dashboard shows
NO RECOMMENDATION until it is resolved.

---

## 6. Known limitations

**Structural**

- The template holds 3–6 reporting periods and up to 15 peers. Beyond that the input layout would
  have to be extended.
- One currency per valuation. Peers must be reported in the same currency and unit; the model warns
  when they differ but does not convert.
- A single consolidated entity is valued. Sum-of-the-parts across segments is not supported.

**Methodological**

- Where fewer than three valid peers exist on every multiple, relative valuation is switched off and
  the intrinsic model carries the full weight. An industry-median fallback is not implemented.
- Dilution from options, warrants and convertibles is not modelled beyond the share count entered.
- A dividend discount model is not offered; financial firms use the excess-return model.
- Scenarios move a fixed set of levers by fixed amounts; they are not full re-forecasts.
- Terminal value is sensitive to the spread between the terminal discount rate and terminal growth.
  The model warns when that spread is narrow or when terminal value exceeds 85% of enterprise value,
  but it cannot make the assumption safer.

**Between the two engines**

- The application solves a WACC break-even that the workbook does not, because WACC there is
  computed rather than entered and Goal Seek cannot reach it. Everything else matches: the parity
  test in `3_Validasi/` compares 34 outputs across four test companies.

**Data**

- Historical statements are entered from published filings. The model does not audit them; it
  checks internal consistency (units, period order, equity bridge) only.
- Market inputs are stated as of the valuation date and do not refresh on their own.

---

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "NO RECOMMENDATION" on the dashboard | One or more ERROR checks. Open Checks (or run Validate inputs) and fix what is listed. |
| Implied P/B or P/S flagged as implausible | Unit mismatch. Check `unit` and `share_unit` on the Company sheet. |
| A multiple is marked unusable | Fewer than three valid peers, or the target's own metric is not positive. Both are stated on the Relative tab. |
| Terminal growth error | Terminal growth must sit below the terminal discount rate. Lower it, or revisit the risk-free rate. |
| Macros do nothing | The file is not .xlsm, macros are disabled, or the file is blocked. See Setup. |
| "Run the macro Refresh all" on Key risks | The break-even cells are filled by Goal Seek; press Refresh all. |
