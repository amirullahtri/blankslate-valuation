# Access instructions

The model is a web application. It is already running at the address below, and it can also be run
locally from the source in this package. Neither route needs a subscription, an account or an API
key, and no figure in it comes from a paid feed at run time.

---

## A. Web application

**Hosted** — https://blankslate-valuation-triamirullah.streamlit.app

Nothing to install and nothing to sign in to. The application is public; opening the link is enough.
An internet connection is needed for this route only.

**Locally** — from this folder (`2_Aplikasi`):

```bash
pip install -r requirements.txt
streamlit run app.py
```

The application opens at `http://localhost:8501`. Python 3.10 or later. This route runs entirely
offline, so the same input file always reproduces the same valuation.

### What to try first

1. The sidebar opens with a built-in example. Five are preloaded: ICBP, the company reported here;
   BBCA, a bank; and three synthetic cases. Switch between them to see the method weights change by
   themselves: a stable firm leans on the discounted cash-flow model, a loss-making one leans on
   multiples, and a bank switches to the excess-return model with the EV multiples disabled.
   Nothing is entered to make that happen; the six rules in **Method selection** decide it.
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

## B. Excel workbook — the second implementation

The workbooks in `1_Excel` are not an alternative deliverable. They are the same valuation logic
written again, independently, as Excel formulas, so that the application can be checked against
something other than itself. Section C is that check.

Open any of them and every figure is live; there is nothing to enable and no macro to run:

| File | Holds |
|---|---|
| `BlankSlate_Valuation_blank.xlsx` | The empty calculator |
| `BlankSlate_Valuation_ICBP.xlsx` | ICBP, the company reported here |
| `BlankSlate_Valuation_BBCA.xlsx` | BBCA, in financial-firm mode |
| `BlankSlate_Valuation_example.xlsx` | A synthetic case |
| `BlankSlate_input_template.xlsx` | The blank input template, for any other company |

Sheet colours mark the four layers: orange tabs are inputs, grey tabs are calculations, and the
Dashboard and Key risks are outputs. Calculation sheets hold formulas only.

`BlankSlateMacros.bas` is included as readable source. It adds buttons to the Dashboard for
importing a template, switching scenarios, solving break-evens through Goal Seek and exporting a
summary. It is optional and no part of the validation depends on it: the parity test recalculates
formulas only, and the figures above are produced without it. To use it, import the module through
the VBA editor and save the workbook as `.xlsm`.

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
