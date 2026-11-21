# Access instructions

Two ways to run the model. Neither needs an internet connection, a subscription or an API key.

---

## A. Web application

**Hosted** — open the link on the cover of the report, if one is given. Nothing to install.

**Locally** — from this folder (`2_Aplikasi`):

```bash
pip install -r requirements.txt
streamlit run app.py
```

The application opens at `http://localhost:8501`. Python 3.10 or later.

### What to try first

1. The sidebar opens with a built-in example. Switch between the three to see the method weights
   change by themselves: a stable firm leans on the discounted cash-flow model, a loss-making one
   leans on multiples, and a bank switches to the excess-return model with EV multiples disabled.
2. **Data & history** — change the share price. Everything recalculates, including the
   recommendation.
3. **Assumptions** — tick *override* on any line. The engine's own default and the rule behind it
   stay on screen beside your value.
4. **Method selection** — the six factors, each with the measurement that produced it. Override the
   weights at the bottom if you disagree.
5. **Checks** — a check at ERROR severity blocks the recommendation entirely.
6. **Export** — results workbook, saved project, JSON, or an Excel engine pre-filled with the
   company on screen.
7. **Guide** — the full operating instructions, the same text as the user guide.

To value a different company: download the blank template from the sidebar, fill it, and upload it
under *Open project / upload template*.

---

## B. Excel workbook

The macro-enabled workbook is built from the files in `1_Excel`, because an `.xlsm` cannot be
produced without Excel itself: follow `1_Excel/HOW_TO_MAKE_THE_XLSM.txt`, which also lists the
checks to run once it opens. In short: open `BlankSlate_Valuation_blank.xlsx` (or
`BlankSlate_Valuation_ICBP.xlsx` for a copy already filled with the reported company), import
`BlankSlateMacros.bas` through the VBA editor, and save as `.xlsm`.

Then enable macros. If Windows blocks the file, right-click it, choose Properties, tick
**Unblock**, then reopen.

Run `SetupButtons` once (Developer > Macros) to place the buttons on the Dashboard. After that:
**Import template**, **New company**, **Refresh all**, **Validate inputs**, **Bear / Base / Bull**,
**Key risks**, **Export summary**.

The VBA source is also included as readable text in `BlankSlateMacros.bas`.

Sheet colours mark the four layers: orange tabs are inputs, grey tabs are calculations, and the
Dashboard and Key risks are outputs. Calculation sheets contain formulas only and are never written
to by the macros.

---

## C. Checking that the engine is validated

From `3_Validasi`:

```bash
python3 parity.py
```

It builds the Excel workbook from the same inputs used by the Python engine, recalculates it with
LibreOffice, and compares every output of the two against each other across six test cases: three
synthetic companies, the two real companies, and one run with the method weights overridden by
hand. Per case it compares 47 outputs for a non-financial firm and 41 for a financial one, where
the difference is the two EV multiples a bank does not use. The comparison covers the derived
history, the discount rates, the assumption defaults, the three scenario values, the relative
valuation, the six decision tilts and the resulting weights, the fair-value range, the upside, the
recommendation and its confidence, which validation checks fire, and the usability and stated
reason for each multiple. `parity_report.txt` holds the result of the last run.

---

## Requirements summary

| | |
|---|---|
| Subscription or paid data | None |
| API key | None |
| Internet at run time | Not required |
| Excel | Required for the workbook only (Windows or macOS desktop; VBA does not run on Excel for the web) |
| Python | 3.10+ for the application and the parity test |
| LibreOffice | Only to rerun the parity test |
