"""Standard input template: create a blank template, read a filled one, export results."""
from __future__ import annotations
import datetime as _dt
import io as _io
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from .core import SECTORS, DEFAULT_SETTINGS

META_FIELDS = [
    ("name", "Company name", ""), ("ticker", "Ticker", ""),
    ("sector", "Sector (choose from list)", ""), ("is_financial", "Financial firm? (bank/insurer/multifinance) TRUE/FALSE", "FALSE"),
    ("currency", "Reporting currency (e.g. IDR)", "IDR"),
    ("unit", "Unit of ALL statement figures (1e9 = billion, 1e6 = million)", 1e9),
    ("shares", "Shares outstanding (in share_unit)", ""), ("share_unit", "Share unit (1e6 = million shares)", 1e6),
    ("price", "Share price at valuation date (per share)", ""), ("valuation_date", "Valuation date (YYYY-MM-DD)", ""),
    ("peers_as_of", "Date of the peer market values (YYYY-MM-DD; must equal the valuation date)", ""),
]
FIN_FIELDS = [
    ("revenue", "Revenue", "IS"), ("ebit", "Operating profit (EBIT)", "IS"),
    ("d_and_a", "Depreciation & amortisation (positive)", "IS/CF"),
    ("interest_expense", "Interest expense (positive)", "IS"), ("pretax_income", "Profit before tax", "IS"),
    ("income_tax", "Income tax expense (positive)", "IS"), ("net_income", "Net income attributable to parent", "IS"),
    ("dividends_paid", "Dividends paid", "CF"),
    ("cash", "Cash & short-term investments", "BS"), ("total_debt", "Total borrowings & bonds", "BS"),
    ("lease_liabilities", "Lease liabilities", "BS"), ("minority_interest", "Non-controlling interest", "BS"),
    ("equity_parent", "Equity attributable to parent", "BS"),
    ("non_operating_assets", "Investments in associates/JVs & other non-operating assets", "BS"),
    ("goodwill_intangibles", "Goodwill & other intangible assets (for the P/B comparability check)", "BS"),
    ("total_assets", "Total assets", "BS"), ("cfo", "Cash flow from operations", "CF"),
    ("capex", "Capital expenditure (purchase of PP&E/intangibles)", "CF"),
]
MARKET_FIELDS = [
    ("rf", "Risk-free rate (10-year government bond yield)", ""), ("erp", "Mature-market equity risk premium", ""),
    ("crp", "Country risk premium", ""), ("beta", "Levered beta (if beta_method = user)", ""),
    ("beta_method", "Beta method: user / bottom-up", "user"), ("credit_spread", "Credit spread over rf (pre-tax)", ""),
    ("kd_pretax", "OR pre-tax cost of debt directly (overrides spread)", ""),
    ("marginal_tax", "Marginal tax rate", 0.22), ("target_dv", "Target D/V (blank = current market D/V)", ""),
]
PEER_FIELDS = ["name", "market_cap", "total_debt", "lease_liabilities", "minority_interest", "cash",
               "revenue", "ebitda", "ebit", "net_income", "equity_book", "beta", "source"]
ASSUMPTION_FIELDS = [
    ("g1", "Revenue growth, year 1"), ("g_terminal", "Terminal growth"), ("target_margin", "Target EBIT margin (year 5)"),
    ("sales_to_capital", "Sales-to-capital ratio"), ("roic_terminal", "Terminal ROIC"),
    ("eff_tax_start", "Effective tax rate, year 1"), ("terminal_beta", "Terminal beta"),
    ("roe_start", "Financial firms: starting ROE"), ("roe_terminal", "Financial firms: terminal ROE"),
    ("payout", "Financial firms: payout ratio"),
    ("w_intrinsic", "Weight on intrinsic value (blank = engine's own choice)"),
]
RISK_FIELDS = ["category", "risk", "measure", "break_even", "severity"]
SETTING_FIELDS = [
    ("buy_threshold", "BUY if upside >="), ("sell_threshold", "SELL if upside <="),
    ("scn_growth_delta", "Scenario shift: growth (pp)"), ("scn_margin_delta", "Scenario shift: margin / ROE (pp)"),
    ("scn_rate_delta", "Scenario shift: discount rate (pp)"),
]
HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F3A4D")
INPUT = PatternFill("solid", fgColor="FFF4D6")
N_PERIODS = 6


def _hdr(ws, row, vals):
    for j, v in enumerate(vals, 1):
        c = ws.cell(row, j, v); c.font = HEAD; c.fill = FILL


def blank_template(path_or_buf=None, data=None):
    """Write the standard template. If `data` is given, the template is pre-filled."""
    wb = Workbook()
    ws = wb.active; ws.title = "README"
    lines = [
        "BlankSlate Valuation Calculator - standard input template",
        "1. Fill the yellow cells on Company, Financials, Market and Peers. Keep the sheet and row layout.",
        "2. Financials: periods from oldest (left) to newest (right); last column may be TTM (e.g. '2026 TTM').",
        "   Balance-sheet items: value at the period end. Use the SAME unit for every figure (see Company!unit).",
        "3. Peers: same currency and unit as the company. Leave a cell blank if unknown (never type 0 for unknown).",
        "4. Assumptions: leave blank to use the engine default derived from the data; type a value to override.",
        "5. Write the source of each line in the 'Source' column.",
    ]
    for i, t in enumerate(lines, 1):
        ws.cell(i, 1, t).font = Font(bold=(i == 1), size=12 if i == 1 else 11)
    ws.column_dimensions["A"].width = 110

    d = data or {}
    # Company
    s = wb.create_sheet("Company"); _hdr(s, 1, ["Key", "Description", "Value", "Source"])
    for i, (k, desc, dflt) in enumerate(META_FIELDS, 2):
        s.cell(i, 1, k); s.cell(i, 2, desc)
        v = d.get("meta", {}).get(k, dflt)
        c = s.cell(i, 3, v); c.fill = INPUT
        s.cell(i, 4, d.get("sources", {}).get(f"meta.{k}", ""))
    dv = DataValidation(type="list", formula1='"' + ",".join(SECTORS) + '"', allow_blank=False)
    s.add_data_validation(dv); dv.add("C4")
    s.cell(len(META_FIELDS) + 3, 1, "last_updated"); s.cell(len(META_FIELDS) + 3, 3,
                                                            d.get("last_updated", _dt.date.today().isoformat())).fill = INPUT
    for col, w in zip("ABCD", (16, 62, 22, 40)):
        s.column_dimensions[col].width = w
    # Financials
    f = wb.create_sheet("Financials")
    periods = d.get("periods", [""] * N_PERIODS)
    _hdr(f, 1, ["Key", "Line item", "Stmt"] + [f"P{j+1}" for j in range(N_PERIODS)] + ["Source"])
    f.cell(2, 1, "period"); f.cell(2, 2, "Period label (e.g. 2021 ... 2025, 2026 TTM)")
    for j in range(N_PERIODS):
        c = f.cell(2, 4 + j, periods[j] if j < len(periods) else ""); c.fill = INPUT
    for i, (k, desc, st) in enumerate(FIN_FIELDS, 3):
        f.cell(i, 1, k); f.cell(i, 2, desc); f.cell(i, 3, st)
        vals = d.get("fin", {}).get(k, [])
        for j in range(N_PERIODS):
            c = f.cell(i, 4 + j, vals[j] if j < len(vals) else None); c.fill = INPUT
            c.number_format = '#,##0.0;(#,##0.0)'
        f.cell(i, 4 + N_PERIODS, d.get("sources", {}).get(f"fin.{k}", ""))
    for col, w in zip("ABC", (20, 52, 7)):
        f.column_dimensions[col].width = w
    # Market
    mk = wb.create_sheet("Market"); _hdr(mk, 1, ["Key", "Description", "Value", "Source"])
    for i, (k, desc, dflt) in enumerate(MARKET_FIELDS, 2):
        mk.cell(i, 1, k); mk.cell(i, 2, desc)
        c = mk.cell(i, 3, d.get("market", {}).get(k, dflt)); c.fill = INPUT
        mk.cell(i, 4, d.get("sources", {}).get(f"market.{k}", ""))
    for col, w in zip("ABCD", (16, 52, 14, 46)):
        mk.column_dimensions[col].width = w
    # Peers
    p = wb.create_sheet("Peers"); _hdr(p, 1, PEER_FIELDS)
    for i in range(2, 17):
        pr = d.get("peers", [])[i - 2] if i - 2 < len(d.get("peers", [])) else {}
        for j, k in enumerate(PEER_FIELDS, 1):
            c = p.cell(i, j, pr.get(k)); c.fill = INPUT
    p.column_dimensions["A"].width = 26; p.column_dimensions["M"].width = 40
    # Assumptions
    a = wb.create_sheet("Assumptions"); _hdr(a, 1, ["Key", "Description", "Override (blank = default)", "Note"])
    for i, (k, desc) in enumerate(ASSUMPTION_FIELDS, 2):
        a.cell(i, 1, k); a.cell(i, 2, desc)
        a.cell(i, 3, d.get("overrides", {}).get(k)).fill = INPUT
    a.column_dimensions["A"].width = 18; a.column_dimensions["B"].width = 40; a.column_dimensions["C"].width = 26
    # Risks (analyst-entered; the engine adds its own)
    rk = wb.create_sheet("Risks")
    _hdr(rk, 1, ["Category", "Risk (what could go wrong)", "Measure / evidence", "Break-even or trigger", "Severity (High/Medium/Low)"])
    rk.cell(2, 1, "").comment = None
    for i in range(2, 14):
        src = d.get("risks", [])[i - 2] if i - 2 < len(d.get("risks", [])) else {}
        for j, k in enumerate(RISK_FIELDS, 1):
            rk.cell(i, j, src.get(k)).fill = INPUT
    dvs = DataValidation(type="list", formula1='"High,Medium,Low"', allow_blank=True)
    rk.add_data_validation(dvs); dvs.add("E2:E13")
    for col, w in zip("ABCDE", (24, 60, 46, 26, 14)):
        rk.column_dimensions[col].width = w
    rk.cell(15, 1, "The engine adds data-derived risks automatically (terminal-value weight, "
                   "market-implied growth, break-even drivers, peer dispersion, method divergence). "
                   "Use these rows for risks only you can know: customers, regulation, FX, supply, key people.")
    # Settings
    st = wb.create_sheet("Settings"); _hdr(st, 1, ["Key", "Description", "Value"])
    for i, (k, desc) in enumerate(SETTING_FIELDS, 2):
        st.cell(i, 1, k); st.cell(i, 2, desc)
        st.cell(i, 3, d.get("settings", {}).get(k, DEFAULT_SETTINGS[k])).fill = INPUT
    st.cell(len(SETTING_FIELDS) + 2, 1, "scenario_prob"); st.cell(len(SETTING_FIELDS) + 2, 2, "Probabilities bear / base / bull")
    for j, v in enumerate(d.get("settings", {}).get("scenario_prob", DEFAULT_SETTINGS["scenario_prob"])):
        st.cell(len(SETTING_FIELDS) + 2, 3 + j, v).fill = INPUT
    st.column_dimensions["A"].width = 18; st.column_dimensions["B"].width = 40
    if path_or_buf is None:
        buf = _io.BytesIO(); wb.save(buf); return buf.getvalue()
    wb.save(path_or_buf)


def _v(x):
    if isinstance(x, str):
        t = x.strip()
        if t.upper() in ("TRUE", "FALSE"):
            return t.upper() == "TRUE"
        try:
            return float(t.replace(",", ""))
        except ValueError:
            return t if t else None
    return x


def read_template(src):
    wb = load_workbook(src, data_only=True)
    d = {"meta": {}, "fin": {}, "market": {}, "peers": [], "overrides": {}, "settings": {}, "sources": {}}
    s = wb["Company"]
    for row in s.iter_rows(min_row=2, values_only=True):
        if row[0] == "last_updated":
            d["last_updated"] = str(row[2]) if row[2] else None
        elif row[0]:
            d["meta"][row[0]] = _v(row[2])
            if row[3]: d["sources"][f"meta.{row[0]}"] = row[3]
    if isinstance(d["meta"].get("valuation_date"), (_dt.date, _dt.datetime)):
        d["meta"]["valuation_date"] = d["meta"]["valuation_date"].strftime("%Y-%m-%d")
    f = wb["Financials"]
    rows = list(f.iter_rows(min_row=2, values_only=True))
    per = [str(x).strip() for x in rows[0][3:3 + N_PERIODS]]
    used = [j for j, x in enumerate(per) if x and x != "None"]
    d["periods"] = [per[j] for j in used]
    for row in rows[1:]:
        if row[0]:
            d["fin"][row[0]] = [_v(row[3 + j]) for j in used]
            if row[3 + N_PERIODS]: d["sources"][f"fin.{row[0]}"] = row[3 + N_PERIODS]
    for row in wb["Market"].iter_rows(min_row=2, values_only=True):
        if row[0]:
            d["market"][row[0]] = _v(row[2])
            if row[3]: d["sources"][f"market.{row[0]}"] = row[3]
    for row in wb["Peers"].iter_rows(min_row=2, values_only=True):
        if row[0]:
            d["peers"].append({k: _v(v) for k, v in zip(PEER_FIELDS, row)})
    for row in wb["Assumptions"].iter_rows(min_row=2, values_only=True):
        if row[0] and _v(row[2]) is not None:
            d["overrides"][row[0]] = _v(row[2])
    d["risks"] = []
    if "Risks" in wb.sheetnames:
        for row in wb["Risks"].iter_rows(min_row=2, max_row=13, values_only=True):
            if row[1] and str(row[1]).strip():
                d["risks"].append({k: (_v(v) if k != "risk" else str(v)) for k, v in zip(RISK_FIELDS, row)})
    for row in wb["Settings"].iter_rows(min_row=2, values_only=True):
        if row[0] == "scenario_prob":
            d["settings"]["scenario_prob"] = [float(x) for x in row[2:5] if x is not None]
        elif row[0] and _v(row[2]) is not None:
            d["settings"][row[0]] = _v(row[2])
    return d


def export_results(d, o, path_or_buf=None):
    """Write a results workbook: summary, decision trace, intrinsic table, relative, checks, inputs."""
    from openpyxl.chart import BarChart, Reference
    wb = Workbook()
    ws = wb.active; ws.title = "Summary"
    m, fv, rec = d["meta"], o["fair_value"] or {}, o["recommendation"]
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = [
        ("BlankSlate Valuation Calculator - results", None),
        ("Company", f"{m.get('name')} ({m.get('ticker')})"), ("Sector", m.get("sector")),
        ("Valuation date", m.get("valuation_date")), ("Data last updated", d.get("last_updated")),
        ("Exported", stamp), (None, None),
        ("Market price", o["price"]), ("Intrinsic value (" + o["intrinsic"]["model"] + "), scenario-weighted", o["intrinsic_central"]),
        ("Relative value (composite)", (o["relative"]["composite"] or {}).get("value")),
        ("Weight intrinsic", o["decision"]["w_intrinsic"]), ("Weight relative", o["decision"]["w_relative"]),
        ("Fair value - low", fv.get("low")), ("Fair value - central", fv.get("central")), ("Fair value - high", fv.get("high")),
        ("Upside / downside", rec.get("upside")), ("Recommendation", rec["call"]), ("Confidence", rec.get("confidence")),
        ("Rationale", rec.get("rationale")),
    ]
    for i, (k, v) in enumerate(rows, 1):
        ws.cell(i, 1, k); c = ws.cell(i, 2, v)
        if isinstance(v, float):
            c.number_format = "0.0%" if k in ("Weight intrinsic", "Weight relative", "Upside / downside") else "#,##0.00"
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 52; ws.column_dimensions["B"].width = 60
    # football field data + chart
    r0 = len(rows) + 2
    ws.cell(r0, 1, "Method"); ws.cell(r0, 2, "Low"); ws.cell(r0, 3, "Central"); ws.cell(r0, 4, "High")
    sc, comp = o["scenarios"], o["relative"]["composite"] or {}
    ff = [("Intrinsic", sc["bear"]["value"], o["intrinsic_central"], sc["bull"]["value"]),
          ("Relative", comp.get("low"), comp.get("value"), comp.get("high")),
          ("Blended fair value", fv.get("low"), fv.get("central"), fv.get("high"))]
    for j, row in enumerate(ff, 1):
        for k, v in enumerate(row, 1):
            ws.cell(r0 + j, k, v)
    ch = BarChart(); ch.type = "bar"; ch.title = "Value per share by method"; ch.height = 7; ch.width = 18
    ch.add_data(Reference(ws, min_col=2, max_col=4, min_row=r0, max_row=r0 + 3), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=r0 + 1, max_row=r0 + 3))
    ws.add_chart(ch, f"D2")
    # decision
    s = wb.create_sheet("Method selection")
    _hdr(s, 1, ["Factor", "Name", "Tilt (-2 relative ... +2 intrinsic)", "Reason"])
    for i, f in enumerate(o["decision"]["factors"], 2):
        for j, k in enumerate(("id", "name", "tilt", "reason"), 1):
            s.cell(i, j, f[k])
    n = len(o["decision"]["factors"]) + 3
    s.cell(n, 1, "Total tilt"); s.cell(n, 3, o["decision"]["total_tilt"])
    s.cell(n + 1, 1, "Weight intrinsic = clip(50% + 5% x total, 20%, 80%)"); s.cell(n + 1, 3, o["decision"]["w_intrinsic"])
    s.column_dimensions["B"].width = 38; s.column_dimensions["D"].width = 90
    # intrinsic
    t = wb.create_sheet("Intrinsic")
    rws = o["intrinsic"]["rows"]
    if rws:
        keys = list(rws[0].keys())
        _hdr(t, 1, keys)
        for i, rr in enumerate(rws, 2):
            for j, k in enumerate(keys, 1):
                t.cell(i, j, rr[k])
    k0 = len(rws) + 3
    for i, k in enumerate(("pv_explicit", "pv_excess", "tv", "pv_tv", "ev", "equity", "value_per_share", "tv_share"), k0):
        if k in o["intrinsic"]:
            t.cell(i, 1, k); t.cell(i, 2, o["intrinsic"][k])
    # relative
    rl = wb.create_sheet("Relative")
    _hdr(rl, 1, ["Multiple", "Valid peers", "Median", "P25", "P75", "Usable", "Value/share", "Weight", "Note"])
    for i, (k, v) in enumerate(o["relative"]["multiples"].items(), 2):
        for j, x in enumerate((k, v["n"], v["median"], v["p25"], v["p75"], v["usable"], v["value"],
                               v.get("weight_share", 0), v["reason"]), 1):
            rl.cell(i, j, x)
    # checks
    c = wb.create_sheet("Checks"); _hdr(c, 1, ["Severity", "Code", "Message"])
    for i, ck in enumerate(o["checks"], 2):
        c.cell(i, 1, ck["severity"]); c.cell(i, 2, ck["code"]); c.cell(i, 3, ck["message"])
    c.column_dimensions["C"].width = 110
    # data sources (provenance travels with the results)
    sp = wb.create_sheet("Data sources")
    _hdr(sp, 1, ["Input", "Source as entered"])
    sp.cell(2, 1, "Valuation date"); sp.cell(2, 2, m.get("valuation_date"))
    sp.cell(3, 1, "Data last updated"); sp.cell(3, 2, d.get("last_updated"))
    sp.cell(4, 1, "Reporting currency / unit"); sp.cell(4, 2, f"{m.get('currency')} x {m.get('unit')}")
    r_ = 6
    for k, v in sorted((d.get("sources") or {}).items()):
        if v:
            sp.cell(r_, 1, k); sp.cell(r_, 2, v); r_ += 1
    if r_ == 6:
        sp.cell(r_, 1, "(no source text entered on the input template)"); r_ += 1
    r_ += 1
    sp.cell(r_, 1, "Peers").font = Font(bold=True); r_ += 1
    for p_ in d.get("peers", []):
        if p_.get("name"):
            sp.cell(r_, 1, p_["name"]); sp.cell(r_, 2, p_.get("source")); r_ += 1
    r_ += 1
    sp.cell(r_, 1, "Access and connectivity").font = Font(bold=True)
    sp.cell(r_ + 1, 1, "No subscription, API key or internet connection is required: the model "
                       "computes entirely offline, so the same input file always reproduces this result.")
    sp.column_dimensions["A"].width = 38; sp.column_dimensions["B"].width = 95
    # risks
    rk = wb.create_sheet("Key risks")
    _hdr(rk, 1, ["Severity", "Category", "Risk", "Measure", "Break-even / trigger", "Source"])
    for i, x in enumerate(o.get("risks", []), 2):
        for j, k in enumerate(("severity", "category", "risk", "measure", "break_even", "source"), 1):
            rk.cell(i, j, x.get(k))
    for col, w in zip("ABCDEF", (12, 24, 80, 60, 30, 12)):
        rk.column_dimensions[col].width = w
    # assumptions
    a = wb.create_sheet("Assumptions used"); _hdr(a, 1, ["Key", "Used", "Engine default", "Overridden", "Default rule"])
    for i, k in enumerate(o["assumptions"], 2):
        a.cell(i, 1, k); a.cell(i, 2, o["assumptions"][k] if not isinstance(o["assumptions"][k], (list, dict)) else str(o["assumptions"][k]))
        dv = o["defaults"].get(k); a.cell(i, 3, dv if not isinstance(dv, (list, dict)) else str(dv))
        a.cell(i, 4, "yes" if k in o["overrides"] else ""); a.cell(i, 5, o["assumption_sources"].get(k, ""))
    if path_or_buf is None:
        buf = _io.BytesIO(); wb.save(buf); return buf.getvalue()
    wb.save(path_or_buf)
