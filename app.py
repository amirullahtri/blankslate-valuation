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
from engine.checks import REQUIRED_META, REQUIRED_FIN, REQUIRED_MKT

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
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=[PAPRIKA, OLIVE, PETROL, GOLD, STONE, TAUPE],
    xaxis=dict(gridcolor="#E2D9C9", zerolinecolor=BORDER, linecolor=BORDER),
    yaxis=dict(gridcolor="#E2D9C9", zerolinecolor=BORDER, linecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
))
pio.templates.default = "blankslate"

st.markdown(f"""
<style>
.block-container {{padding-top: 1.2rem;}}
h1, h2, h3 {{color:{INK};}}

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

.kpi {{background:#FFFFFF; border:1px solid {BORDER}; border-radius:10px; padding:12px 14px;
       height:100%;}}
.kpi .l {{font-size:.74rem; color:{STONE}; text-transform:uppercase; letter-spacing:.05em;}}
.kpi .v {{font-size:1.45rem; font-weight:700; color:{INK}; margin-top:2px;}}

/* Tabs: the active one is marked by the accent, not by a grey box. */
.stTabs [data-baseweb="tab-list"] {{gap:2px; border-bottom:1px solid {BORDER};}}
.stTabs [data-baseweb="tab"] {{padding:8px 14px; color:{STONE};}}
.stTabs [aria-selected="true"] {{color:{PAPRIKA} !important; font-weight:700;
                                 border-bottom:3px solid {PAPRIKA};}}
[data-testid="stSidebar"] {{background:{SAND};}}
[data-testid="stDataFrame"] {{border:1px solid {BORDER}; border-radius:8px;}}
</style>""", unsafe_allow_html=True)

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
    if up is not None:
        try:
            st.session_state["data"] = read_template(up)
            st.session_state["data_name"] = up.name
        except Exception as e:  # noqa: BLE001
            st.sidebar.error(f"Could not read the template: {e}")
else:
    import examples
    names = list(examples.EXAMPLES)
    pick = st.sidebar.selectbox("Example company", names)
    if st.session_state.get("data_name") != pick:
        st.session_state["data"] = copy.deepcopy(examples.EXAMPLES[pick])
        st.session_state["data_name"] = pick
        st.session_state["ovr"] = {}
st.sidebar.download_button("⬇ Blank input template", blank_template(), "BlankSlate_input_template.xlsx",
                           help="Fill this file for any listed company and upload it here.")

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
st.markdown(
    f"<div class='band'><div class='t'>BLANKSLATE</div>"
    f"<div class='n'>{m.get('name') or 'Unnamed company'} &nbsp;·&nbsp; {m.get('ticker') or ''}</div>"
    f"<div class='s'>Sector: {m.get('sector')} &nbsp;·&nbsp; Valuation date: {m.get('valuation_date')}"
    f" &nbsp;·&nbsp; Data last updated: {d.get('last_updated')}"
    f" &nbsp;·&nbsp; Figures in {m.get('currency')} × {_num(m.get('unit')) or 1:,.0f}</div></div>",
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
tabs = st.tabs(["Dashboard", "Data & history", "Assumptions", "Intrinsic value", "Relative value",
                "Method selection", "Scenarios & sensitivity", "Key risks", "Checks", "Export", "Guide"])

# ------------------------------------------------------------------ dashboard
with tabs[0]:
    color = {"BUY": PAPRIKA, "HOLD": GOLD, "SELL": PETROL}.get(rec["call"], TAUPE)
    c1, c2 = st.columns([1.1, 2.4])
    with c1:
        up = rec.get("upside")
        st.markdown(
            f"<div class='call' style='background:{color}'>"
            f"<div class='c'>{rec['call']}</div>"
            f"<div class='f'>{fmt(up, pct=True) if up is not None else ''} &nbsp;·&nbsp; "
            f"confidence {rec.get('confidence') or '–'}</div></div>", unsafe_allow_html=True)
        st.caption(rec["rationale"])
    with c2:
        k = st.columns(4)
        kpi(k[0], "Market price", fmt(o["price"], dec=0))
        kpi(k[1], "Fair value (central)", fmt(fv.get("central")))
        kpi(k[2], "Upside / downside", fmt(rec.get("upside"), pct=True))
        kpi(k[3], "Fair-value range", f"{fmt(fv.get('low'))} – {fmt(fv.get('high'))}")
    errs = [c for c in o["checks"] if c["severity"] == "ERROR"]
    warns = [c for c in o["checks"] if c["severity"] == "WARNING"]
    if errs:
        st.error(f"{len(errs)} error(s) block the recommendation. See the Checks tab.")
    elif warns:
        st.warning(f"{len(warns)} warning(s). See the Checks tab.")

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
    st.plotly_chart(fig, width='stretch')

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
        c1.write(f"**{labels.get(k, k)}**  \n<span style='color:#56666C;font-size:.8rem'>{o['assumption_sources'].get(k, 'market input')}</span>",
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
    st.subheader("Guide")
    st.caption("Operating instructions for this calculator. The same text ships as the user guide "
               "in the submission package.")
    _gp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "USER_GUIDE.md")
    try:
        with open(_gp, encoding="utf-8") as _f:
            st.markdown(_f.read())
    except OSError:
        st.warning("USER_GUIDE.md not found next to the application; see the submission package.")
