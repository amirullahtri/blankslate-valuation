"""BlankSlate Valuation Calculator - web application (Streamlit).
Run locally:  streamlit run app.py
"""
import copy
import datetime as dt
import json
import os

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from engine import run, SECTORS, DEFAULT_SETTINGS as DS
from engine.core import _num
from engine.io import blank_template, read_template, export_results, ASSUMPTION_FIELDS
from engine.checks import REQUIRED_META, REQUIRED_FIN, REQUIRED_MKT, CHECK_CODES

st.set_page_config(page_title="BlankSlate Valuation Calculator", page_icon="📐", layout="wide")

# "Paprika & Ink" — the same palette as the deck, so the tool and the report read as one piece of
# work. Each colour carries one meaning: paprika is our value, petrol is the market's own price.
INK, PAPRIKA, PETROL = "#1F2A30", "#A83D24", "#30606B"
OLIVE, GOLD, TAUPE = "#5E7A52", "#D8A33C", "#A99C88"
CREAM, SAND, BORDER, STONE = "#F6F0E6", "#EFE7D9", "#DCD2C2", "#56666C"
# Aliases kept so the rest of the file reads unchanged.
TEAL, ORANGE, RED, GREY = PAPRIKA, GOLD, PETROL, TAUPE

pio.templates["blankslate"] = go.layout.Template(layout=dict(
    font=dict(color=INK, size=12),
    # White panels rather than transparent: a transparent chart inherits the viewer's theme
    # background, and ink axis labels then sit on a dark ground. A self-contained panel reads
    # the same whichever theme is chosen, and matches the white cards elsewhere.
    paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
    colorway=[PAPRIKA, OLIVE, PETROL, GOLD, STONE, TAUPE],
    xaxis=dict(gridcolor="#E2D9C9", zerolinecolor=BORDER, linecolor=BORDER),
    yaxis=dict(gridcolor="#E2D9C9", zerolinecolor=BORDER, linecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
))
pio.templates.default = "blankslate"

st.markdown(f"""
<style>
.block-container {{padding-top: 1.2rem;}}

/* The page header: one solid block of ink, the way every slide in the deck opens. */
.band {{background:{INK}; border-radius:12px; padding:18px 22px 16px 22px; margin-bottom:14px;}}
.band .n {{font-size:1.55rem; font-weight:800; color:#FFFFFF; line-height:1.15;}}
.band .t {{display:inline-block; background:{PAPRIKA}; color:#FFFFFF; font-size:.72rem;
           font-weight:700; letter-spacing:.09em; padding:3px 9px; border-radius:6px;
           margin-bottom:8px;}}
.band .s {{font-size:.80rem; color:#A99C88; margin-top:7px;}}

/* The call, as a filled card rather than coloured text. */
.call {{border-radius:12px; padding:16px 18px; color:#FFFFFF;}}
.call .c {{font-size:2.5rem; font-weight:800; line-height:1;}}
.call .f {{font-size:.82rem; opacity:.88; margin-top:4px;}}

/* Dashboard cards. Each one carries a small visual of its own, so a figure arrives with the
   context that makes it mean something: where the price sits inside the fair-value range, which
   way revenue has gone, how the two approaches were weighted. Every card sets its own background
   and text colour, so it reads the same in a light or a dark theme. */
.dgrid {{display:grid; grid-template-columns:1.25fr 1fr 1fr 1fr; gap:12px; margin-bottom:6px;}}
.dc {{background:#FFFFFF; border:1px solid {BORDER}; border-radius:12px; padding:14px 16px;
      color:{INK};}}
.dc .l {{font-size:10.5px; letter-spacing:.06em; text-transform:uppercase; color:{STONE};}}
.dc .v {{font-size:25px; font-weight:800; margin-top:3px; white-space:nowrap;
         font-variant-numeric:tabular-nums;}}
.dc .ft {{font-size:10.5px; color:{STONE}; margin-top:6px; line-height:1.35;}}
.dc.verdict {{display:flex; flex-direction:column; justify-content:center; color:#FFFFFF;}}
.dc.verdict .l {{color:#F2CFC2;}}  .dc.verdict .v {{color:#FFFFFF; font-size:42px; line-height:1;}}
.dc.verdict .ft {{color:#F2CFC2; font-size:11.5px;}}
.scale {{position:relative; height:9px; border-radius:5px; margin-top:11px;
         background:linear-gradient(90deg,#E6B6A3,{PAPRIKA});}}
.scale b {{position:absolute; top:-4px; width:3px; height:17px; background:{INK};
           border-radius:2px;}}
.sbars {{display:flex; align-items:flex-end; gap:5px; height:38px; margin-top:9px;}}
.sbars i {{flex:1; background:#E3D9C9; border-radius:2px 2px 0 0;}}
.sbars i.hi {{background:{PAPRIKA};}}
.ring {{float:right; margin-top:-30px;}}
/* The six factors, compact, beside the football field: the decision rule in one glance. */
.tf {{display:flex; align-items:center; gap:9px; margin-bottom:7px; font-size:11.5px;
      color:{INK};}}
.tf .id {{width:112px; color:{STONE};}}
.tf .tk {{position:relative; flex:1; height:9px; background:#E3D9C9; border-radius:5px;}}
.tf .tk b {{position:absolute; top:0; height:9px; border-radius:5px;}}
.tf .tv {{width:26px; text-align:right; font-weight:700;}}
.kpi {{background:#FFFFFF; border:1px solid {BORDER}; border-radius:10px; padding:12px 14px;
       height:100%;}}
.kpi .l {{font-size:.72rem; color:{STONE}; text-transform:uppercase; letter-spacing:.03em;
          line-height:1.2;}}
/* A price must never break across two lines: "1,500" split after the comma reads as two numbers.
   The figure stays on one line and shrinks with the viewport instead. */
.kpi .v {{font-size:clamp(.88rem, .78vw + .42rem, 1.45rem); font-weight:700; color:{INK};
          margin-top:3px; white-space:nowrap; font-variant-numeric:tabular-nums;}}

/* Tabs: the active one is marked by the accent, not by a grey box. */
.stTabs [data-baseweb="tab-list"] {{gap:2px; border-bottom:1px solid {BORDER};}}
.stTabs [data-baseweb="tab"] {{padding:8px 14px;}}
/* Paprika carries enough contrast on both a cream and a near-black ground, so the active tab
   is marked the same way in either theme. */
.stTabs [aria-selected="true"] {{color:{PAPRIKA} !important; font-weight:700;
                                 border-bottom:3px solid {PAPRIKA};}}
[data-testid="stDataFrame"] {{border:1px solid {BORDER}; border-radius:8px;}}

/* Tints below assume a light page. They are applied only to a viewer in a light colour scheme;
   a viewer in dark keeps Streamlit's own surfaces, which already carry readable text. */
@media (prefers-color-scheme: light) {{
  [data-testid="stSidebar"] {{background:{SAND};}}
  .stTabs [data-baseweb="tab"] {{color:{STONE};}}
}}
</style>""", unsafe_allow_html=True)

# The in-application user guide. It lives here, not in a separate file, so the Guide tab
# cannot go blank because one file of a deployment was missed. build_package.py writes it
# out to the submission package from this string, so there is one source of truth.
APP_GUIDE = """# How to use this calculator

This is a blank valuation calculator. It holds no logic specific to any one company: it values
whichever company you load, by the same rules, and it shows you the rule behind every number it
produces. You can read a result in a minute, or audit how it was reached.

Nothing here is a recommendation to buy or sell anything. The calculator applies stated rules to
the data you give it; the judgement about whether those rules and that data suit your purpose
remains yours.

---

## 1. Load a company

The sidebar is where data comes in, and there are three ways.

**A built-in example.** Five are loaded and need nothing from you. **ICBP** is the company the
accompanying report analyses. **BBCA** is a bank, carried to show the calculator switching to a
different valuation model on its own. The three synthetic cases are a stable consumer-staples
firm, a loss-making growth platform, and a bank. Move between them and watch the method weights
on the Dashboard change without you touching anything: that is the decision engine working.

**Your own company.** Press **Blank input template** in the sidebar, fill the file, then switch
the data source to *Open project / upload template* and upload it. The template has one sheet per
kind of input and tells you the units it expects.

**A project you saved earlier.** The Export tab writes a project file that carries your inputs,
your overrides and your settings. Upload it the same way and you resume exactly where you stopped.

**Nothing has to be started.** The valuation recalculates the moment a file is read, and again
on every change you make afterwards, so there is no step between loading data and having an answer.

**Recalculate now**, in the sidebar, forces a fresh pass and stamps the time; the stamp appears
under the recommendation. It is there so the calculation can be seen happening rather than taken
on trust, not because anything waits for it — press it or ignore it, the figures are the same.

When a file loads, the sidebar confirms it by name and says how many periods and peers it found,
and the header names the source it is showing. Those are the signs that an upload took effect. If
the figures look unchanged afterwards, read the source line in the header before assuming nothing
happened: a template written out from a built-in case reproduces that case exactly, which is the
point of it.

### The minimum the calculator needs

It will not compute until these are present, and it tells you which are missing rather than
guessing:

| Group | Fields |
|---|---|
| Company | name, sector, currency, unit, shares, share unit, share price, valuation date |
| Financials | revenue, EBIT, net income, equity attributable to parent, cash, total debt |
| Market | risk-free rate, equity risk premium |

Everything else is optional. Where an optional input is absent the calculator derives a default
and names the rule it used, so a sparse input file still produces a result you can trace.

---

## 2. Read the answer

**Dashboard** is the whole valuation on one screen.

The coloured card carries the call, the upside against the market price, and a confidence level.
The four cards beside it are the market price, the central fair value, the upside, and the
fair-value range.

The **football field** underneath is the part worth your attention. Each bar is one method's
range, the dot inside it is that method's central value, and the dashed line is the market price.
A market price sitting outside every bar is telling you something; so is one method disagreeing
with the rest.

The donut shows how the two approaches were weighted, and the panel beside it shows what the
market price implies — the growth rate the company would have to deliver to be worth today's
price. Where no growth rate in the search range can reach the price, the calculator says so
plainly instead of returning a number it cannot stand behind.

### What the call means

By default a **BUY** needs upside of 15% or more, a **SELL** needs downside of 15% or more, and
anything between is a **HOLD**. Both thresholds are yours to change, under *Recommendation &
scenario settings* in the sidebar.

Confidence is not a feeling. It falls when the checks raise warnings, when the terminal value
carries most of the enterprise value, or when the two approaches disagree widely.

**A validation error blocks the recommendation entirely.** The calculator will not issue a call on
data it believes is wrong.

---

## 3. Change what you disagree with

Every assumption starts from a default the calculator derived from your data, and every default
shows the rule that produced it.

**Assumptions** lists them. Tick *override* on any line and type your own value; the engine's
default stays on screen beside yours, so the disagreement is visible rather than buried. The
Dashboard, the scenarios and the recommendation recalculate at once.

What you can override: the first-year growth rate, terminal growth, the target operating margin,
sales-to-capital, terminal ROIC, the effective tax rate and the terminal beta — and for a
financial firm, the starting and terminal ROE and the payout ratio. You can also override the
discount-rate inputs directly: the risk-free rate, the equity and country risk premiums, beta, the
pre-tax cost of debt, the marginal tax rate and the target debt ratio.

You can also override **the method weight itself**, at the bottom of the same tab, if you disagree
with how the calculator split the two approaches.

**Data & history** is where you change the data rather than the assumptions: the share price, the
share count, the valuation date, and the date the peer prices were taken. Changing the price
alone is the fastest way to see where the recommendation flips.

---

## 4. Follow the reasoning

These tabs exist so you need not take any number on trust.

**Intrinsic value** shows the ten-year forecast year by year, and the bridge from enterprise value
to equity value: cash and non-operating assets added, debt, leases and minority interest deducted.
Watch the terminal value's share of enterprise value. Above roughly three quarters, the valuation
is mostly a statement about the far future.

**Relative value** shows every multiple, how many peers survived the filters, and why each
excluded peer was dropped. A peer with a non-positive denominator is excluded. Where at least five
peers remain, outliers beyond 1.5 times the interquartile range are excluded. A multiple is used
only if at least three valid peers remain and the company's own metric is positive. Enterprise
multiples are converted to equity value using the same net claims as the cash-flow model, so the
two approaches cannot quietly disagree about the balance sheet.

**Method selection** is the decision engine, exposed. Six factors are measured from the data — not
chosen by hand — and each tilts from −2, meaning trust the multiples, to +2, meaning trust the
cash flows. The weight on the intrinsic approach is then

```
weight = 50% + 5% × (sum of the six tilts),  held between 20% and 80%
```

The table shows each factor's measurement, so you can see what produced each tilt.

**Scenarios & sensitivity** gives a bear, base and bull case with probabilities you control, and
two grids: value against discount rate and terminal growth, and value against first-year growth
and target margin. The grids tell you how fragile the answer is far faster than re-running it.

**Key risks** solves each risk backwards: the level at which the recommendation would reverse. A
break-even is more useful than a worry, because you can judge whether that level is plausible.

---

## 5. Check before you trust it

**Validation** lists everything the calculator noticed, at three severities. Errors block the
recommendation. Warnings do not, but each one names something a reader could reasonably challenge.

Three are worth understanding because they catch the mistakes that most often spoil a comparable
valuation:

- **Peer prices on a different date from the valuation date.** The comparison is then between two
  different markets. The calculator requires the dates to be equal, not merely close.
- **Terminal growth above the risk-free rate.** A company cannot grow faster than the economy
  forever; the risk-free rate is the practical ceiling.
- **An enterprise-to-equity bridge that does not reconcile.** The commonest source of a wrong
  per-share value.

---

## 6. Take it with you

**Export** writes four things: a results workbook with the summary, the method trace, the
intrinsic table, the relative valuation, the checks and the assumptions used; a project file that
restores this session; the full result as JSON; and a spreadsheet engine pre-filled with the
company on screen.

---

## 7. What this calculator cannot do

It values a going concern from reported figures. It does not know anything the statements do not
contain — a pending acquisition, a regulatory change, a key customer about to leave. Those belong
on the Risks sheet of the input template, where you can enter them yourself; they then appear on
the Key risks tab beside the calculated ones.

It cannot tell you that the data you gave it is the wrong data. The checks catch inconsistency,
not inaccuracy.

And it cannot price a control premium, a liquidity discount or a holding-company discount. Where
the market price sits far from the calculated value and no plausible operating assumption closes
the gap, a structural factor of that kind is usually the explanation, and it falls outside the
model.

---

## 8. If something looks wrong

| What you see | What it means |
|---|---|
| "Cannot calculate yet. Missing required inputs" | A field from the table in section 1 is blank. The message names each one. |
| A multiple shows "not usable" | Fewer than three peers survived the filters, or the company's own metric is not positive. The Relative value tab names every exclusion. |
| The recommendation is withheld | A check at error severity is active. Open the Validation tab. |
| No implied growth rate on the Dashboard | No growth path in the search range reproduces the market price. The Key risks tab solves on the discount rate instead. |
| The value moves a long way for a small change | Look at the terminal value's share of enterprise value on the Intrinsic value tab, and at the sensitivity grids. |
"""

PCT_KEYS = {"g1", "g_terminal", "target_margin", "roic_terminal", "eff_tax_start", "roe_start", "roe_terminal", "payout"}


def fmt(v, pct=False, dec=0):
    if v is None:
        return "–"
    return f"{v:.{max(dec,1)}%}" if pct else f"{v:,.{dec}f}"


def kpi(col, label, value):
    col.markdown(f"<div class='kpi'><div class='l'>{label}</div><div class='v'>{value}</div></div>", unsafe_allow_html=True)


def preflight(d):
    miss = [k for k in REQUIRED_META if d["meta"].get(k) in (None, "")]
    miss += [f"Financials: {k}" for k in REQUIRED_FIN
             if not any(_num(x) is not None for x in d["fin"].get(k, []))
             and not (d["meta"].get("is_financial") and k == "ebit")]
    miss += [f"Market: {k}" for k in REQUIRED_MKT if _num(d["market"].get(k)) is None]
    if not d.get("periods"):
        miss.append("Financials: period labels")
    return miss


# ------------------------------------------------------------------ sidebar: data
st.sidebar.title("📐 BlankSlate")
st.sidebar.caption("A blank valuation calculator: load any company's data, get DCF + relative valuation, "
                   "a rule-based method choice and a recommendation.")
src = st.sidebar.radio("Data source", ["Open project / upload template", "Built-in example"], index=1)
if src == "Open project / upload template":
    up = st.sidebar.file_uploader("Filled template or saved project (.xlsx)", type=["xlsx", "xlsm"])
    st.sidebar.caption("The valuation recalculates the moment the file is read — you do not have "
                       "to start it. Recalculate now, below, forces a fresh pass and stamps the time.")
    if up is not None:
        try:
            st.session_state["data"] = read_template(up)
            st.session_state["data_name"] = up.name
        except Exception as e:  # noqa: BLE001
            st.sidebar.error(f"Could not read the template: {e}")
    # Confirm the load explicitly. Without this the screen can look unchanged after an upload --
    # the company name may even be the same as the example that was showing -- and a first-time
    # reader concludes nothing happened.
    _ld = st.session_state.get("data")
    if _ld and st.session_state.get("data_name"):
        _np = len(_ld.get("periods") or [])
        _pr = len(_ld.get("peers") or [])
        st.sidebar.success(
            f"Loaded **{st.session_state['data_name']}**  \n"
            f"{_ld['meta'].get('name') or 'unnamed company'} · {_np} period(s) · {_pr} peer(s) · "
            f"recalculated")
else:
    import examples
    # The two real companies lead, so the application opens on the company the report is about
    # rather than on a synthetic case. The synthetic cases follow; they exist to show the method
    # selection switching, not to be the first thing a reader sees.
    lead = ["ICBP", "BBCA"]
    names = sorted(list(examples.EXAMPLES),
                   key=lambda n: (next((i for i, p in enumerate(lead) if n.startswith(p)), 9), n))
    pick = st.sidebar.selectbox("Example company", names)
    if st.session_state.get("data_name") != pick:
        st.session_state["data"] = copy.deepcopy(examples.EXAMPLES[pick])
        st.session_state["data_name"] = pick
        st.session_state["ovr"] = {}
st.sidebar.download_button("⬇ Blank input template", blank_template(), "BlankSlate_input_template.xlsx",
                           help="Fill this file for any listed company and upload it here.")
# The calculator is reactive: every input change recalculates on its own. This button forces a
# fresh pass and stamps the time, so a reader can see the valuation being produced rather than
# having to take it on trust. It is deliberately not called "Run": nothing here waits for it, and
# a button that implied otherwise would be false the moment it was pressed.
_recalc = st.sidebar.button("↻ Recalculate now", type="primary", width="stretch",
                            help="Not required: the valuation already recalculates on every "
                                 "change. Press it to force a fresh pass and stamp the time.")

d = st.session_state.get("data")
if not d:
    st.title("BlankSlate Valuation Calculator")
    st.info("Upload a filled template or choose an example in the sidebar to start.")
    st.stop()

ovr = st.session_state.setdefault("ovr", dict(d.get("overrides", {})))
settings = dict(d.get("settings", {}))

# sidebar: recommendation settings
with st.sidebar.expander("Recommendation & scenario settings"):
    settings["buy_threshold"] = st.number_input("BUY if upside ≥", value=float(settings.get("buy_threshold", DS["buy_threshold"])), step=.05, format="%.2f")
    settings["sell_threshold"] = st.number_input("SELL if upside ≤", value=float(settings.get("sell_threshold", DS["sell_threshold"])), step=.05, format="%.2f")
    settings["scn_growth_delta"] = st.number_input("Scenario shift: growth", value=float(settings.get("scn_growth_delta", DS["scn_growth_delta"])), step=.01, format="%.3f")
    settings["scn_margin_delta"] = st.number_input("Scenario shift: margin/ROE", value=float(settings.get("scn_margin_delta", DS["scn_margin_delta"])), step=.01, format="%.3f")
    settings["scn_rate_delta"] = st.number_input("Scenario shift: discount rate", value=float(settings.get("scn_rate_delta", DS["scn_rate_delta"])), step=.005, format="%.3f")
    pb = st.slider("Bear probability", 0.0, 0.5, float(settings.get("scenario_prob", [.25, .5, .25])[0]), .05)
    pu = st.slider("Bull probability", 0.0, 0.5, float(settings.get("scenario_prob", [.25, .5, .25])[2]), .05)
    settings["scenario_prob"] = [pb, 1 - pb - pu, pu]

missing = preflight(d)
m = d["meta"]
_dn = st.session_state.get("data_name") or ""
esc_src = (f"uploaded file &ldquo;{_dn}&rdquo;" if src.startswith("Open project")
           else f"built-in example &ldquo;{_dn}&rdquo;")
st.markdown(
    f"<div class='band'><div class='t'>BLANKSLATE</div>"
    f"<div class='n'>{m.get('name') or 'Unnamed company'} &nbsp;·&nbsp; {m.get('ticker') or ''}</div>"
    f"<div class='s'>Sector: {m.get('sector')} &nbsp;·&nbsp; Valuation date: {m.get('valuation_date')}"
    f" &nbsp;·&nbsp; Data last updated: {d.get('last_updated')}"
    f" &nbsp;·&nbsp; Figures in {m.get('currency')} × {_num(m.get('unit')) or 1:,.0f}"
    f" &nbsp;·&nbsp; Source: {esc_src}</div></div>",
    unsafe_allow_html=True)
if missing:
    st.error("Cannot calculate yet. Missing required inputs: " + ", ".join(missing))
    st.stop()

try:
    o = run(d, ovr, settings)
except Exception as e:  # noqa: BLE001
    st.error(f"Calculation stopped: {e}. Check the input template for non-numeric or empty cells.")
    st.stop()

rec, fv, dec = o["recommendation"], o["fair_value"] or {}, o["decision"]
calc_at = dt.datetime.now().strftime("%H:%M:%S")
if _recalc:
    st.toast(f"Recalculated at {calc_at} — {rec['call']} {fmt(rec.get('upside'), pct=True)}")
tabs = st.tabs(["Dashboard", "Data & history", "Assumptions", "Intrinsic value", "Relative value",
                "Method selection", "Scenarios & sensitivity", "Key risks", "Validation", "Export", "Guide"])

# ------------------------------------------------------------------ dashboard
with tabs[0]:
    color = {"BUY": PAPRIKA, "HOLD": GOLD, "SELL": PETROL}.get(rec["call"], TAUPE)

    # Card 2: where the market price sits inside the fair-value range. Clamped, because a price
    # outside the range is exactly the case worth showing at the edge rather than off the card.
    _lo, _hi = fv.get("low"), fv.get("high")
    if _lo is not None and _hi is not None and _hi > _lo:
        _raw = (o["price"] - _lo) / (_hi - _lo)
        _pos = min(max(_raw, 0.0), 1.0) * 100
        # A clamped marker sits on the edge, which would read as "just inside". Say which it is.
        _where = ("price is below the whole range" if _raw < 0 else
                  "price is above the whole range" if _raw > 1 else
                  f"price sits {_raw:.0%} of the way up the range")
        _scale = (f"<div class='scale'><b style='left:calc({_pos:.1f}% - 1.5px)'></b></div>"
                  f"<div class='ft'>fair {fmt(fv.get('central'))} · range {fmt(_lo)} – {fmt(_hi)}"
                  f"<br>{_where}</div>")
    else:
        _scale = "<div class='ft'>No fair-value range available.</div>"

    # Card 3: the top line over the periods loaded, newest highlighted.
    _rows = o["history"]["rows"]
    _series = [r.get("revenue") for r in _rows if r.get("revenue") is not None]
    if _series and max(_series) > 0:
        _mx = max(_series)
        _bars = "".join(
            f"<i class='hi' style='height:{v/_mx*100:.0f}%'></i>" if i == len(_series) - 1
            else f"<i style='height:{max(v/_mx*100, 3):.0f}%'></i>"
            for i, v in enumerate(_series))
        _unit = _num(m.get("unit")) or 1
        _latest = _series[-1] * _unit
        _big = (f"{_latest/1e12:,.1f}T" if _latest >= 1e12 else
                f"{_latest/1e9:,.1f}B" if _latest >= 1e9 else f"{_series[-1]:,.0f}")
        _rev_card = (f"<div class='l'>Revenue, {len(_series)} periods</div><div class='v'>{_big}</div>"
                     f"<div class='sbars'>{_bars}</div>")
    else:
        _rev_card = "<div class='l'>Revenue history</div><div class='v'>–</div>"

    # Card 4: the weight split, as a ring. The dash array is the split itself.
    _wi = dec["w_intrinsic"] * 100
    _ring = (f"<svg class='ring' width='58' height='58' viewBox='0 0 42 42' aria-hidden='true'>"
             f"<circle cx='21' cy='21' r='16' fill='none' stroke='#E3D9C9' stroke-width='7'/>"
             f"<circle cx='21' cy='21' r='16' fill='none' stroke='{PAPRIKA}' stroke-width='7'"
             f" stroke-dasharray='{_wi:.0f} {100-_wi:.0f}' stroke-dashoffset='25'"
             f" transform='rotate(-90 21 21)'/></svg>")

    st.markdown(f"""
<div class="dgrid">
  <div class="dc verdict" style="background:{color};border-color:{color}">
    <div class="l">Recommendation</div><div class="v">{rec['call']}</div>
    <div class="ft">{fmt(rec.get('upside'), pct=True)} &nbsp;·&nbsp; confidence
      {rec.get('confidence') or '–'}</div></div>
  <div class="dc"><div class="l">Price vs fair value</div>
    <div class="v">{fmt(o['price'])}</div>{_scale}</div>
  <div class="dc">{_rev_card}</div>
  <div class="dc"><div class="l">Method weight</div>
    <div class="v">{dec['w_intrinsic']:.0%} / {dec['w_relative']:.0%}</div>{_ring}
    <div class="ft">intrinsic {dec['w_intrinsic']:.0%} · relative {dec['w_relative']:.0%}<br>
      total tilt {dec['total_tilt']:+d}</div></div>
</div>""", unsafe_allow_html=True)
    st.caption(f"{rec['rationale']}  Calculated at {calc_at} from the inputs now on screen; "
               f"every change recalculates it.")
    errs = [c for c in o["checks"] if c["severity"] == "ERROR"]
    warns = [c for c in o["checks"] if c["severity"] == "WARNING"]
    _ntot = len(CHECK_CODES)
    if errs:
        st.error(f"**Validation: {len(errs)} error(s)** block the recommendation, and "
                 f"{len(warns)} warning(s) stand. {_ntot} checks were run. Open the Validation tab.")
    elif warns:
        st.warning(f"**Validation: {len(warns)} warning(s)** — the recommendation stands, but each "
                   f"warning names something a reader could challenge. {_ntot} checks were run. "
                   f"Open the Validation tab.")
    else:
        st.success(f"**Validation: all {_ntot} checks passed** — no missing inputs, no unit "
                   f"mismatch, terminal growth within bounds, every multiple valid, and the "
                   f"enterprise-to-equity bridge reconciles.")

    # football field
    sc, comp = o["scenarios"], o["relative"]["composite"] or {}
    bars = [("Intrinsic (" + ("excess return" if o["financial"] else "DCF") + ")", sc["bear"]["value"], sc["bull"]["value"], o["intrinsic_central"], TEAL)]
    for name, v in o["relative"]["multiples"].items():
        if v["usable"]:
            bars.append((f"Relative · {name}", v["low"], v["high"], v["value"], "#A99C88"))
    if comp:
        bars.append(("Relative composite", comp["low"], comp["high"], comp["value"], "#5E7A52"))
    bars.append(("Blended fair value", fv.get("low"), fv.get("high"), fv.get("central"), INK))
    fig = go.Figure()
    for i, (n, lo, hi, mid, colr) in enumerate(bars):
        if lo is None or hi is None:
            continue
        fig.add_trace(go.Bar(y=[n], x=[hi - lo], base=[lo], orientation="h", marker_color=colr,
                             hovertemplate=f"{n}<br>low %{{base:,.0f}} · high {hi:,.0f}<extra></extra>", showlegend=False))
        fig.add_trace(go.Scatter(y=[n], x=[mid], mode="markers", marker=dict(color="white", size=9, line=dict(color=colr, width=2)),
                                 hovertemplate=f"central {mid:,.0f}<extra></extra>", showlegend=False))
    fig.add_vline(x=o["price"], line_dash="dash", line_color=RED, annotation_text=f"Price {o['price']:,.0f}", annotation_position="top")
    fig.update_layout(title="Valuation football field (value per share)", height=110 + 46 * len(bars),
                      margin=dict(l=10, r=10, t=50, b=10), yaxis=dict(autorange="reversed"), plot_bgcolor="white")

    # The field and the rule that produced the weights, side by side. Seeing the six measured
    # factors next to the spread they govern is the whole argument of this model on one screen;
    # the full trace, with each factor's measurement, stays on the Method selection tab.
    f1, f2 = st.columns([1.65, 1])
    with f1:
        st.plotly_chart(fig, width='stretch')
    with f2:
        st.markdown(f"<div style='font:700 14px Cambria;margin:6px 0 10px'>"
                    f"Why the weights fell {dec['w_intrinsic']:.0%} / {dec['w_relative']:.0%}</div>",
                    unsafe_allow_html=True)
        _tf = []
        for _f in dec["factors"]:
            _t = _f["tilt"]
            _c = PAPRIKA if _t > 0 else PETROL if _t < 0 else TAUPE
            _w = abs(_t) / 2 * 44
            _left = 50 if _t >= 0 else 50 - _w
            _tf.append(f"<div class='tf'><span class='id' title=\"{_f['name']}\">{_f['id']} "
                       f"{_f['name'][:22]}</span><span class='tk'>"
                       f"<b style='left:{_left:.0f}%;width:{_w:.0f}%;background:{_c}'></b></span>"
                       f"<span class='tv' style='color:{_c}'>{_t:+d}</span></div>")
        st.markdown("".join(_tf), unsafe_allow_html=True)
        st.caption("Each factor is measured from the data, not chosen. "
                   "← favours multiples · favours cash flows →")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("How the methods were weighted")
        wfig = go.Figure(go.Pie(labels=["Intrinsic", "Relative"], values=[dec["w_intrinsic"], dec["w_relative"]],
                                hole=.6, marker_colors=[PAPRIKA, OLIVE], sort=False))
        wfig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(wfig, width='stretch')
        st.caption(f"Total tilt {dec['total_tilt']:+d} → intrinsic weight = clip(50% + 5% × tilt, 20%, 80%)"
                   + (f" · gate: {dec['gate']}" if dec["gate"] else ""))
    with c4:
        st.subheader("What the price implies")
        rv = o["reverse"]
        if rv and rv.get("bracketed") is False:
            # Growth alone cannot reach the price: say so, and say what the bound is worth.
            st.metric("Value at the lowest growth tested", fmt(rv.get("value_at_low_growth")),
                      delta=f"price: {fmt(o['price'])}", delta_color="off")
            st.warning(rv.get("note") or "No growth path in the search range reproduces the market price.")
            st.caption("The key-risk register solves on the discount rate instead; see the Key risks tab.")
        elif rv:
            if o["financial"]:
                st.metric("Implied starting ROE", fmt(rv.get("implied_roe_start"), pct=True),
                          delta=f"model: {o['assumptions']['roe_start']:.1%}", delta_color="off")
            else:
                st.metric("Implied year-1 revenue growth", fmt(rv.get("implied_g1"), pct=True),
                          delta=f"model: {o['assumptions']['g1']:.1%}", delta_color="off")
                st.metric("Implied 10-year revenue CAGR", fmt(rv.get("implied_rev_cagr_10y"), pct=True))
            st.caption("Reverse valuation: the growth path (scaled) at which intrinsic value equals the market price.")
        else:
            st.caption("No growth path within the search range reproduces the market price.")

# ------------------------------------------------------------------ data & history
with tabs[1]:
    h = o["history"]
    st.subheader("Market data on the valuation date")
    st.caption("These drive the comparison with the market price. Edit them here; everything "
               "recalculates. Use Save project on the Export tab to keep the change.")
    with st.container(border=True):
        e1, e2, e3, e4, e5 = st.columns(5)
        try:
            _vd = dt.date.fromisoformat(str(m.get("valuation_date"))[:10])
        except (ValueError, TypeError):
            _vd = dt.date.today()
        nvd = e1.date_input("Valuation date", value=_vd, format="YYYY-MM-DD", key="in_vd")
        d["meta"]["valuation_date"] = nvd.isoformat()
        d["meta"]["price"] = e2.number_input(f"Share price ({m.get('currency')})",
                                             value=float(_num(m.get("price")) or 0.0), step=1.0,
                                             format="%.2f", key="in_price")
        d["meta"]["shares"] = e3.number_input("Shares outstanding", value=float(_num(m.get("shares")) or 0.0),
                                              step=1.0, format="%.3f", key="in_sh",
                                              help=f"In units of {_num(m.get('share_unit')) or 1:,.0f}")
        d["last_updated"] = e4.text_input("Data last updated", value=str(d.get("last_updated") or ""),
                                          key="in_lu", help="Date of the newest statement loaded")
        d["meta"]["peers_as_of"] = e5.text_input(
            "Peers priced on", value=str(m.get("peers_as_of") or ""), key="in_pao",
            help="Date of the peer market values (YYYY-MM-DD). It must equal the valuation date, "
                 "or the relative valuation is built on a different market from the company's.")
        st.caption(f"Market capitalisation implied: "
                   f"{(d['meta']['price'] * d['meta']['shares'] * (_num(m.get('share_unit')) or 1)) / (_num(m.get('unit')) or 1):,.0f} "
                   f"({m.get('currency')} x {_num(m.get('unit')) or 1:,.0f})")
    st.divider()
    st.subheader("Historical performance")
    rows = h["rows"]
    per = [r["period"] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=per, y=[r["revenue"] for r in rows], name="Revenue", marker_color="#E3D9C9"))
    fig.add_trace(go.Bar(x=per, y=[r["ebit"] for r in rows], name="EBIT", marker_color=TEAL))
    fig.add_trace(go.Scatter(x=per, y=[r["ebit_margin"] for r in rows], name="EBIT margin", yaxis="y2",
                             mode="lines+markers", line=dict(color=ORANGE, width=3)))
    fig.update_layout(barmode="overlay", height=360, yaxis2=dict(overlaying="y", side="right", tickformat=".0%"),
                      margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"), plot_bgcolor="white")
    st.plotly_chart(fig, width='stretch')
    c = st.columns(4)
    kpi(c[0], "Revenue CAGR", fmt(h["cagr"], pct=True)); kpi(c[1], "Avg EBIT margin (3p)", fmt(h["margin_avg3"], pct=True))
    kpi(c[2], "Margin volatility (CV)", fmt(h["margin_cv"], dec=2)); kpi(c[3], "Sales-to-capital (median)", fmt(h["s2c_median"], dec=2))
    st.dataframe([{k: v for k, v in r.items()} for r in rows], width='stretch', hide_index=True)
    with st.expander("Raw inputs and sources"):
        st.json({"meta": d["meta"], "market": d["market"], "sources": d.get("sources", {})})

# ------------------------------------------------------------------ assumptions
with tabs[2]:
    st.subheader("Assumptions")
    st.caption("Every value starts from an engine default derived from the data. Tick 'override' to replace it; "
               "the dashboard, scenarios and recommendation recalculate immediately.")
    keys = [k for k, _ in ASSUMPTION_FIELDS if (k.startswith("roe") or k == "payout") == o["financial"] or k in ("g_terminal", "terminal_beta")]
    if not o["financial"]:
        keys = [k for k, _ in ASSUMPTION_FIELDS if not (k.startswith("roe") or k == "payout")]
    keys += ["rf", "erp", "crp", "beta", "kd_pretax", "marginal_tax", "target_dv"]
    labels = dict(ASSUMPTION_FIELDS) | {"rf": "Risk-free rate", "erp": "Equity risk premium", "crp": "Country risk premium",
                                        "beta": "Levered beta (user method)", "kd_pretax": "Pre-tax cost of debt",
                                        "marginal_tax": "Marginal tax rate", "target_dv": "Target D/V"}
    pct_like = PCT_KEYS | {"rf", "erp", "crp", "kd_pretax", "marginal_tax", "target_dv"}
    for k in keys:
        dflt = o["defaults"].get(k)
        c1, c2, c3, c4 = st.columns([2.3, 1.2, .8, 1.4])
        c1.write(f"**{labels.get(k, k)}**  \n<span style='opacity:.70;font-size:.8rem'>{o['assumption_sources'].get(k, 'market input')}</span>",
                 unsafe_allow_html=True)
        c2.write(f"default: {fmt(dflt, pct=k in pct_like, dec=2) if isinstance(dflt, (int, float)) else dflt}")
        on = c3.checkbox("override", value=k in ovr, key=f"chk_{k}")
        if on:
            base = float(ovr.get(k, dflt if isinstance(dflt, (int, float)) else 0.0))
            ovr[k] = c4.number_input("value", value=base, step=0.005 if k in pct_like else 0.05, format="%.4f",
                                     key=f"num_{k}", label_visibility="collapsed")
        else:
            ovr.pop(k, None)
    r = o["rates"]
    st.divider()
    st.subheader("Discount rate build-up")
    c = st.columns(5)
    kpi(c[0], "Beta used", fmt(r["beta"], dec=2)); kpi(c[1], "Cost of equity", fmt(r["ke"], pct=True))
    kpi(c[2], "After-tax cost of debt", fmt(r["kd_after_tax"], pct=True)); kpi(c[3], "WACC (years 1–5)", fmt(r["wacc"], pct=True))
    kpi(c[4], "Terminal WACC", fmt(r["wacc_T"], pct=True))
    st.caption(f"ke = rf + β × (ERP + CRP) = {r['rf']:.2%} + {r['beta']:.2f} × ({r['erp']:.2%} + {r['crp']:.2%}). "
               f"Beta: {r['beta_note']}. Target D/V {r['dv']:.1%} (current market D/V {r['dv_current']:.1%}).")

# ------------------------------------------------------------------ intrinsic
with tabs[3]:
    i = o["intrinsic"]
    st.subheader(i["model"])
    if o["financial"]:
        st.caption("Equity = book value + PV of excess returns (ROE − ke) × opening book value + PV of terminal excess return.")
        c = st.columns(4)
        kpi(c[0], "Book value", fmt(i["bv0"])); kpi(c[1], "PV excess returns (10y)", fmt(i["pv_excess"]))
        kpi(c[2], "PV terminal", fmt(i["pv_tv"])); kpi(c[3], "Value per share", fmt(i["value_per_share"]))
    else:
        rows = i["rows"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[x["year"] for x in rows], y=[x["fcff"] for x in rows], name="FCFF", marker_color=TEAL))
        fig.add_trace(go.Scatter(x=[x["year"] for x in rows], y=[x["margin"] for x in rows], name="EBIT margin",
                                 yaxis="y2", line=dict(color=ORANGE, width=3)))
        fig.add_trace(go.Scatter(x=[x["year"] for x in rows], y=[x["growth"] for x in rows], name="Revenue growth",
                                 yaxis="y2", line=dict(color=INK, width=2, dash="dot")))
        fig.update_layout(height=340, yaxis2=dict(overlaying="y", side="right", tickformat=".0%"), plot_bgcolor="white",
                          margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"), xaxis_title="Forecast year")
        st.plotly_chart(fig, width='stretch')
        b = i["bridge"]
        wf = go.Figure(go.Waterfall(
            x=["PV FCFF yrs 1–10", "PV terminal value", "Enterprise value", "+ Cash", "+ Non-operating assets",
               "− Debt", "− Leases", "− Minority interest", "Equity value"],
            measure=["relative", "relative", "total", "relative", "relative", "relative", "relative", "relative", "total"],
            y=[i["pv_explicit"], i["pv_tv"] or 0, 0, b["cash"], b["non_operating_assets"], -b["total_debt"],
               -b["lease_liabilities"], -b["minority_interest"], 0],
            connector={"line": {"color": "#DCD2C2"}}, increasing={"marker": {"color": TEAL}},
            decreasing={"marker": {"color": RED}}, totals={"marker": {"color": INK}}))
        wf.update_layout(title="Enterprise-to-equity bridge", height=360, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor="white")
        st.plotly_chart(wf, width='stretch')
        c = st.columns(4)
        kpi(c[0], "Terminal value share of EV", fmt(i["tv_share"], pct=True))
        kpi(c[1], "Terminal reinvestment rate", fmt(i["terminal_reinvestment_rate"], pct=True))
        kpi(c[2], "Equity value", fmt(i["equity"])); kpi(c[3], "Value per share (base)", fmt(i["value_per_share"]))
    st.dataframe(i["rows"], width='stretch', hide_index=True)

# ------------------------------------------------------------------ relative
with tabs[4]:
    rel = o["relative"]
    st.subheader("Relative valuation")
    st.caption("Rules: peers with a non-positive denominator are excluded; with ≥5 values, IQR outliers are excluded; "
               "a multiple needs ≥3 valid peers and a positive target metric. EV multiples are converted to equity with "
               f"the same net claims as the DCF ({rel['claims']:,.0f}).")
    tbl = []
    for k, v in rel["multiples"].items():
        tbl.append({"Multiple": k, "Valid peers": v["n"], "Median": v["median"], "P25": v["p25"], "P75": v["p75"],
                    "Target metric": v["target_metric"], "Value/share": v["value"], "Weight": v.get("weight_share", 0),
                    "Status": v["reason"]})
    st.dataframe(tbl, width='stretch', hide_index=True)
    for k, v in rel["multiples"].items():
        if not v["valid"]:
            continue
        fig = go.Figure(go.Bar(x=[n for n, _ in v["valid"]], y=[x for _, x in v["valid"]], marker_color=OLIVE))
        if v["median"]:
            fig.add_hline(y=v["median"], line_dash="dash", line_color=INK, annotation_text=f"median {v['median']:.2f}")
        fig.update_layout(title=f"{k}: valid peers", height=260, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
        st.plotly_chart(fig, width='stretch')
        if v["excluded"]:
            st.caption("Excluded: " + "; ".join(f"{n} ({w})" for n, _, w in v["excluded"]))

# ------------------------------------------------------------------ method selection
with tabs[5]:
    st.subheader("Valuation approach selection: rule trace")
    st.caption("Each factor tilts from −2 (favour relative valuation) to +2 (favour intrinsic valuation), using measured data.")
    fig = go.Figure(go.Bar(x=[f["tilt"] for f in dec["factors"]], y=[f"{f['id']} {f['name']}" for f in dec["factors"]],
                           orientation="h", marker_color=[PAPRIKA if f["tilt"] > 0 else PETROL if f["tilt"] < 0 else TAUPE for f in dec["factors"]]))
    fig.update_layout(height=320, xaxis=dict(range=[-2.2, 2.2], dtick=1, title="← relative   tilt   intrinsic →"),
                      yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white")
    st.plotly_chart(fig, width='stretch')
    st.dataframe(dec["factors"], width='stretch', hide_index=True)
    st.info(f"Total tilt {dec['total_tilt']:+d} → intrinsic {dec['w_intrinsic']:.0%}, relative {dec['w_relative']:.0%}."
            + (f" Gate applied: {dec['gate']}." if dec["gate"] else ""))

# ------------------------------------------------------------------ scenarios & sensitivity
with tabs[6]:
    sc = o["scenarios"]
    st.subheader("Scenarios")
    fig = go.Figure(go.Bar(x=["Bear", "Base", "Bull"], y=[sc[k]["value"] for k in ("bear", "base", "bull")],
                           marker_color=["#E6B6A3", "#B85A3E", "#A83D24"], text=[fmt(sc[k]["value"]) for k in ("bear", "base", "bull")]))
    fig.add_hline(y=o["price"], line_dash="dash", line_color=INK, annotation_text="market price")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor="white")
    st.plotly_chart(fig, width='stretch')
    st.dataframe([{"scenario": k, **v} for k, v in sc.items()], width='stretch', hide_index=True)
    st.caption(f"Probability-weighted intrinsic value: {fmt(o['intrinsic_central'])} "
               f"(weights {settings['scenario_prob'][0]:.0%}/{settings['scenario_prob'][1]:.0%}/{settings['scenario_prob'][2]:.0%}).")
    st.subheader("Sensitivity: discount rate × terminal growth")
    gs = [o["assumptions"]["g_terminal"] + x for x in (-0.01, -0.005, 0, 0.005, 0.01)]
    z = [row["values"] for row in o["sens_rate"]]
    hm = go.Figure(go.Heatmap(z=z, x=[f"{g:.2%}" for g in gs], y=[f"{row['rate']:.2%}" for row in o["sens_rate"]],
                              colorscale=[[0, "#F6E3DA"], [.5, "#D99877"], [1, "#A83D24"]],
                              text=[[fmt(v) for v in row] for row in z], texttemplate="%{text}"))
    hm.update_layout(height=320, xaxis_title="terminal growth", yaxis_title="discount rate", xaxis_type="category", yaxis_type="category", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(hm, width='stretch')
    if o["sens_ops"]:
        st.subheader("Sensitivity: year-1 growth × target margin")
        g1s = [o["assumptions"]["g1"] + x for x in (-0.10, -0.05, 0, 0.05, 0.10)]
        z = [row["values"] for row in o["sens_ops"]]
        hm2 = go.Figure(go.Heatmap(z=z, x=[f"{g:.1%}" for g in g1s], y=[f"{row['target_margin']:.1%}" for row in o["sens_ops"]],
                                   colorscale=[[0, "#F6E3DA"], [.5, "#D99877"], [1, "#A83D24"]],
                                   text=[[fmt(v) for v in row] for row in z], texttemplate="%{text}"))
        hm2.update_layout(height=320, xaxis_title="year-1 revenue growth", yaxis_title="target EBIT margin", xaxis_type="category", yaxis_type="category",
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(hm2, width='stretch')

# ------------------------------------------------------------------ key risks
with tabs[7]:
    st.subheader("Key risks")
    st.caption("Derived from this valuation, so the register updates with the data. A break-even is "
               "the level of one driver at which the blended fair value equals the market price: "
               "the point where the recommendation reverses.")
    rk = o.get("risks", [])
    if not rk:
        st.info("No risk register available.")
    else:
        cnt = st.columns(3)
        for c, sev in zip(cnt, ("High", "Medium", "Low")):
            kpi(c, f"{sev} severity", str(sum(1 for x in rk if x["severity"] == sev)))
        tone = {"High": st.error, "Medium": st.warning, "Low": st.info}
        for x in rk:
            with st.container(border=True):
                head = f"**{x['category']}** · {x['severity']}" + (" · analyst-entered" if x["source"] == "analyst" else "")
                st.markdown(head)
                st.write(x["risk"])
                if x["measure"]:
                    st.caption(x["measure"])
                if x["break_even"]:
                    st.markdown(f"Break-even: **{x['break_even']}**")
        st.caption("Add risks only you can know (customers, regulation, FX, supply, key people) on "
                   "the Risks sheet of the input template; they appear here alongside these.")

# ------------------------------------------------------------------ checks
with tabs[8]:
    st.subheader("Validation checks")
    st.caption("Thirty rules run on every calculation: missing inputs, inconsistent units, "
               "implausible terminal growth, unusable multiples, and the enterprise-to-equity "
               "reconciliation. Errors block the recommendation; warnings do not, but each one "
               "names something a reader could reasonably challenge.")
    for sev, fn in (("ERROR", st.error), ("WARNING", st.warning), ("INFO", st.info)):
        items = [c for c in o["checks"] if c["severity"] == sev]
        if items:
            fn(f"**{sev}** ({len(items)})\n\n" + "\n".join(f"- `{c['code']}` {c['message']}" for c in items))
    if not o["checks"]:
        st.success("All checks passed.")

# ------------------------------------------------------------------ export
with tabs[9]:
    st.subheader("Export and save")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    tk = (m.get("ticker") or "company").replace(" ", "")
    d_save = copy.deepcopy(d); d_save["overrides"] = dict(ovr); d_save["settings"] = settings
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇ Results workbook (.xlsx)", export_results(d_save, o), f"{tk}_valuation_results_{stamp}.xlsx")
    c2.download_button("⬇ Save project (.xlsx)", blank_template(data=d_save), f"{tk}_project_{stamp}.xlsx",
                       help="Inputs, overrides and settings. Reopen it with 'Open project' in the sidebar.")
    try:
        import sys as _s, io as _io, tempfile, os
        from excel.build_workbook import build as _build
        with tempfile.TemporaryDirectory() as _t:
            _p = os.path.join(_t, "wb.xlsx"); _build(d_save, _p)
            st.download_button("⬇ Excel engine pre-filled with this company (.xlsx; import the VBA module to make it .xlsm)",
                               open(_p, "rb").read(), f"{tk}_BlankSlate_Valuation_{stamp}.xlsx")
    except Exception as _e:  # noqa: BLE001
        st.caption(f"Excel engine export unavailable: {_e}")
    c3.download_button("⬇ Full results (.json)", json.dumps(o, default=str, indent=1), f"{tk}_valuation_{stamp}.json")
    st.caption("The results workbook contains the summary and football-field chart, method-selection trace, "
               "intrinsic table, relative valuation, checks and the assumptions used (with defaults and overrides).")


# ------------------------------------------------------------------ guide
with tabs[10]:
    # Written for whoever has this application open. Someone reading this tab is already inside
    # the tool, so it covers using it, never installing or reaching it. Setup, access and the
    # Excel engine belong to USER_GUIDE.md, which ships with the submission package.
    st.markdown(APP_GUIDE)
