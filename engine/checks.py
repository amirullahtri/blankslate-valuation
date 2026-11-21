"""Validation checks (SPEC section 9). Each check: severity, code, message."""
from statistics import median

from .core import _num, latest

REQUIRED_META = ["name", "sector", "currency", "unit", "shares", "share_unit", "price", "valuation_date"]
REQUIRED_FIN = ["revenue", "ebit", "net_income", "equity_parent", "cash", "total_debt"]
REQUIRED_MKT = ["rf", "erp"]


def missing_required(d):
    """Inputs without which no valuation can be attempted. Checked before any calculation."""
    m, mk = d.get("meta", {}), d.get("market", {})
    fin_firm = bool(m.get("is_financial")) or m.get("sector") == "Financials"
    miss = [f"Company: {k}" for k in REQUIRED_META if m.get(k) in (None, "")]
    miss += [f"Financials: {k}" for k in REQUIRED_FIN
             if latest(d, k) is None and not (fin_firm and k == "ebit")]
    miss += [f"Market: {k}" for k in REQUIRED_MKT if _num(mk.get(k)) is None]
    if not d.get("periods"):
        miss.append("Financials: period labels")
    return miss


def run_checks(d, o):
    C = []
    add = lambda sev, code, msg: C.append({"severity": sev, "code": code, "message": msg})
    m, f, mk = d["meta"], d["fin"], d["market"]
    fin_firm = o["financial"]

    # --- missing inputs
    miss = [k for k in REQUIRED_META if m.get(k) in (None, "")]
    miss += [f"fin.{k}" for k in REQUIRED_FIN if latest(d, k) is None and not (fin_firm and k in ("ebit",))]
    miss += [f"market.{k}" for k in REQUIRED_MKT if _num(mk.get(k)) is None]
    if miss:
        add("ERROR", "MISSING_INPUT", "Required inputs missing: " + ", ".join(miss))
    if (_num(m.get("price")) or 0) <= 0 or (_num(m.get("shares")) or 0) <= 0:
        add("ERROR", "PRICE_SHARES", "Share price and shares outstanding must be positive.")

    # --- period order
    P = d["periods"]
    try:
        yrs = [int(str(p)[:4]) for p in P]
        if any(b < a for a, b in zip(yrs, yrs[1:])):
            add("ERROR", "PERIOD_ORDER", "Periods must run from oldest to newest.")
    except ValueError:
        add("WARNING", "PERIOD_LABEL", "Period labels should start with a 4-digit year (e.g. 2025, 2026 TTM).")
    lens = {k: len(v) for k, v in f.items()}
    if any(L != len(P) for L in lens.values()):
        add("ERROR", "PERIOD_LENGTH", "Every financial line must have one value per period.")

    a, r = o["assumptions"], o["rates"]
    gT = a["g_terminal"]
    # --- terminal growth
    rate_T = r["ke"] if fin_firm else r["wacc_T"]
    if rate_T <= gT:
        add("ERROR", "TERMINAL_GROWTH", f"Terminal growth {gT:.2%} must be below the terminal discount rate {rate_T:.2%}.")
    if a["rf"] is not None and gT > a["rf"]:
        add("WARNING", "TERMINAL_ABOVE_RF", f"Terminal growth {gT:.2%} exceeds the risk-free rate {a['rf']:.2%}; a firm cannot outgrow the economy forever.")
    rr = o["intrinsic"].get("terminal_reinvestment_rate")
    if rr is not None and not (0 <= rr < 1):
        add("ERROR", "TERMINAL_REINVESTMENT", f"Terminal reinvestment rate g/ROIC = {rr:.0%} must lie in [0%, 100%).")
    ts = o["intrinsic"].get("tv_share")
    if ts is not None and ts > .85 and not fin_firm:
        add("WARNING", "TV_SHARE", f"Terminal value is {ts:.0%} of enterprise value; result is highly sensitive to long-run assumptions.")

    # --- units / plausibility
    mcap = r["market_cap"]
    bv, rev = latest(d, "equity_parent"), latest(d, "revenue")
    if bv and bv > 0 and mcap:
        pb = mcap / bv
        if pb < 0.05 or pb > 100:
            add("WARNING", "UNIT_PB", f"Implied P/B {pb:,.2f} is implausible: check unit and share_unit.")
    if rev and rev > 0 and mcap and not fin_firm:
        ps = mcap / rev
        if ps < 0.01 or ps > 100:
            add("WARNING", "UNIT_PS", f"Implied P/S {ps:,.2f} is implausible: check unit and share_unit.")
    et = o["history"]["eff_tax_avg3"]
    if et is not None and not (0 <= et <= .5):
        add("WARNING", "TAX_RANGE", f"Average effective tax {et:.1%} outside 0-50%; default bounded.")
    for p in d.get("peers", []):
        if p.get("currency") and p.get("currency") != m.get("currency"):
            add("WARNING", "PEER_CURRENCY", f"Peer {p.get('name')} reported in {p.get('currency')}, target in {m.get('currency')}.")
        if p.get("unit") and _num(p.get("unit")) != _num(m.get("unit")):
            add("WARNING", "PEER_UNIT", f"Peer {p.get('name')} uses a different unit from the target.")

    # --- discount-rate inputs that fall back silently
    if _num(mk.get("beta")) is None and not (mk.get("beta_method") == "bottom-up" and r.get("beta_note", "").startswith("bottom-up:")):
        add("WARNING", "BETA_DEFAULT", f"No beta supplied and no peer betas to build one; beta defaulted to {r['beta']:.2f}. "
                                       "Beta drives the cost of equity directly, so supply one or add peer betas.")
    # P/B compares book equity across companies, so it only means something when intangibles are
    # accounted for alike. An acquisition-built book is not comparable to an organically grown one.
    pb = o["relative"]["multiples"].get("P/B") or {}
    if pb.get("usable"):
        gwi, bvp = latest(d, "goodwill_intangibles"), latest(d, "equity_parent")
        if gwi is not None and bvp not in (None, 0):
            share = gwi / bvp
            if share > 0.30:
                tbv = (bvp - gwi) / (_num(m.get("shares")) or 1)
                add("WARNING", "PB_INTANGIBLE",
                    f"Goodwill and other intangibles are {share:.0%} of book equity, leaving a tangible book of "
                    f"{tbv:,.0f} per share. P/B is only comparable where peers carry intangibles on the same "
                    "basis; an acquisition-built book inflates the denominator and so inflates the value this "
                    "multiple returns. Treat the P/B figure as the least reliable of the four.")
        elif gwi is None:
            add("INFO", "PB_INTANGIBLE",
                "Goodwill and other intangibles were not entered, so P/B comparability could not be checked. "
                "Enter them on the Financials sheet if book equity carries acquired intangibles.")

    # Peer prices must sit on the valuation date. A sector-wide move between the two dates feeds
    # straight into the peer medians and so into the relative value.
    pa = str(m.get("peers_as_of") or d.get("peers_as_of") or "").strip()
    vd = str(m.get("valuation_date") or "").strip()
    if d.get("peers") and pa and vd:
        if pa != vd:
            add("WARNING", "PEER_PRICE_DATE",
                f"Peer market values are dated {pa} but the company is priced at {vd}. Reprice the peers on the "
                "valuation date, or treat the relative value as indicative only.")
    elif d.get("peers") and not pa:
        add("INFO", "PEER_PRICE_DATE",
            "No pricing date recorded for the peers. Record one so the relative value can be checked against the "
            "valuation date.")

    # A regression beta far below the sector's business risk is usually a thin-trading artefact,
    # not low risk. Betas this low push the cost of equity under the cost of debt.
    pbetas = [_num(p.get("beta")) for p in d.get("peers", [])]
    pbetas = [b for b in pbetas if b is not None]
    if pbetas:
        lowb = [b for b in pbetas if b < 0.20]
        if len(lowb) >= max(2, len(pbetas) // 2):
            add("WARNING", "BETA_IMPLAUSIBLE",
                f"{len(lowb)} of {len(pbetas)} peer betas are below 0.20 (range {min(pbetas):.2f} to "
                f"{max(pbetas):.2f}, median {median(sorted(pbetas)):.2f}). Regressions this flat usually mean "
                "thin trading, not low risk, and a bottom-up beta built from them would understate the cost of "
                "equity. Use an industry unlevered beta relevered at the target's capital structure instead.")
    if not fin_firm and r["ke"] <= r["kd"]:
        add("ERROR", "KE_BELOW_KD",
            f"Cost of equity {r['ke']:.2%} is at or below the pre-tax cost of debt {r['kd']:.2%}. Equity is the "
            "junior claim, so this ordering cannot hold; check beta and the credit spread.")
    # The cost of debt enters the WACC only, which is switched off for a financial firm.
    if not fin_firm and _num(mk.get("kd_pretax")) is None and not _num(mk.get("credit_spread")):
        add("WARNING", "SPREAD_DEFAULT", f"No cost of debt or credit spread supplied; a 2.00 pp spread over the risk-free "
                                         f"rate was assumed, giving {r['kd']:.2%} pre-tax.")

    # --- multiples
    usable = [k for k, v in o["relative"]["multiples"].items() if v["usable"]]
    if not usable:
        add("WARNING", "NO_MULTIPLE", "No usable multiple (need >= 3 valid peers and a positive target metric).")
    for k, v in o["relative"]["multiples"].items():
        for nme, val, why in v["excluded"]:
            add("INFO", "MULTIPLE_EXCLUDED", f"{k}: {nme} excluded ({why}).")
        if not v["usable"]:
            add("INFO", "MULTIPLE_UNUSABLE", f"{k} not used: {v['reason']}.")
    if fin_firm:
        add("INFO", "FIN_MODE", "Financial firm: FCFF/WACC and EV multiples switched off.")

    # --- enterprise-to-equity reconciliation
    i = o["intrinsic"]
    if not fin_firm and i.get("ev") is not None:
        b = i["bridge"]
        rebuilt = i["ev"] + b["cash"] + b["non_operating_assets"] - b["total_debt"] - b["lease_liabilities"] - b["minority_interest"]
        if abs(rebuilt - i["equity"]) > 1e-6 * max(1, abs(i["ev"])):
            add("ERROR", "EQUITY_BRIDGE", "Enterprise-to-equity bridge does not reconcile.")
        rel_claims = o["relative"]["claims"]
        bridge_claims = b["total_debt"] + b["lease_liabilities"] + b["minority_interest"] - b["cash"] - b["non_operating_assets"]
        if abs(rel_claims - bridge_claims) > 1e-6 * max(1, abs(bridge_claims)):
            add("ERROR", "BRIDGE_CONSISTENCY", "DCF and relative valuation use different net claims.")
    if i.get("equity") is not None and i["equity"] < 0:
        add("WARNING", "NEGATIVE_EQUITY", "Intrinsic equity value is negative (net claims exceed enterprise value).")

    # --- method divergence / defaults
    comp = o["relative"]["composite"]
    if comp and o["intrinsic_central"]:
        gap = abs(o["intrinsic_central"] - comp["value"]) / max(abs(o["intrinsic_central"]), abs(comp["value"]))
        if gap > .5:
            add("WARNING", "METHOD_GAP", f"Intrinsic and relative values differ by {gap:.0%}; review assumptions and peer set.")
    # The EBIT margin feeds FCFF only, so for a financial firm it is never read.
    if not fin_firm and ("peer median" in o["assumption_sources"].get("target_margin", "")
                         or "fallback" in o["assumption_sources"].get("target_margin", "")):
        add("WARNING", "MARGIN_DEFAULT", "Target margin not derived from own history: " + o["assumption_sources"]["target_margin"] + ".")
    for k in o["overrides"]:
        add("INFO", "OVERRIDE", f"Assumption '{k}' overridden by user (default {o['defaults'].get(k)}).")
    return C
