"""Builds the formula-driven Excel engine (BlankSlate_Valuation.xlsx -> saved as .xlsm after VBA import).

Input sheets (Company, Financials, Market, Peers, Assumptions col C, Settings) use the same layout as the
standard input template, so the VBA importer copies them 1:1. All calculation sheets are formulas that
mirror engine/core.py rule-for-rule.
"""
import sys
sys.path.insert(0, ".")
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, LineChart
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter as CL

from engine.io import blank_template, META_FIELDS, FIN_FIELDS, MARKET_FIELDS, PEER_FIELDS, ASSUMPTION_FIELDS, SETTING_FIELDS, N_PERIODS
from engine.core import SECTORS
from openpyxl import load_workbook
import io

INK, TEAL, ORANGE = "1F3A4D", "17808C", "D2601A"
HEAD = Font(bold=True, color="FFFFFF"); HFILL = PatternFill("solid", fgColor=INK)
CALC = PatternFill("solid", fgColor="EEF3F6"); KEY = PatternFill("solid", fgColor="DDEFF1")
B = Font(bold=True)
PCT, NUM, NUM2, RAT = "0.0%", "#,##0;(#,##0)", "#,##0.00", "0.00"


def build(data=None, out="BlankSlate_Valuation.xlsx"):
    wb = load_workbook(io.BytesIO(blank_template(data=data)))
    names = {}

    def name(n, ref):
        wb.defined_names[n] = DefinedName(n, attr_text=ref)
        names[n] = ref

    def hdr(ws, row, vals, col=1):
        for j, v in enumerate(vals):
            c = ws.cell(row, col + j, v); c.font = HEAD; c.fill = HFILL

    # ---------------------------------------------------------------- README
    rd = wb["README"]
    extra = [
        "",
        "HOW THIS WORKBOOK WORKS",
        "Input sheets (yellow cells): Company, Financials, Market, Peers, Assumptions (column C overrides), Settings.",
        "Calculation sheets (do not edit): Lists, History, Rates, Intrinsic, Relative, Decision, Checks.",
        "Output sheets: Dashboard, Sensitivity (filled by macro), Log (one row per Export).",
        "",
        "MACROS (Developer > Macros, or the buttons on the Dashboard after running SetupButtons once):",
        "  ImportTemplate  - load a filled standard template (.xlsx) for any company",
        "  NewCompany      - clear every input: the blank calculator",
        "  RefreshAll      - recalculate, solve implied growth, run sensitivity grids, stamp the time",
        "  ScenarioBear / ScenarioBase / ScenarioBull - switch the scenario shown on the Dashboard",
        "  ValidateInputs  - highlight missing required inputs and summarise checks",
        "  ExportSummary   - save the Dashboard as PDF + values-only .xlsx and append a row to Log",
        "",
        "Formula logic follows SPEC.md and is identical to the web application's Python engine.",
    ]
    for i, t in enumerate(extra, 9):
        rd.cell(i, 1, t).font = Font(bold=t.isupper() and t != "")

    # ---------------------------------------------------------------- Lists
    L = wb.create_sheet("Lists")
    hdr(L, 1, ["Sector", "Preferred 1", "Preferred 2", "Industry tilt (F1)"])
    for i, (s, v) in enumerate(SECTORS.items(), 2):
        L.cell(i, 1, s); L.cell(i, 2, v["pref"][0]); L.cell(i, 3, v["pref"][1] if len(v["pref"]) > 1 else ""); L.cell(i, 4, v["tilt"])
    nS = len(SECTORS) + 1
    name("tbl_sector", f"Lists!$A$2:$D${nS}")
    L.column_dimensions["A"].width = 30

    # ---------------------------------------------------------------- short refs to inputs
    meta_row = {k: i for i, (k, _, _) in enumerate(META_FIELDS, 2)}
    for k, r in meta_row.items():
        name(f"c_{k}", f"Company!$C${r}")
    # last_updated sits two rows below the last meta field (see engine.io.blank_template). It is
    # named rather than referenced by cell, so adding a Company field cannot silently detach it.
    name("c_last_updated", f"Company!$C${len(META_FIELDS) + 3}")
    fin_row = {k: i for i, (k, _, _) in enumerate(FIN_FIELDS, 3)}
    mk_row = {k: i for i, (k, _, _) in enumerate(MARKET_FIELDS, 2)}
    for k, r in mk_row.items():
        name(f"m_{k}", f"Market!$C${r}")
    st_row = {k: i for i, (k, _) in enumerate(SETTING_FIELDS, 2)}
    for k, r in st_row.items():
        name(f"s_{k}", f"Settings!$C${r}")
    pr = len(SETTING_FIELDS) + 2
    name("s_p_bear", f"Settings!$C${pr}"); name("s_p_base", f"Settings!$D${pr}"); name("s_p_bull", f"Settings!$E${pr}")
    PER = f"Financials!$D$2:${CL(3+N_PERIODS)}$2"
    def FR(k):  # financial row range
        r = fin_row[k]; return f"Financials!$D${r}:${CL(3+N_PERIODS)}${r}"

    # ---------------------------------------------------------------- History
    H = wb.create_sheet("History")
    hdr(H, 1, ["Metric", "Rule", ""] + [f"P{j+1}" for j in range(N_PERIODS)])
    cols = [CL(4 + j) for j in range(N_PERIODS)]
    lastc = cols[-1]
    hrows = [
        ("period", "label", lambda c, p: f'=IF(LEN(Financials!{c}2&"")>0,Financials!{c}2,"")'),
        ("revenue", "", lambda c, p: f'=IF(ISNUMBER(Financials!{c}{fin_row["revenue"]}),Financials!{c}{fin_row["revenue"]},"")'),
        ("ebit", "", lambda c, p: f'=IF(ISNUMBER(Financials!{c}{fin_row["ebit"]}),Financials!{c}{fin_row["ebit"]},"")'),
        ("growth", "Rev_t/Rev_t-1 - 1", lambda c, p: '=""' if p is None else
            f'=IF(AND(ISNUMBER({c}3),ISNUMBER({p}3)),IF(AND({c}3<>0,{p}3<>0),{c}3/{p}3-1,""),"")'),
        ("ebit_margin", "EBIT / revenue", lambda c, p: f'=IF(AND(ISNUMBER({c}3),ISNUMBER({c}4)),IF({c}3<>0,{c}4/{c}3,""),"")'),
        ("eff_tax", "tax / pretax (pretax>0)", lambda c, p: f'=IF(AND(ISNUMBER(Financials!{c}{fin_row["pretax_income"]}),ISNUMBER(Financials!{c}{fin_row["income_tax"]})),IF(Financials!{c}{fin_row["pretax_income"]}>0,Financials!{c}{fin_row["income_tax"]}/Financials!{c}{fin_row["pretax_income"]},""),"")'),
        ("invested_capital", "equity+debt+leases+MI-cash-non-op", lambda c, p: f'=IF(AND(ISNUMBER(Financials!{c}{fin_row["equity_parent"]}),ISNUMBER(Financials!{c}{fin_row["total_debt"]})),Financials!{c}{fin_row["equity_parent"]}+Financials!{c}{fin_row["total_debt"]}+N(Financials!{c}{fin_row["lease_liabilities"]})+N(Financials!{c}{fin_row["minority_interest"]})-N(Financials!{c}{fin_row["cash"]})-N(Financials!{c}{fin_row["non_operating_assets"]}),"")'),
        ("sales_to_capital", "revenue / IC (IC>0)", lambda c, p: f'=IF(AND(ISNUMBER({c}3),ISNUMBER({c}8)),IF(AND({c}3<>0,{c}8>0),{c}3/{c}8,""),"")'),
        ("roe", "NI_t / equity_t-1", lambda c, p: '=""' if p is None else
            f'=IF(AND(ISNUMBER(Financials!{c}{fin_row["net_income"]}),ISNUMBER(Financials!{p}{fin_row["equity_parent"]})),IF(Financials!{p}{fin_row["equity_parent"]}<>0,Financials!{c}{fin_row["net_income"]}/Financials!{p}{fin_row["equity_parent"]},""),"")'),
        ("payout", "|dividends| / NI (NI>0)", lambda c, p: f'=IF(AND(ISNUMBER(Financials!{c}{fin_row["dividends_paid"]}),ISNUMBER(Financials!{c}{fin_row["net_income"]})),IF(Financials!{c}{fin_row["net_income"]}>0,ABS(Financials!{c}{fin_row["dividends_paid"]})/Financials!{c}{fin_row["net_income"]},""),"")'),
        ("fcff", "CFO + interest(1-t) - |capex|", lambda c, p: f'=IF(AND(ISNUMBER(Financials!{c}{fin_row["cfo"]}),ISNUMBER(Financials!{c}{fin_row["capex"]})),Financials!{c}{fin_row["cfo"]}+N(Financials!{c}{fin_row["interest_expense"]})*(1-IF(ISNUMBER({c}7),IF({c}7<>0,{c}7,0.22),0.22))-ABS(Financials!{c}{fin_row["capex"]}),"")'),
        ("rank_margin", "position from latest", lambda c, p: f'=IF(ISNUMBER({c}6),COUNT({c}6:${lastc}6),"")'),
        ("rank_roe", "position from latest", lambda c, p: f'=IF(ISNUMBER({c}10),COUNT({c}10:${lastc}10),"")'),
        ("rank_payout", "position from latest", lambda c, p: f'=IF(ISNUMBER({c}11),COUNT({c}11:${lastc}11),"")'),
    ]
    for i, (k, rule, fn) in enumerate(hrows, 2):
        H.cell(i, 1, k).font = B; H.cell(i, 2, rule)
        for j, c in enumerate(cols):
            cell = H.cell(i, 4 + j, fn(c, cols[j - 1] if j else None)); cell.fill = CALC
            cell.number_format = PCT if k in ("growth", "ebit_margin", "eff_tax", "roe", "payout") else (RAT if k == "sales_to_capital" else NUM)
    R = lambda r: f"History!$D${r}:${lastc}${r}"
    # scalars
    sc = [
        ("h_n", "periods", f'=SUMPRODUCT(--(LEN({PER}&"")>0))', "0"),
        ("h_rev_cnt", "non-zero revenues", f"=SUMPRODUCT(ISNUMBER({R(3)})*({R(3)}<>0))", "0"),
        ("h_rev_first", "first revenue", f'=IFERROR(INDEX({R(3)},MATCH(1,INDEX(ISNUMBER({R(3)})*({R(3)}<>0),0),0)),"")', NUM),
        ("h_rev_last", "last revenue", f'=IFERROR(LOOKUP(2,1/(ISNUMBER({R(3)})*({R(3)}<>0)),{R(3)}),"")', NUM),
        ("h_cagr", "revenue CAGR", '=IF(h_rev_cnt>=2,IF(AND(h_rev_first>0,h_rev_last>0),(h_rev_last/h_rev_first)^(1/(h_rev_cnt-1))-1,""),"")', PCT),
        ("h_margin_cv", "EBIT margin CV", f'=IF(COUNT({R(6)})<2,"",IF(AVERAGE({R(6)})=0,"",STDEV({R(6)})/ABS(AVERAGE({R(6)}))))', RAT),
        ("h_margin_avg3", "avg of last 3 margins", f'=IFERROR(AVERAGEIFS({R(6)},{R(13)},"<=3"),"")', PCT),
        ("h_margin_last", "latest margin", f'=IFERROR(LOOKUP(2,1/ISNUMBER({R(6)}),{R(6)}),"")', PCT),
        ("h_eff_tax_avg3", "avg effective tax, last 3 periods", f'=IFERROR(AVERAGE(OFFSET(History!$D$7,0,MAX(0,h_n-3),1,MIN(3,h_n))),"")', PCT),
        ("h_s2c_median", "median sales-to-capital", f'=IF(COUNT({R(9)})=0,"",MEDIAN({R(9)}))', RAT),
        ("h_roe_avg3", "avg of last 3 ROE", f'=IFERROR(AVERAGEIFS({R(10)},{R(14)},"<=3"),"")', PCT),
        ("h_payout_avg3", "avg of last 3 payout", f'=IFERROR(AVERAGEIFS({R(11)},{R(15)},"<=3"),"")', PCT),
        ("h_fcff_neg_share", "share of periods with FCFF<0", f'=IF(COUNT({R(12)})=0,0,COUNTIF({R(12)},"<0")/COUNT({R(12)}))', PCT),
    ]
    r0 = len(hrows) + 4
    H.cell(r0 - 1, 1, "Scalars").font = B
    for i, (n, desc, f, fmt_) in enumerate(sc, r0):
        H.cell(i, 1, n).font = B; H.cell(i, 2, desc); c = H.cell(i, 3, f); c.fill = KEY; c.number_format = fmt_
        name(n, f"History!$C${i}")
    # latest values of statement lines
    r1 = r0 + len(sc) + 2
    H.cell(r1 - 1, 1, "Latest values (last non-blank)").font = B
    for i, (k, _, _) in enumerate(FIN_FIELDS, r1):
        H.cell(i, 1, f"L_{k}").font = B
        c = H.cell(i, 3, f'=IFERROR(LOOKUP(2,1/ISNUMBER({FR(k)}),{FR(k)}),"")'); c.fill = KEY; c.number_format = NUM
        name(f"L_{k}", f"History!$C${i}")
    H.column_dimensions["A"].width = 20; H.column_dimensions["B"].width = 34; H.column_dimensions["C"].width = 14

    # ---------------------------------------------------------------- Rates
    Rt = wb.create_sheet("Rates")
    hdr(Rt, 1, ["Item", "Formula / rule", "Value"])
    rates = [
        ("r_fin", "financial firm flag", '=OR(c_is_financial=TRUE,UPPER(c_is_financial&"")="TRUE",c_sector="Financials")', None),
        ("r_rf", "risk-free rate", "=m_rf", PCT),
        ("r_erp", "mature ERP", "=m_erp", PCT),
        ("r_crp", "country risk premium (blank=0)", "=N(m_crp)", PCT),
        ("r_tax", "marginal tax (blank=22%)", "=IF(ISNUMBER(m_marginal_tax),m_marginal_tax,0.22)", PCT),
        ("r_kd", "pre-tax cost of debt = given, or rf + spread (blank/0 spread = 2%)",
         "=IF(ISNUMBER(m_kd_pretax),m_kd_pretax,N(r_rf)+IF(N(m_credit_spread)<>0,m_credit_spread,0.02))", PCT),
        ("r_mcap", "market cap = price x shares x share_unit / unit",
         "=IF(ISNUMBER(c_price),c_price,0)*IF(ISNUMBER(c_shares),c_shares,0)*IF(N(c_share_unit)<>0,c_share_unit,1)/IF(N(c_unit)<>0,c_unit,1)", NUM),
        ("r_debt", "debt + leases (latest)", "=N(L_total_debt)+N(L_lease_liabilities)", NUM),
        ("r_dv_current", "current market D/V", "=IF(r_debt+r_mcap>0,r_debt/(r_debt+r_mcap),0)", PCT),
        ("r_dv", "target D/V (blank = current)", "=IF(ISNUMBER(m_target_dv),m_target_dv,r_dv_current)", PCT),
        ("r_de", "target D/E", "=r_dv/(1-r_dv)", RAT),
        ("r_bu_peers", "median unlevered peer beta", '=IFERROR(MEDIAN(Relative!$X$4:$X$18),"")', RAT),
        ("r_beta", "levered beta (user, or bottom-up relevered)",
         '=IF(AND(LOWER(m_beta_method&"")="bottom-up",ISNUMBER(r_bu_peers)),r_bu_peers*(1+(1-r_tax)*r_de),IF(N(m_beta)<>0,m_beta,1))', RAT),
        ("r_ke", "ke = rf + beta x (ERP + CRP)", "=r_rf+r_beta*(r_erp+r_crp)", PCT),
        ("r_wacc", "WACC = ke E/V + kd(1-t) D/V", "=r_ke*(1-r_dv)+r_kd*(1-r_tax)*r_dv", PCT),
        ("r_ke_T", "terminal ke (terminal beta)", "=r_rf+a_terminal_beta*(r_erp+r_crp)", PCT),
        ("r_wacc_T", "terminal WACC", "=r_ke_T*(1-r_dv)+r_kd*(1-r_tax)*r_dv", PCT),
        ("r_psf", "per-share factor = unit / (shares x share_unit)",
         "=IF(N(c_unit)<>0,c_unit,1)/(c_shares*IF(N(c_share_unit)<>0,c_share_unit,1))", "0.000000"),
    ]
    for i, (n, desc, f, fm) in enumerate(rates, 2):
        Rt.cell(i, 1, n).font = B; Rt.cell(i, 2, desc); c = Rt.cell(i, 3, f); c.fill = KEY
        if fm: c.number_format = fm
        name(n, f"Rates!$C${i}")
    Rt.column_dimensions["A"].width = 16; Rt.column_dimensions["B"].width = 62; Rt.column_dimensions["C"].width = 14

    # ---------------------------------------------------------------- Assumptions (D default, E used, F rule)
    A = wb["Assumptions"]
    for col, t in zip("DEF", ["Engine default", "USED", "Default rule"]):
        c = A[f"{col}1"]; c.value = t; c.font = HEAD; c.fill = HFILL
    arow = {k: i for i, (k, _) in enumerate(ASSUMPTION_FIELDS, 2)}
    dflt = {
        "g1": ('=IF(h_cagr="",0.05,MAX(-0.05,MIN(0.3,h_cagr)))', "historical revenue CAGR bounded to [-5%, 30%]"),
        "g_terminal": ("=IF(ISNUMBER(r_rf),MIN(r_rf,0.04),0.03)", "min(rf, 4%)"),
        "target_margin": ('=IF(h_margin_avg3="",IF(Relative!$Z$2>0,Relative!$Z$3,0.1),IF(h_margin_avg3<=0,IF(Relative!$Z$2>0,Relative!$Z$3,0.1),h_margin_avg3))',
                          "3-period average EBIT margin; peer median if history loss-making"),
        "sales_to_capital": ('=MAX(0.5,MIN(5,IF(h_s2c_median="",1.5,IF(h_s2c_median<=0,1.5,h_s2c_median))))', "median historical sales-to-capital, bounded [0.5, 5]"),
        "roic_terminal": ("=r_wacc_T+0.03", "terminal WACC + 3 pp"),
        "eff_tax_start": ('=IF(h_eff_tax_avg3="",0.22,MAX(0,MIN(0.5,h_eff_tax_avg3)))', "3-period average effective tax"),
        "terminal_beta": ("=1", "1.0 (mature firm)"),
        "roe_start": ('=IF(h_roe_avg3="",r_ke,h_roe_avg3)', "3-period average ROE"),
        "roe_terminal": ("=r_ke+0.02", "ke + 2 pp"),
        "payout": ('=IF(h_payout_avg3="",0.4,MAX(0,MIN(0.9,h_payout_avg3)))', "3-period average payout ratio"),
        "w_intrinsic": ("=Decision!$C$10", "method-selection rules (F1-F6)"),
    }
    for k, r in arow.items():
        A.cell(r, 4, dflt[k][0]).fill = CALC
        used = (f"=IF(NOT(rel_ok),1,IF(ISNUMBER(C{r}),MAX(0,MIN(1,C{r})),D{r}))" if k == "w_intrinsic"
                else f"=IF(ISNUMBER(C{r}),C{r},D{r})")
        c = A.cell(r, 5, used); c.fill = KEY; c.font = B
        A.cell(r, 6, dflt[k][1])
        for col in "CDE":
            A[f"{col}{r}"].number_format = RAT if k in ("sales_to_capital", "terminal_beta") else PCT
        name(f"a_{k}", f"Assumptions!$E${r}")
    A.column_dimensions["D"].width = 15; A.column_dimensions["E"].width = 12; A.column_dimensions["F"].width = 60

    # ---------------------------------------------------------------- Relative
    Rl = wb.create_sheet("Relative")
    hdr(Rl, 1, ["Peer valuation helper: stage 1 = valid (positive denominator and multiple); stage 2 = IQR outliers removed when >= 5 valid"])
    Rl.merge_cells("A1:L1")
    mults = [("EV/Revenue", "G", True), ("EV/EBITDA", "H", True), ("P/E", "J", False), ("P/B", "K", False)]
    hdr(Rl, 3, ["Peer", "EV"] + [f"{m} s1" for m, _, _ in mults] + [f"{m} s2" for m, _, _ in mults], 1)
    hdr(Rl, 3, ["Unlev. beta", "", "Peer EBIT margin", "", "Peer ROE"], 24)
    P0, P1 = 2, 16          # peer rows on Peers sheet
    for k in range(P0, P1 + 1):
        r = k + 2           # helper rows 4..18
        Rl.cell(r, 1, f'=IF(LEN(Peers!A{k}&"")>0,Peers!A{k},"")')
        Rl.cell(r, 2, f'=IF(A{r}="","",N(Peers!B{k})+N(Peers!C{k})+N(Peers!D{k})+N(Peers!E{k})-N(Peers!F{k}))').number_format = NUM
        for j, (m, dc, ev) in enumerate(mults):
            numer = f"B{r}" if ev else f"Peers!B{k}"
            f1 = (f'=IF(A{r}="","",IF(AND(ISNUMBER(Peers!{dc}{k}),ISNUMBER({numer})),IF(Peers!{dc}{k}>0,'
                  f'IF({numer}/Peers!{dc}{k}>0,{numer}/Peers!{dc}{k},""),""),""))')
            if m == "P/E":
                # Net income above EBIT means earnings carry a one-off gain: P/E is not comparable.
                f1 = (f'=IF(AND(ISNUMBER(Peers!I{k}),Peers!I{k}>0,N(Peers!J{k})>Peers!I{k}),"",'
                      f'{f1[1:]})')
            if ev:
                f1 = f'=IF(r_fin,"",{f1[1:]})'
            Rl.cell(r, 3 + j, f1).number_format = NUM2
            s1 = f"{CL(3+j)}{r}"
            col1 = f"${CL(3+j)}$4:${CL(3+j)}$18"
            lo = f"(PERCENTILE({col1},0.25)-1.5*(PERCENTILE({col1},0.75)-PERCENTILE({col1},0.25)))"
            hi = f"(PERCENTILE({col1},0.75)+1.5*(PERCENTILE({col1},0.75)-PERCENTILE({col1},0.25)))"
            Rl.cell(r, 7 + j, f'=IF({s1}="","",IF(AND(COUNT({col1})>=5,OR({s1}<{lo},{s1}>{hi})),"",{s1}))').number_format = NUM2
        # unlevered beta for bottom-up
        Rl.cell(r, 24, f'=IF(A{r}="","",IF(AND(ISNUMBER(Peers!L{k}),N(Peers!B{k})<>0),Peers!L{k}/(1+(1-r_tax)*(N(Peers!C{k})+N(Peers!D{k}))/Peers!B{k}),""))').number_format = RAT
        Rl.cell(r, 26, f'=IF(A{r}="","",IF(AND(ISNUMBER(Peers!I{k}),N(Peers!G{k})<>0),IF(Peers!I{k}/Peers!G{k}>0,Peers!I{k}/Peers!G{k},""),""))').number_format = PCT
        # peer ROE, for the F5 test on whether the target is a typical member of its peer set
        Rl.cell(r, 28, f'=IF(A{r}="","",IF(AND(ISNUMBER(Peers!J{k}),N(Peers!K{k})>0),Peers!J{k}/Peers!K{k},""))').number_format = PCT
    Rl["Y2"] = "peer margins >0: count"; Rl["Z2"] = "=COUNT(Z4:Z18)"
    Rl["Y3"] = "median"; Rl["Z3"] = '=IF(Z2>0,MEDIAN(Z4:Z18),"")'
    # summary table
    s0 = 21
    hdr(Rl, s0, ["Multiple", "n stage 1", "n valid", "Median", "P25", "P75", "CV", "Target metric", "Usable",
                 "Value/share", "Low/share", "High/share", "Preferred", "Weight", "Weight share", "Status"])
    claims = "(N(L_total_debt)+N(L_lease_liabilities)+N(L_minority_interest)-N(L_cash)-N(L_non_operating_assets))"
    name("rel_claims", f"Relative!$B${s0+6}")
    tmet = {"EV/Revenue": "L_revenue", "EV/EBITDA": 'IF(ISNUMBER(L_ebit),L_ebit+N(L_d_and_a),"")',
            "P/E": "L_net_income", "P/B": "L_equity_parent"}
    for j, (m, dc, ev) in enumerate(mults):
        r = s0 + 1 + j
        c1 = f"${CL(3+j)}$4:${CL(3+j)}$18"; c2 = f"${CL(7+j)}$4:${CL(7+j)}$18"
        Rl.cell(r, 1, m).font = B
        Rl.cell(r, 2, f"=COUNT({c1})")
        Rl.cell(r, 3, f"=COUNT({c2})")
        Rl.cell(r, 4, f'=IF(C{r}>0,MEDIAN({c2}),"")').number_format = NUM2
        Rl.cell(r, 5, f'=IF(C{r}>0,PERCENTILE({c2},0.25),"")').number_format = NUM2
        Rl.cell(r, 6, f'=IF(C{r}>0,PERCENTILE({c2},0.75),"")').number_format = NUM2
        Rl.cell(r, 7, f'=IF(C{r}<2,"",IF(AVERAGE({c2})=0,"",STDEV({c2})/ABS(AVERAGE({c2}))))').number_format = RAT
        Rl.cell(r, 8, "=" + tmet[m]).number_format = NUM
        Rl.cell(r, 9, (f'=AND(NOT(r_fin),C{r}>=3,ISNUMBER(H{r}),N(H{r})>0)' if ev else f'=AND(C{r}>=3,ISNUMBER(H{r}),N(H{r})>0)'))
        for col, stat in ((10, "D"), (11, "E"), (12, "F")):
            sub = f"-{claims}" if ev else ""
            Rl.cell(r, col, f'=IF(AND(ISNUMBER({stat}{r}),ISNUMBER(H{r})),IF(H{r}>0,({stat}{r}*H{r}{sub})*r_psf,""),"")').number_format = NUM
        Rl.cell(r, 13, f'=OR(IFERROR(VLOOKUP(c_sector,tbl_sector,2,FALSE),"")=A{r},IFERROR(VLOOKUP(c_sector,tbl_sector,3,FALSE),"")=A{r})')
        Rl.cell(r, 14, f'=IF(I{r},IF(M{r},1.5,1)/(1+N(G{r})),0)').number_format = RAT
        Rl.cell(r, 15, f'=IF(SUM($N${s0+1}:$N${s0+4})>0,N{r}/SUM($N${s0+1}:$N${s0+4}),0)').number_format = PCT
        Rl.cell(r, 16, f'=IF(I{r},"usable",IF(C{r}<3,"fewer than 3 valid peers","target metric <= 0 or missing"))')
    rr = s0 + 6
    Rl.cell(rr, 1, "Net claims (debt+leases+MI-cash-non-op)").font = B
    Rl.cell(rr, 2, "=" + claims).number_format = NUM
    rng = lambda col: f"${col}${s0+1}:${col}${s0+4}"
    comp = [("rel_ok", "any usable multiple", f'=SUM({rng("N")})>0', None),
            ("rel_value", "composite value/share", f'=IF(rel_ok,SUMPRODUCT({rng("N")},{rng("J")})/SUM({rng("N")}),"")', NUM),
            ("rel_low", "composite low (P25)", f'=IF(rel_ok,SUMPRODUCT({rng("N")},{rng("K")})/SUM({rng("N")}),"")', NUM),
            ("rel_high", "composite high (P75)", f'=IF(rel_ok,SUMPRODUCT({rng("N")},{rng("L")})/SUM({rng("N")}),"")', NUM)]
    for i, (n, desc, f, fm) in enumerate(comp, rr + 1):
        Rl.cell(i, 1, desc).font = B; c = Rl.cell(i, 2, f); c.fill = KEY
        if fm: c.number_format = fm
        name(n, f"Relative!$B${i}")
    name("rel_tbl", f"Relative!$A${s0+1}:$P${s0+4}")
    Rl.column_dimensions["A"].width = 30
    for j in range(2, 17):
        Rl.column_dimensions[CL(j)].width = 12

    # ---------------------------------------------------------------- Intrinsic blocks
    I = wb.create_sheet("Intrinsic")
    I["A1"] = "Intrinsic valuation blocks: identical formulas, different parameters (scenario, reverse solve, sensitivity)."
    I["A1"].font = B
    blocks = [  # name, g1 shift, margin shift, rate shift, gT shift, growth multiplier cell
        ("BEAR", "-s_scn_growth_delta", "-s_scn_margin_delta", "+s_scn_rate_delta", "", None),
        ("BASE", "", "", "", "", None),
        ("BULL", "+s_scn_growth_delta", "+s_scn_margin_delta", "-s_scn_rate_delta", "", None),
        ("REVERSE", "", "", "", "", "k"),
        ("SENS", "+sens_dg1", "+sens_dm", "+sens_dw", "+sens_dg", None),
    ]
    start = 3
    block_out = {}
    for bname, dg1, dm, dw, dgT, kcell in blocks:
        top = start
        I.cell(top, 1, f"BLOCK {bname}").font = Font(bold=True, size=12, color=TEAL)
        par = top + 1
        p = {}
        labels = [("mult", "growth multiplier (reverse solve)"), ("g1", "year-1 growth"), ("gT", "terminal growth"),
                  ("tm", "target EBIT margin"), ("wacc", "WACC years 1-5"), ("waccT", "terminal WACC"),
                  ("roe0", "starting ROE (financial)"), ("ke", "cost of equity (financial)"), ("m0", "base margin")]
        forms = {
            "mult": "=1",
            "g1": f"=a_g1{dg1}", "gT": f"=a_g_terminal{dgT}", "tm": f"=a_target_margin{dm}",
            "wacc": f"=r_wacc{dw}", "waccT": f"=r_wacc_T{dw}",
            "roe0": None, "ke": f"=r_ke{dw}",
            "m0": None,
        }
        for j, (k, lab) in enumerate(labels):
            r = par + j
            I.cell(r, 1, lab); p[k] = f"$C${r}"
            if k == "roe0":
                f = f"=a_roe_terminal+(a_roe_start{dm}-a_roe_terminal)*{p['mult']}"
            elif k == "m0":
                f = f'=IF(h_margin_last="",{p["tm"]},h_margin_last)'
            else:
                f = forms[k]
            c = I.cell(r, 3, f); c.fill = KEY if not (k == "mult" and kcell) else PatternFill("solid", fgColor="FFF4D6")
            c.number_format = RAT if k == "mult" else PCT
        if kcell:
            name("rev_mult", f"Intrinsic!{p['mult']}")
        # FCFF table
        t0 = par + len(labels) + 1
        cols_f = ["t", "growth", "revenue", "margin", "EBIT", "tax rate", "NOPAT", "reinvestment", "FCFF", "WACC", "DF", "PV"]
        hdr(I, t0, cols_f)
        cols_e = ["t", "ROE", "BV open", "net income", "excess return", "PV", "BV close"]
        hdr(I, t0, cols_e, 15)
        for t in range(1, 11):
            r = t0 + t
            pr_ = r - 1
            I.cell(r, 1, t)
            I.cell(r, 2, f"={p['g1']}*{p['mult']}+({p['gT']}-{p['g1']}*{p['mult']})*(A{r}-1)/9").number_format = PCT
            I.cell(r, 3, (f"=L_revenue*(1+B{r})" if t == 1 else f"=C{pr_}*(1+B{r})")).number_format = NUM
            I.cell(r, 4, f"=IF(A{r}<=5,{p['m0']}+({p['tm']}-{p['m0']})*(A{r}-1)/4,{p['tm']})").number_format = PCT
            I.cell(r, 5, f"=C{r}*D{r}").number_format = NUM
            I.cell(r, 6, f"=a_eff_tax_start+(r_tax-a_eff_tax_start)*(A{r}-1)/9").number_format = PCT
            I.cell(r, 7, f"=IF(E{r}>0,E{r}*(1-F{r}),E{r})").number_format = NUM
            I.cell(r, 8, (f"=(C{r}-L_revenue)/a_sales_to_capital" if t == 1 else f"=(C{r}-C{pr_})/a_sales_to_capital")).number_format = NUM
            I.cell(r, 9, f"=G{r}-H{r}").number_format = NUM
            I.cell(r, 10, f"=IF(A{r}<=5,{p['wacc']},{p['wacc']}+({p['waccT']}-{p['wacc']})*(A{r}-5)/5)").number_format = PCT
            I.cell(r, 11, (f"=1/(1+J{r})" if t == 1 else f"=K{pr_}/(1+J{r})")).number_format = "0.0000"
            I.cell(r, 12, f"=I{r}*K{r}").number_format = NUM
            # excess return
            I.cell(r, 15, t)
            I.cell(r, 16, f"={p['roe0']}+(a_roe_terminal-{p['roe0']})*(O{r}-1)/9").number_format = PCT
            I.cell(r, 17, ("=L_equity_parent" if t == 1 else f"=U{pr_}")).number_format = NUM
            I.cell(r, 18, f"=P{r}*Q{r}").number_format = NUM
            I.cell(r, 19, f"=(P{r}-{p['ke']})*Q{r}").number_format = NUM
            I.cell(r, 20, f"=S{r}/(1+{p['ke']})^O{r}").number_format = NUM
            I.cell(r, 21, f"=Q{r}+R{r}*(1-a_payout)").number_format = NUM
        e = t0 + 10
        s = e + 2
        outs = [
            ("PV explicit FCFF", f"=SUM(L{t0+1}:L{e})"),
            ("FCFF year 11", f"=C{e}*(1+{p['gT']})*{p['tm']}*(1-r_tax)*(1-{p['gT']}/a_roic_terminal)"),
            ("Terminal reinvestment rate g/ROIC", f"={p['gT']}/a_roic_terminal"),
            ("Terminal value", f'=IF({p["waccT"]}>{p["gT"]},C{s+1}/({p["waccT"]}-{p["gT"]}),"")'),
            ("PV terminal value", f'=IF(ISNUMBER(C{s+3}),C{s+3}*K{e},"")'),
            ("Enterprise value", f'=IF(ISNUMBER(C{s+4}),C{s}+C{s+4},"")'),
            ("Equity value", f'=IF(ISNUMBER(C{s+5}),C{s+5}+N(L_cash)+N(L_non_operating_assets)-N(L_total_debt)-N(L_lease_liabilities)-N(L_minority_interest),"")'),
            ("FCFF value per share", f'=IF(ISNUMBER(C{s+6}),C{s+6}*r_psf,"")'),
            ("TV share of EV", f'=IF(AND(ISNUMBER(C{s+5}),ISNUMBER(C{s+4})),IF(C{s+5}>0,C{s+4}/C{s+5},""),"")'),
            ("ER: PV excess returns", f"=SUM(T{t0+1}:T{e})"),
            ("ER: terminal value", f'=IF({p["ke"]}>{p["gT"]},(a_roe_terminal-{p["ke"]})*U{e}/({p["ke"]}-{p["gT"]}),"")'),
            ("ER: PV terminal", f'=IF(ISNUMBER(C{s+10}),C{s+10}/(1+{p["ke"]})^10,"")'),
            ("ER: equity value", f'=IF(ISNUMBER(C{s+11}),L_equity_parent+C{s+9}+C{s+11},"")'),
            ("ER value per share", f'=IF(ISNUMBER(C{s+12}),C{s+12}*r_psf,"")'),
            ("VALUE PER SHARE (model by firm type)", f"=IF(r_fin,C{s+13},C{s+7})"),
            ("10-year revenue CAGR", f'=IF(AND(N(L_revenue)>0,C{e}>0),(C{e}/L_revenue)^(1/10)-1,"")'),
        ]
        for j, (lab, f) in enumerate(outs):
            I.cell(s + j, 1, lab).font = B if "VALUE PER SHARE" in lab else Font()
            c = I.cell(s + j, 3, f); c.fill = KEY
            c.number_format = PCT if ("rate" in lab or "share of" in lab or "CAGR" in lab) else NUM
        block_out[bname] = {"vps": f"Intrinsic!$C${s+14}", "ev": f"Intrinsic!$C${s+5}", "eq": f"Intrinsic!$C${s+6}",
                            "tvshare": f"Intrinsic!$C${s+8}", "rr": f"Intrinsic!$C${s+2}", "pv": f"Intrinsic!$C${s}",
                            "pvtv": f"Intrinsic!$C${s+4}", "cagr": f"Intrinsic!$C${s+15}", "t0": t0, "s": s, "p": p}
        start = s + len(outs) + 2
    for bn, bo in block_out.items():
        name(f"v_{bn.lower()}", bo["vps"])
    name("i_ev", block_out["BASE"]["ev"]); name("i_eq", block_out["BASE"]["eq"]); name("i_tvshare", block_out["BASE"]["tvshare"])
    name("i_rr", block_out["BASE"]["rr"]); name("i_pv", block_out["BASE"]["pv"]); name("i_pvtv", block_out["BASE"]["pvtv"])
    I.column_dimensions["A"].width = 34
    # sensitivity drivers (set by macro) live on Sensitivity sheet
    Sn = wb.create_sheet("Sensitivity")
    Sn["A1"] = "Sensitivity grids (filled by macro RefreshAll; engine-equivalent)"; Sn["A1"].font = Font(bold=True, size=12)
    for i, (n, lab) in enumerate([("sens_dw", "rate shift"), ("sens_dg", "terminal growth shift"),
                                  ("sens_dg1", "year-1 growth shift"), ("sens_dm", "margin shift")], 3):
        Sn.cell(i, 1, lab); Sn.cell(i, 2, 0).fill = KEY; name(n, f"Sensitivity!$B${i}")
    Sn["A8"] = "Discount rate (rows) x terminal growth (columns)"; Sn["A8"].font = B
    Sn["A16"] = "Target margin (rows) x year-1 growth (columns)"; Sn["A16"].font = B
    Sn["A24"] = "Last run"; Sn["B24"] = ""
    name("sens_stamp", "Sensitivity!$B$24")
    name("v_sens_cell", block_out["SENS"]["vps"])

    # ---------------------------------------------------------------- Decision
    D = wb.create_sheet("Decision")
    hdr(D, 1, ["Factor", "Name", "Tilt", "Measure / reason"])
    rel_sum = f"Relative!$A${s0+1}:$P${s0+4}"
    usable_any = "rel_ok"
    best = (f'IFERROR(MATCH(IFERROR(VLOOKUP(c_sector,tbl_sector,2,FALSE),"x"),IF(Relative!$I${s0+1}:$I${s0+4},Relative!$A${s0+1}:$A${s0+4},"#"),0),'
            f'IFERROR(MATCH(IFERROR(VLOOKUP(c_sector,tbl_sector,3,FALSE),"x"),IF(Relative!$I${s0+1}:$I${s0+4},Relative!$A${s0+1}:$A${s0+4},"#"),0),'
            f'MATCH(MAX(Relative!$R${s0+1}:$R${s0+4}),Relative!$R${s0+1}:$R${s0+4},0)))')
    # helper: masked n for usable multiples, and preferred-usable index
    for j in range(4):
        r = s0 + 1 + j
        Rl.cell(r, 18, f"=IF(I{r},C{r},-1)")
        Rl.cell(r, 20, f"=IF(I{r},C{r},9999)")
        Rl.cell(r, 21, f"=IF(I{r},N(G{r}),-1)")
        Rl.cell(r, 19, f'=IF(AND(I{r},A{r}=IFERROR(VLOOKUP(c_sector,tbl_sector,2,FALSE),"x")),1,IF(AND(I{r},A{r}=IFERROR(VLOOKUP(c_sector,tbl_sector,3,FALSE),"x")),2,99))')
    Rl.cell(s0, 18, "n if usable").font = B; Rl.cell(s0, 19, "pref rank").font = B
    Rl.cell(s0 + 6, 18, "best idx").font = B
    Rl.cell(s0 + 6, 19, f'=IF(MIN(S{s0+1}:S{s0+4})<99,MATCH(MIN(S{s0+1}:S{s0+4}),S{s0+1}:S{s0+4},0),MATCH(MAX(R{s0+1}:R{s0+4}),R{s0+1}:R{s0+4},0))')
    name("rel_best", f"Relative!$S${s0+6}")
    best_n = f"INDEX(Relative!$C${s0+1}:$C${s0+4},rel_best)"
    best_cv = f"N(INDEX(Relative!$G${s0+1}:$G${s0+4},rel_best))"
    proe = "Relative!$AB$4:$AB$18"      # peer ROE helper column
    dec = [
        ("F1", "Industry & business model", "=IFERROR(VLOOKUP(c_sector,tbl_sector,4,FALSE),0)",
         '="Sector "&c_sector&": "&CHOOSE(C2+2,"cash flows hard to forecast; market pricing more informative","no structural preference","predictable cash flows favour intrinsic value")'),
        ("F2", "Maturity & growth", '=IF(h_cagr="",0,IF(h_cagr<=0.1,2,IF(h_cagr<=0.2,1,IF(h_cagr<=0.35,-1,-2))))',
         '=IF(h_cagr="","growth history unavailable","Revenue CAGR "&TEXT(h_cagr,"0.0%")&IF(C3>0,": mature, forecastable",": high growth, long-run cash flows uncertain"))'),
        ("F3", "Profitability & cash-flow stability",
         '=IF(r_fin,IF(h_roe_avg3="",-2,IF(h_roe_avg3>0,1,-2)),IF(AND(ISNUMBER(L_ebit),N(L_ebit)<=0),-2,IF(h_margin_cv="",0,MAX(-2,IF(h_margin_cv<0.15,2,IF(h_margin_cv<0.35,1,IF(h_margin_cv<0.6,0,-1)))-IF(h_fcff_neg_share>0.5,1,0)))))',
         '=IF(r_fin,"Average ROE "&IF(h_roe_avg3="","n/a",TEXT(h_roe_avg3,"0.0%")),IF(AND(ISNUMBER(L_ebit),N(L_ebit)<=0),"Latest EBIT is negative: intrinsic value rests on recovery assumptions",IF(h_margin_cv="","Margin volatility not measurable","EBIT margin CV "&TEXT(h_margin_cv,"0.00")&IF(h_fcff_neg_share>0.5,"; historical FCFF negative in most periods",""))))'),
        ("F4", "Information availability & reliability", "=IF(h_n>=5,1,IF(h_n>=3,0,-2))", '=h_n&" periods of financial history"'),
        ("F5", "Availability of suitable peers",
         f"=IF(NOT(rel_ok),0,IF(AND({best_n}>=5,{best_cv}<0.5),-2,IF({best_n}>=5,-1,IF({best_n}>=3,0,1)))"
         f'+IF(AND(COUNT({proe})>=4,N(L_equity_parent)<>0,ISNUMBER(L_net_income),'
         f'OR(L_net_income/L_equity_parent<PERCENTILE({proe},0.25),'
         f'L_net_income/L_equity_parent>PERCENTILE({proe},0.75))),1,0))',
         f'=IF(NOT(rel_ok),"No usable multiple: relative valuation gated off",{best_n}&" valid peers on main multiple ("&INDEX(Relative!$A${s0+1}:$A${s0+4},rel_best)&"), dispersion CV "&TEXT({best_cv},"0.00")'
         f'&IF(AND(COUNT({proe})>=4,N(L_equity_parent)<>0,ISNUMBER(L_net_income),'
         f'OR(L_net_income/L_equity_parent<PERCENTILE({proe},0.25),'
         f'L_net_income/L_equity_parent>PERCENTILE({proe},0.75))),'
         f'"; but the target ROE of "&TEXT(L_net_income/L_equity_parent,"0.0%")&" sits outside the peer interquartile range ("'
         f'&TEXT(PERCENTILE({proe},0.25),"0.0%")&" to "&TEXT(PERCENTILE({proe},0.75),"0.0%")&"), so the median multiple does not describe it",""))'),
        ("F6", "Capital structure & financial sector", "=IF(r_fin,0,IF(r_de>1.5,-1,0))",
         '=IF(r_fin,"Financial firm: FCFF/WACC switched off; excess-return model and P/B, P/E used","Target D/E "&TEXT(r_de,"0.00")&IF(r_de>1.5," (high leverage makes WACC unstable)",""))'),
    ]
    for i, (fid, nm, f, why) in enumerate(dec, 2):
        D.cell(i, 1, fid).font = B; D.cell(i, 2, nm); c = D.cell(i, 3, f); c.fill = KEY; D.cell(i, 4, why)
    D["A9"] = "Total tilt"; D["C9"] = "=SUM(C2:C7)"; D["A9"].font = B
    D["A10"] = "Weight intrinsic = clip(50% + 5% x tilt, 20%, 80%); 100% if relative gated off"
    D["C10"] = "=IF(NOT(rel_ok),1,MAX(0.2,MIN(0.8,0.5+0.05*C9)))"; D["C10"].number_format = PCT
    D["A11"] = "Weight relative"; D["C11"] = "=1-C10"; D["C11"].number_format = PCT
    name("d_tilt", "Decision!$C$9"); name("w_i", "Decision!$C$10"); name("w_r", "Decision!$C$11")
    D.column_dimensions["B"].width = 38; D.column_dimensions["D"].width = 95; D.column_dimensions["A"].width = 12

    # ---------------------------------------------------------------- Checks
    C = wb.create_sheet("Checks")
    hdr(C, 1, ["Severity", "Code", "Triggered?", "Message"])
    req_meta = " ,".join([])
    miss_meta = "+".join([f'(LEN(c_{k}&"")=0)' for k in ["name", "sector", "currency", "unit", "shares", "share_unit", "price", "valuation_date"]])
    miss_fin = "+".join([f'(L_{k}="")' for k in ["revenue", "net_income", "equity_parent", "cash", "total_debt"]]) + '+AND(NOT(r_fin),L_ebit="")'
    miss_mk = '(NOT(ISNUMBER(m_rf)))+(NOT(ISNUMBER(m_erp)))'
    checks = [
        ("ERROR", "MISSING_INPUT", f"=({miss_meta}+{miss_fin}+{miss_mk})>0", "Required inputs missing (Company, Financials latest values, Market rf/ERP). Run ValidateInputs to highlight them."),
        ("ERROR", "PRICE_SHARES", "=OR(N(c_price)<=0,N(c_shares)<=0)", "Share price and shares outstanding must be positive."),
        ("ERROR", "PERIOD_ORDER", f'=SUMPRODUCT((LEN(Financials!$E$2:${lastc}$2&"")>0)*(IFERROR(VALUE(LEFT(Financials!$E$2:${lastc}$2&"",4)),0)<IFERROR(VALUE(LEFT(Financials!$D$2:${CL(2+N_PERIODS)}$2&"",4)),0)))>0', "Periods must run from oldest to newest."),
        ("ERROR", "TERMINAL_GROWTH", "=IF(r_fin,r_ke<=a_g_terminal,r_wacc_T<=a_g_terminal)", "Terminal growth must be below the terminal discount rate."),
        ("ERROR", "TERMINAL_REINVESTMENT", '=AND(NOT(r_fin),OR(i_rr<0,i_rr>=1))', "Terminal reinvestment rate g/ROIC must lie in [0%, 100%)."),
        ("ERROR", "EQUITY_BRIDGE", '=AND(NOT(r_fin),ISNUMBER(i_ev),ABS(i_ev-rel_claims-i_eq)>0.000001*MAX(1,ABS(i_ev)))', "Enterprise-to-equity bridge does not reconcile (DCF vs relative net claims)."),
        ("WARNING", "TERMINAL_ABOVE_RF", "=AND(ISNUMBER(m_rf),a_g_terminal>m_rf)", "Terminal growth exceeds the risk-free rate."),
        ("WARNING", "TV_SHARE", '=AND(NOT(r_fin),ISNUMBER(i_tvshare),N(i_tvshare)>0.85)', "Terminal value exceeds 85% of enterprise value."),
        ("WARNING", "UNIT_PB", '=AND(N(L_equity_parent)>0,r_mcap>0,OR(r_mcap/L_equity_parent<0.05,r_mcap/L_equity_parent>100))', "Implied P/B implausible: check unit and share_unit."),
        ("WARNING", "UNIT_PS", '=AND(NOT(r_fin),N(L_revenue)>0,r_mcap>0,OR(r_mcap/L_revenue<0.01,r_mcap/L_revenue>100))', "Implied P/S implausible: check unit and share_unit."),
        ("WARNING", "TAX_RANGE", '=AND(ISNUMBER(h_eff_tax_avg3),OR(h_eff_tax_avg3<0,h_eff_tax_avg3>0.5))', "Average effective tax outside 0-50%; default bounded."),
        ("WARNING", "NO_MULTIPLE", "=NOT(rel_ok)", "No usable multiple (need >= 3 valid peers and a positive target metric)."),
        ("WARNING", "NEGATIVE_EQUITY", '=AND(ISNUMBER(v_base),v_base<0)', "Intrinsic equity value is negative."),
        ("WARNING", "METHOD_GAP", '=AND(rel_ok,ISNUMBER(o_intr),IFERROR(ABS(o_intr-rel_value)/MAX(ABS(o_intr),ABS(rel_value))>0.5,FALSE))', "Intrinsic and relative values differ by more than 50%."),
        ("WARNING", "MARGIN_DEFAULT", '=AND(NOT(r_fin),NOT(ISNUMBER(Assumptions!$C$4)),OR(h_margin_avg3="",N(h_margin_avg3)<=0))', "Target margin not derived from own history (peer median or 10% fallback)."),
        ("WARNING", "PB_INTANGIBLE", f'=AND(Relative!$I${s0+4},ISNUMBER(L_goodwill_intangibles),N(L_equity_parent)<>0,L_goodwill_intangibles/L_equity_parent>0.3)',
         "Goodwill and intangibles exceed 30% of book equity: P/B is not like-for-like against peers and overstates the value this multiple returns."),
        ("WARNING", "BETA_IMPLAUSIBLE", '=AND(COUNT(Peers!$L$2:$L$16)>0,COUNTIF(Peers!$L$2:$L$16,"<0.2")>=MAX(2,ROUNDDOWN(COUNT(Peers!$L$2:$L$16)/2,0)))',
         "Half or more of the peer betas are below 0.20: regressions this flat usually mean thin trading, so use an industry beta relevered at the target's D/E."),
        ("ERROR", "KE_BELOW_KD", "=AND(NOT(r_fin),r_ke<=r_kd)",
         "Cost of equity is at or below the pre-tax cost of debt; equity is the junior claim, so check beta and the credit spread."),
        ("WARNING", "PEER_PRICE_DATE", '=AND(COUNT(Peers!$B$2:$B$16)>0,LEN(c_peers_as_of&"")>0,(c_peers_as_of&"")<>(c_valuation_date&""))',
         "Peer market values are not dated on the valuation date. Reprice the peers, or treat the relative value as indicative only."),
        ("INFO", "PEER_PRICE_DATE", '=AND(COUNT(Peers!$B$2:$B$16)>0,LEN(c_peers_as_of&"")=0)',
         "No pricing date recorded for the peers; enter one on the Company sheet so it can be checked against the valuation date."),
        ("INFO", "PB_INTANGIBLE", f'=AND(Relative!$I${s0+4},NOT(ISNUMBER(L_goodwill_intangibles)))',
         "Goodwill and intangibles not entered, so P/B comparability could not be checked."),
        ("INFO", "OVERRIDE", f"=COUNT(Assumptions!$C$2:$C${1 + len(ASSUMPTION_FIELDS)})>0",
         "One or more assumptions overridden by the user."),
        ("INFO", "FIN_MODE", "=r_fin", "Financial firm: FCFF/WACC and EV multiples switched off."),
    ]
    for i, (sev, code, f, msg) in enumerate(checks, 2):
        C.cell(i, 1, sev); C.cell(i, 2, code); C.cell(i, 3, f).fill = KEY; C.cell(i, 4, msg)
    ne = len(checks) + 1
    C.cell(ne + 2, 1, "Errors triggered").font = B; C.cell(ne + 2, 3, f'=COUNTIFS(A2:A{ne},"ERROR",C2:C{ne},TRUE)')
    C.cell(ne + 3, 1, "Warnings triggered").font = B; C.cell(ne + 3, 3, f'=COUNTIFS(A2:A{ne},"WARNING",C2:C{ne},TRUE)')
    name("chk_err", f"Checks!$C${ne+2}"); name("chk_warn", f"Checks!$C${ne+3}")
    red = PatternFill("solid", fgColor="F6D5D5")
    C.conditional_formatting.add(f"A2:D{ne}", FormulaRule(formula=["$C2=TRUE"], fill=red))
    C.column_dimensions["B"].width = 24; C.column_dimensions["D"].width = 90

    # ---------------------------------------------------------------- Dashboard
    Db = wb.create_sheet("Dashboard", 1)
    Db.sheet_view.showGridLines = False
    Db["B2"] = '=IF(LEN(c_name&"")=0,"BlankSlate Valuation Calculator (no company loaded)",c_name&" ("&c_ticker&")")'
    Db["B2"].font = Font(bold=True, size=18, color=INK)
    Db["B3"] = '="Sector: "&c_sector&"   |   Valuation date: "&c_valuation_date&"   |   Data last updated: "&c_last_updated&"   |   Model: "&IF(r_fin,"excess-return (financial firm)","FCFF DCF")'
    Db["B3"].font = Font(color="5A6B77")
    out_rows = [
        ("o_price", "Market price", "=c_price", NUM),
        ("o_bear", "Intrinsic - bear", "=v_bear", NUM), ("o_base", "Intrinsic - base", "=v_base", NUM), ("o_bull", "Intrinsic - bull", "=v_bull", NUM),
        ("o_intr", "Intrinsic - scenario-weighted", '=IFERROR(s_p_bear*v_bear+s_p_base*v_base+s_p_bull*v_bull,"")', NUM),
        ("o_rel", "Relative - composite", "=rel_value", NUM), ("o_rel_lo", "Relative - P25", "=rel_low", NUM), ("o_rel_hi", "Relative - P75", "=rel_high", NUM),
        ("o_wi", "Weight intrinsic (chosen)", "=a_w_intrinsic", PCT), ("o_wr", "Weight relative", "=1-o_wi", PCT),
        ("o_wi_sug", "Weight intrinsic proposed by the rules", "=w_i", PCT),
        ("o_c_raw", "Fair value central", '=IF(ISNUMBER(o_intr),IF(rel_ok,o_wi*o_intr+o_wr*rel_value,o_intr),"")', NUM),
        ("o_l_raw", "(raw low)", '=IF(ISNUMBER(o_intr),IF(rel_ok,o_wi*v_bear+o_wr*rel_low,v_bear),"")', NUM),
        ("o_h_raw", "(raw high)", '=IF(ISNUMBER(o_intr),IF(rel_ok,o_wi*v_bull+o_wr*rel_high,v_bull),"")', NUM),
        ("o_low", "Fair value low", '=IF(ISNUMBER(o_c_raw),MIN(o_l_raw,o_h_raw,o_c_raw),"")', NUM),
        ("o_high", "Fair value high", '=IF(ISNUMBER(o_c_raw),MAX(o_l_raw,o_h_raw,o_c_raw),"")', NUM),
        ("o_up", "Upside / downside", '=IF(AND(ISNUMBER(o_c_raw),N(o_price)>0),o_c_raw/o_price-1,"")', PCT),
        ("o_call", "RECOMMENDATION", '=IF(OR(chk_err>0,NOT(ISNUMBER(o_up))),"NO RECOMMENDATION",IF(o_up>=s_buy_threshold,"BUY",IF(o_up<=s_sell_threshold,"SELL","HOLD")))', None),
        ("o_width", "Range width / central", '=IF(ISNUMBER(o_c_raw),IF(o_c_raw>0,(o_high-o_low)/o_c_raw,9.99),"")', PCT),
        ("o_gap", "Method gap / central", '=IF(AND(rel_ok,ISNUMBER(o_c_raw)),IF(o_c_raw<>0,ABS(o_intr-rel_value)/ABS(o_c_raw),0),0)', PCT),
        ("o_conf", "Confidence", '=IF(o_call="NO RECOMMENDATION","",IF(AND(o_width<0.4,o_gap<0.25),"High",IF(OR(o_width>0.8,o_gap>0.5),"Low","Medium")))', None),
        ("o_impl_g1", "Implied year-1 growth (reverse, by macro)", '=IF(r_fin,"",a_g1*rev_mult)', PCT),
        ("o_impl_roe", "Implied starting ROE (reverse, by macro)", '=IF(r_fin,a_roe_terminal+(a_roe_start-a_roe_terminal)*rev_mult,"")', PCT),
        ("o_scn", "Scenario shown (macro)", "BASE", None),
        ("o_scn_val", "Intrinsic value, scenario shown", '=CHOOSE(MATCH(o_scn,{"BEAR","BASE","BULL"},0),v_bear,v_base,v_bull)', NUM),
    ]
    r = 6
    Db.cell(r - 1, 2, "Output").font = HEAD; Db.cell(r - 1, 2).fill = HFILL
    Db.cell(r - 1, 3, "Value").font = HEAD; Db.cell(r - 1, 3).fill = HFILL
    for i, (n, lab, f, fm) in enumerate(out_rows, r):
        Db.cell(i, 2, lab); c = Db.cell(i, 3, f); c.fill = KEY
        if fm: c.number_format = fm
        if n in ("o_call", "o_c_raw", "o_up"):
            Db.cell(i, 2).font = B; c.font = Font(bold=True, size=13)
        name(n, f"Dashboard!$C${i}")
    Db.column_dimensions["A"].width = 2; Db.column_dimensions["B"].width = 42; Db.column_dimensions["C"].width = 20
    callc = names["o_call"].split("!")[1].replace("$", "")
    for txt, colr in (("BUY", "CDEBEE"), ("SELL", "F6D5D5"), ("HOLD", "FBE3D1")):
        Db.conditional_formatting.add(callc, FormulaRule(formula=[f'{callc}="{txt}"'], fill=PatternFill("solid", fgColor=colr)))
    # football field data
    fr = r + len(out_rows) + 2
    Db.cell(fr, 2, "Football field").font = B
    for j, t in enumerate(["Method", "Low", "Range", "Central", "Price"]):
        Db.cell(fr + 1, 2 + j, t).font = B
    ff = [("Intrinsic", "=o_bear", "=o_bull-o_bear", "=o_intr"),
          ("Relative", "=rel_low", "=rel_high-rel_low", "=rel_value"),
          ("Blended fair value", "=o_low", "=o_high-o_low", "=o_c_raw")]
    for j, (lab, lo, rg, mid) in enumerate(ff, fr + 2):
        Db.cell(j, 2, lab); Db.cell(j, 3, f'=IFERROR(MIN({lo[1:]},{lo[1:]}+{rg[1:]}),0)'); Db.cell(j, 4, f'=IFERROR(ABS({rg[1:]}),0)')
        Db.cell(j, 5, mid); Db.cell(j, 6, "=o_price")
        for col in (3, 4, 5, 6):
            Db.cell(j, col).number_format = NUM
    ch = BarChart(); ch.type = "bar"; ch.grouping = "stacked"; ch.overlap = 100
    ch.title = "Value per share: low to high by method"; ch.height = 7.5; ch.width = 17
    ch.add_data(Reference(Db, min_col=3, max_col=4, min_row=fr + 1, max_row=fr + 4), titles_from_data=True)
    ch.set_categories(Reference(Db, min_col=2, min_row=fr + 2, max_row=fr + 4))
    ch.series[0].graphicalProperties.noFill = True; ch.series[0].graphicalProperties.line.noFill = True
    ch.series[1].graphicalProperties.solidFill = TEAL
    ch.legend = None
    Db.add_chart(ch, "E5")
    # decision chart
    dch = BarChart(); dch.type = "bar"; dch.title = "Method-selection tilts (-2 relative ... +2 intrinsic)"
    dch.add_data(Reference(D, min_col=3, min_row=1, max_row=7), titles_from_data=True)
    dch.set_categories(Reference(D, min_col=2, min_row=2, max_row=7)); dch.legend = None; dch.height = 7.5; dch.width = 17
    dch.series[0].graphicalProperties.solidFill = ORANGE
    Db.add_chart(dch, "E21")
    # history chart
    hch = BarChart(); hch.title = "Revenue and EBIT (history)"; hch.height = 7.5; hch.width = 17
    hch.add_data(Reference(H, min_col=3, max_col=3 + N_PERIODS, min_row=3, max_row=4), from_rows=True, titles_from_data=True)
    hch.set_categories(Reference(H, min_col=4, max_col=3 + N_PERIODS, min_row=2))
    Db.add_chart(hch, "E37")
    H["C3"] = "revenue"; H["C4"] = "EBIT"

    # ---------------------------------------------------------------- Log
    Lg = wb.create_sheet("Log")
    hdr(Lg, 1, ["Timestamp", "Company", "Valuation date", "Price", "Intrinsic", "Relative", "W intrinsic", "Fair value",
                "Low", "High", "Upside", "Call", "Confidence", "Errors", "Warnings"])


    # ---------------------------------------------------------------- Key risks (output)
    Rk = wb.create_sheet("Key risks")
    hdr(Rk, 1, ["Severity", "Category", "Risk", "Measure / evidence", "Break-even or trigger", "Source"])
    U = "Relative!$I$22:$I$25"
    n_min = 'IF(rel_ok,MIN(Relative!$T$22:$T$25),0)'
    cv_max = 'IF(rel_ok,MAX(Relative!$U$22:$U$25),0)'
    rows_r = [
        ('=IF(r_fin,"Low",IF(N(i_tvshare)>0.75,"High",IF(N(i_tvshare)>0.6,"Medium","Low")))',
         "Forecast horizon",
         "Most of the intrinsic value lies beyond the 10-year forecast, so it rests on terminal assumptions rather than on projected cash flows.",
         '=IF(r_fin,"Excess returns fade to the terminal spread","Terminal value is "&TEXT(N(i_tvshare),"0%")&" of enterprise value")', ""),
        ('=IF(rev_mult=1,"Low",IF(r_fin,IF(ABS(o_impl_roe-a_roe_start)>0.05,"High",IF(ABS(o_impl_roe-a_roe_start)>0.02,"Medium","Low")),IF(ABS(o_impl_g1-a_g1)>0.08,"High",IF(ABS(o_impl_g1-a_g1)>0.03,"Medium","Low"))))',
         "Market expectation",
         "The market price embeds different performance from the model's; the valuation gap is an expectation gap, not only a cash-flow gap.",
         '=IF(rev_mult=1,"Run the macro Refresh all to solve what the price implies",IF(r_fin,"Price implies starting ROE "&TEXT(o_impl_roe,"0.0%")&" vs model "&TEXT(a_roe_start,"0.0%"),"Price implies year-1 growth "&TEXT(o_impl_g1,"0.0%")&" vs model "&TEXT(a_g1,"0.0%")))', ""),
        ('="High"', '=IF(r_fin,"Profitability","Operating margin")',
         "The recommendation reverses if the profitability driver settles at the level shown.",
         '=IF(r_fin,"Model uses starting ROE "&TEXT(a_roe_start,"0.0%"),"Model uses target EBIT margin "&TEXT(a_target_margin,"0.0%")&IF(h_margin_avg3="","","; 3-period history "&TEXT(h_margin_avg3,"0.0%")))', "BE_MARGIN"),
        ('=IF(r_fin,"Low","Medium")', "Terminal growth",
         "The recommendation reverses at the terminal growth rate shown. A rate close to the discount rate makes the terminal value unstable.",
         '="Model uses "&TEXT(a_g_terminal,"0.00%")&"; spread to terminal discount rate "&TEXT(IF(r_fin,r_ke,r_wacc_T)-a_g_terminal,"0.0%")', "BE_GROWTH"),
        (f'=IF(NOT(rel_ok),"High",IF(OR({cv_max}>0.6,{n_min}<4),"High",IF({cv_max}>0.35,"Medium","Low")))',
         "Peer comparability",
         "Relative value depends on how alike the peers really are; wide dispersion means the median carries little information.",
         f'=IF(NOT(rel_ok),"No usable multiple: fewer than 3 valid peers everywhere",{n_min}&" valid peers at the narrowest multiple; widest dispersion CV "&TEXT({cv_max},"0.00"))', ""),
        ('=IF(NOT(rel_ok),"Low",IF(o_gap>0.4,"High",IF(o_gap>0.15,"Medium","Low")))', "Method divergence",
         "The two methods point to different values; the blended figure hides that disagreement, so the weights matter as much as the inputs.",
         '=IF(NOT(rel_ok),"Relative valuation unavailable","Intrinsic "&TEXT(o_intr,"#,##0")&" vs relative "&TEXT(rel_value,"#,##0")&" ("&TEXT(o_gap,"0%")&" apart), weighted "&TEXT(o_wi,"0%")&"/"&TEXT(o_wr,"0%"))', ""),
        ('=IF(r_fin,"Low",IF(h_margin_cv="","Low",IF(h_margin_cv>0.6,"High",IF(h_margin_cv>0.35,"Medium","Low"))))',
         "Earnings stability",
         "Margins have moved enough in the past that a single target margin may not hold.",
         '=IF(h_margin_cv="","Margin volatility not measurable","EBIT-margin coefficient of variation "&TEXT(h_margin_cv,"0.00")&" over "&h_n&" periods")', ""),
        ('=IF(AND(NOT(r_fin),h_fcff_neg_share>0.3),"Medium","Low")', "Cash conversion",
         "Free cash flow was negative in part of the history, so reinvestment may exceed the model's sales-to-capital assumption.",
         '="FCFF negative in "&TEXT(h_fcff_neg_share,"0%")&" of measured periods"', ""),
        ('=IF(r_fin,"Low",IF(r_de>1.5,"High",IF(r_de>0.8,"Medium","Low")))', "Capital structure",
         "Leverage raises the equity beta and makes the valuation more sensitive to rates.",
         '="Target D/E "&TEXT(r_de,"0.00")&", D/V "&TEXT(r_dv,"0.0%")', ""),
        ('=IF(h_n>=5,"Low",IF(h_n>=3,"Medium","High"))', "Information quality",
         "A short history gives the defaults a thin base, so overrides carry more weight.",
         '=h_n&" periods of financial history"', ""),
    ]
    for i, (sev, cat, risk, meas, be) in enumerate(rows_r, 2):
        Rk.cell(i, 1, sev); Rk.cell(i, 2, cat); Rk.cell(i, 3, risk); Rk.cell(i, 4, meas)
        c = Rk.cell(i, 5, "")
        if be:
            c.fill = PatternFill("solid", fgColor="FFF4D6")
            name("be_margin" if be == "BE_MARGIN" else "be_growth", f"Key risks!$E${i}")
        Rk.cell(i, 6, "model")
    n0 = len(rows_r) + 2
    Rk.cell(n0, 1, "Analyst-entered risks (Risks sheet)").font = B
    for j in range(12):
        i = n0 + 1 + j
        Rk.cell(i, 1, f'=IF(LEN(Risks!B{2+j}&"")=0,"",IF(LEN(Risks!E{2+j}&"")=0,"Medium",Risks!E{2+j}))')
        Rk.cell(i, 2, f'=IF(LEN(Risks!B{2+j}&"")=0,"",IF(LEN(Risks!A{2+j}&"")=0,"Analyst-identified",Risks!A{2+j}))')
        Rk.cell(i, 3, f'=IF(LEN(Risks!B{2+j}&"")=0,"",Risks!B{2+j})')
        Rk.cell(i, 4, f'=IF(LEN(Risks!B{2+j}&"")=0,"",Risks!C{2+j})')
        Rk.cell(i, 5, f'=IF(LEN(Risks!B{2+j}&"")=0,"",Risks!D{2+j})')
        Rk.cell(i, 6, f'=IF(LEN(Risks!B{2+j}&"")=0,"","analyst")')
    Rk.cell(n0 + 14, 1, "Break-even cells are filled by the macro BuildRiskRegister (Excel Goal Seek). "
                        "The web application also solves a WACC break-even, which Goal Seek cannot reach "
                        "here because WACC is computed rather than entered.")
    red2 = PatternFill("solid", fgColor="F6D5D5"); amb = PatternFill("solid", fgColor="FBE3D1")
    Rk.conditional_formatting.add(f"A2:F{n0+13}", FormulaRule(formula=['$A2="High"'], fill=red2))
    Rk.conditional_formatting.add(f"A2:F{n0+13}", FormulaRule(formula=['$A2="Medium"'], fill=amb))
    for col, w in zip("ABCDEF", (12, 22, 78, 62, 28, 10)):
        Rk.column_dimensions[col].width = w

    # sheet order
    order = ["README", "Dashboard", "Company", "Financials", "Market", "Peers", "Assumptions", "Risks",
             "Settings", "History", "Rates", "Intrinsic", "Relative", "Decision", "Checks", "Key risks",
             "Sensitivity", "Log", "Lists"]
    wb._sheets = [wb[n] for n in order]
    for n in ["History", "Rates", "Intrinsic", "Relative", "Decision", "Checks", "Key risks", "Lists"]:
        wb[n].sheet_properties.tabColor = "8A9AA5"
    for n in ["Company", "Financials", "Market", "Peers", "Assumptions", "Risks", "Settings"]:
        wb[n].sheet_properties.tabColor = "F0A93B"
    wb["Dashboard"].sheet_properties.tabColor = TEAL
    wb.active = 1
    wb.save(out)
    return names


if __name__ == "__main__":
    import json
    from examples import SAMPLE
    out = sys.argv[1] if len(sys.argv) > 1 else "BlankSlate_Valuation.xlsx"
    build(SAMPLE if "--sample" in sys.argv else None, out)
    print("saved", out)
