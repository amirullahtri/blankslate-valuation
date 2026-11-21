"""BlankSlate Valuation Calculator - calculation engine.

Company-agnostic: every number comes from the input dict (data + assumption overrides).
See SPEC.md for the rules implemented here. Units: statement figures are in `unit`
(e.g. 1e9); shares in `share_unit` (e.g. 1e6); price in currency per share.
"""
from __future__ import annotations
import math
from copy import deepcopy
from statistics import median

SECTORS = {
    "Consumer staples":            {"pref": ["P/E", "EV/EBITDA"], "tilt": 1},
    "Consumer discretionary":      {"pref": ["EV/EBITDA", "P/E"], "tilt": 0},
    "Healthcare":                  {"pref": ["EV/EBITDA", "P/E"], "tilt": 1},
    "Telecom & infrastructure":    {"pref": ["EV/EBITDA"], "tilt": 1},
    "Utilities & energy":          {"pref": ["EV/EBITDA"], "tilt": 1},
    "Industrials":                 {"pref": ["EV/EBITDA", "P/E"], "tilt": 0},
    "Technology & internet":       {"pref": ["EV/Revenue", "EV/EBITDA"], "tilt": -1},
    "Commodities & resources":     {"pref": ["EV/EBITDA"], "tilt": -1},
    "Property & real estate":      {"pref": ["P/B"], "tilt": -1},
    "Financials":                  {"pref": ["P/B", "P/E"], "tilt": 0},
}
EV_MULTIPLES = ["EV/Revenue", "EV/EBITDA"]
EQ_MULTIPLES = ["P/E", "P/B"]

DEFAULT_SETTINGS = {
    "buy_threshold": 0.15, "sell_threshold": -0.15,
    "scenario_prob": [0.25, 0.50, 0.25],          # bear, base, bull
    "scn_growth_delta": 0.03, "scn_margin_delta": 0.02, "scn_rate_delta": 0.005,
    "years": 10,
}

# ----------------------------------------------------------------- helpers
def _num(x):
    try:
        if x is None or (isinstance(x, str) and x.strip() == ""):
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def _clip(x, lo, hi):
    return max(lo, min(hi, x))

def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[f] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)

def _cv(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    if m == 0:
        return None
    sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
    return sd / abs(m)

def lin(a, b, n, i):
    """value at step i (1..n) moving linearly from a (i=1) to b (i=n)."""
    return a if n <= 1 else a + (b - a) * (i - 1) / (n - 1)

# ----------------------------------------------------------------- history
def analyse_history(d):
    f, P = d["fin"], d["periods"]
    n = len(P)
    g = lambda k, i: _num(f.get(k, [None] * n)[i]) if i < len(f.get(k, [])) else None
    rows = []
    for i in range(n):
        rev, ebit = g("revenue", i), g("ebit", i)
        pre, tax = g("pretax_income", i), g("income_tax", i)
        eff = (tax / pre) if (pre and tax is not None and pre > 0) else None
        ic = None
        parts = [g("equity_parent", i), g("total_debt", i), g("lease_liabilities", i) or 0,
                 g("minority_interest", i) or 0]
        if None not in parts[:2]:
            ic = sum(parts) - (g("cash", i) or 0) - (g("non_operating_assets", i) or 0)
        rows.append({
            "period": P[i], "revenue": rev, "ebit": ebit,
            "growth": (rev / g("revenue", i - 1) - 1) if i and rev and g("revenue", i - 1) else None,
            "ebit_margin": (ebit / rev) if (rev and ebit is not None) else None,
            "eff_tax": eff, "invested_capital": ic,
            "sales_to_capital": (rev / ic) if (rev and ic and ic > 0) else None,
            "roe": (g("net_income", i) / g("equity_parent", i - 1))
                   if i and g("net_income", i) is not None and g("equity_parent", i - 1) else None,
            "payout": (abs(g("dividends_paid", i)) / g("net_income", i))
                      if g("dividends_paid", i) is not None and g("net_income", i) and g("net_income", i) > 0 else None,
            "fcff": (g("cfo", i) + (g("interest_expense", i) or 0) * (1 - (eff or 0.22)) - abs(g("capex", i)))
                    if g("cfo", i) is not None and g("capex", i) is not None else None,
        })
    revs = [r["revenue"] for r in rows if r["revenue"]]
    yrs = len(revs) - 1
    cagr = (revs[-1] / revs[0]) ** (1 / yrs) - 1 if yrs >= 1 and revs[0] > 0 and revs[-1] > 0 else None
    margins = [r["ebit_margin"] for r in rows if r["ebit_margin"] is not None]
    return {
        "rows": rows, "n_periods": n, "cagr": cagr,
        "margin_cv": _cv(margins),
        "margin_avg3": _avg(margins[-3:]) if margins else None,
        "margin_last": margins[-1] if margins else None,
        "eff_tax_avg3": _avg([r["eff_tax"] for r in rows][-3:]),
        "s2c_median": median([r["sales_to_capital"] for r in rows if r["sales_to_capital"]])
                      if any(r["sales_to_capital"] for r in rows) else None,
        "roe_avg3": _avg([r["roe"] for r in rows if r["roe"] is not None][-3:]),
        "payout_avg3": _avg([r["payout"] for r in rows if r["payout"] is not None][-3:]),
        "fcff_negative_share": (sum(1 for r in rows if r["fcff"] is not None and r["fcff"] < 0) /
                                max(1, sum(1 for r in rows if r["fcff"] is not None))),
    }

def latest(d, key):
    v = d["fin"].get(key, [])
    for x in reversed(v):
        if _num(x) is not None:
            return _num(x)
    return None

# ----------------------------------------------------------------- relative
def peer_ev(p):
    return (_num(p.get("market_cap")) or 0) + (_num(p.get("total_debt")) or 0) + \
           (_num(p.get("lease_liabilities")) or 0) + (_num(p.get("minority_interest")) or 0) - \
           (_num(p.get("cash")) or 0)

def _roe_of(d):
    """Latest return on equity for the target, on closing book equity."""
    ni, eq = latest(d, "net_income"), latest(d, "equity_parent")
    return None if ni is None or not eq else ni / eq


def peer_roes(peers):
    """Return on equity for each peer that reports both inputs with positive book equity."""
    out = []
    for p in peers:
        ni, eq = _num(p.get("net_income")), _num(p.get("equity_book"))
        if ni is not None and eq is not None and eq > 0:
            out.append(ni / eq)
    return out


def peer_multiples(peers, financial):
    names = ["P/E", "P/B"] if financial else ["EV/Revenue", "EV/EBITDA", "P/E", "P/B"]
    den = {"EV/Revenue": "revenue", "EV/EBITDA": "ebitda", "P/E": "net_income", "P/B": "equity_book"}
    out = {}
    for m in names:
        vals, log = [], []
        for p in peers:
            num = peer_ev(p) if m in EV_MULTIPLES else _num(p.get("market_cap"))
            dv = _num(p.get(den[m]))
            if dv is None or num is None:
                log.append((p.get("name"), None, "missing data")); continue
            if dv <= 0:
                log.append((p.get("name"), None, f"{den[m]} <= 0")); continue
            # Earnings below the operating line can be inflated by disposals or other one-offs.
            # Net income above EBIT is the signature, and it makes P/E meaningless for that peer.
            if m == "P/E":
                pe_ebit = _num(p.get("ebit"))
                if pe_ebit is not None and pe_ebit > 0 and dv > pe_ebit:
                    log.append((p.get("name"), num / dv,
                                "net income exceeds EBIT: earnings carry a one-off gain"))
                    continue
            x = num / dv
            if not math.isfinite(x) or x <= 0:
                log.append((p.get("name"), None, "non-positive multiple")); continue
            vals.append((p.get("name"), x))
        if len(vals) >= 5:
            xs = [v for _, v in vals]
            q1, q3 = _pct(xs, .25), _pct(xs, .75)
            lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            keep = []
            for nme, v in vals:
                if lo <= v <= hi:
                    keep.append((nme, v))
                else:
                    log.append((nme, v, "outlier (IQR rule)"))
            vals = keep
        xs = [v for _, v in vals]
        out[m] = {"valid": vals, "excluded": log,
                  "median": median(xs) if xs else None,
                  "p25": _pct(xs, .25), "p75": _pct(xs, .75),
                  "cv": _cv(xs), "n": len(xs)}
    return out

def relative_valuation(d, h, financial):
    meta = d["meta"]
    pm = peer_multiples(d.get("peers", []), financial)
    claims = (latest(d, "total_debt") or 0) + (latest(d, "lease_liabilities") or 0) + \
             (latest(d, "minority_interest") or 0) - (latest(d, "cash") or 0) - \
             (latest(d, "non_operating_assets") or 0)
    ebitda = None
    if latest(d, "ebit") is not None:
        ebitda = latest(d, "ebit") + (latest(d, "d_and_a") or 0)
    tgt = {"EV/Revenue": latest(d, "revenue"), "EV/EBITDA": ebitda,
           "P/E": latest(d, "net_income"), "P/B": latest(d, "equity_parent")}
    pref = SECTORS.get(meta.get("sector"), {}).get("pref", [])
    per_share = per_share_factor(d)
    res = {}
    for m, s in pm.items():
        t = tgt.get(m)
        usable = s["n"] >= 3 and t is not None and t > 0
        reason = "usable" if usable else ("fewer than 3 valid peers" if s["n"] < 3 else "target metric <= 0 or missing")
        vals = {}
        for k in ("median", "p25", "p75"):
            if s[k] is None or t is None or t <= 0:
                vals[k] = None; continue
            v = s[k] * t
            eq = v - claims if m in EV_MULTIPLES else v
            vals[k] = eq * per_share
        w = ((1.5 if m in pref else 1.0) / (1 + (s["cv"] or 0))) if usable else 0.0
        res[m] = {**s, "target_metric": t, "usable": usable, "reason": reason,
                  "value": vals["median"], "low": vals["p25"], "high": vals["p75"], "weight": w}
    tw = sum(r["weight"] for r in res.values())
    comp = None
    if tw > 0:
        comp = {k: sum(r["weight"] * r[src] for r in res.values() if r["usable"]) / tw
                for k, src in (("value", "value"), ("low", "low"), ("high", "high"))}
        for r in res.values():
            r["weight_share"] = r["weight"] / tw
    return {"multiples": res, "composite": comp, "claims": claims}

def per_share_factor(d):
    m = d["meta"]
    return (_num(m.get("unit")) or 1) / ((_num(m.get("shares")) or float("nan")) * (_num(m.get("share_unit")) or 1))

# ----------------------------------------------------------------- rates
def discount_rates(d, h, a):
    mk, m = d["market"], d["meta"]
    rf, erp, crp = a["rf"], a["erp"], a["crp"]
    t = a["marginal_tax"]
    mcap = (_num(m["price"]) or 0) * (_num(m["shares"]) or 0) * (_num(m.get("share_unit")) or 1) / (_num(m.get("unit")) or 1)
    debt = (latest(d, "total_debt") or 0) + (latest(d, "lease_liabilities") or 0)
    dv_current = debt / (debt + mcap) if (debt + mcap) > 0 else 0
    dv = a["target_dv"] if a.get("target_dv") is not None else dv_current
    de = dv / (1 - dv) if dv < 1 else float("inf")
    beta_note = ""
    if a.get("beta_method") == "bottom-up" and d.get("peers"):
        bus = []
        for p in d["peers"]:
            bl, mc = _num(p.get("beta")), _num(p.get("market_cap"))
            if bl is None or not mc:
                continue
            pd_ = (_num(p.get("total_debt")) or 0) + (_num(p.get("lease_liabilities")) or 0)
            bus.append(bl / (1 + (1 - t) * pd_ / mc))
        if bus:
            bu = median(bus)
            beta = bu * (1 + (1 - t) * de)
            beta_note = f"bottom-up: median unlevered beta {bu:.3f} of {len(bus)} peers, relevered at D/E {de:.2f}"
        else:
            beta = a["beta"]; beta_note = "bottom-up requested but peer betas missing; user beta used"
    else:
        beta = a["beta"]; beta_note = "user levered beta"
    ke = rf + beta * (erp + crp)
    kd = a["kd_pretax"]
    wacc = ke * (1 - dv) + kd * (1 - t) * dv
    ke_T = rf + a["terminal_beta"] * (erp + crp)
    wacc_T = ke_T * (1 - dv) + kd * (1 - t) * dv
    return {"rf": rf, "erp": erp, "crp": crp, "beta": beta, "beta_note": beta_note, "ke": ke,
            "kd": kd, "kd_after_tax": kd * (1 - t), "dv": dv, "dv_current": dv_current, "de": de,
            "wacc": wacc, "ke_T": ke_T, "wacc_T": wacc_T, "market_cap": mcap}

# ----------------------------------------------------------------- defaults
def default_assumptions(d, h):
    mk = d["market"]
    rf = _num(mk.get("rf"))
    margin_src = "3-period average EBIT margin"
    tm = h["margin_avg3"]
    if tm is None or tm <= 0:
        pm = [(_num(p.get("ebit")) / _num(p.get("revenue"))) for p in d.get("peers", [])
              if _num(p.get("ebit")) is not None and _num(p.get("revenue"))]
        pm = [x for x in pm if x > 0]
        tm = median(pm) if pm else 0.10
        margin_src = "peer median EBIT margin (history loss-making)" if pm else "fallback 10% (no data)"
    s2c = h["s2c_median"]
    s2c_src = "median historical sales-to-capital"
    if s2c is None or s2c <= 0:
        s2c, s2c_src = 1.5, "fallback 1.5 (history invalid)"
    a = {
        "rf": rf, "erp": _num(mk.get("erp")), "crp": _num(mk.get("crp")) or 0.0,
        "beta": _num(mk.get("beta")) or 1.0,
        "beta_method": mk.get("beta_method", "user"),
        "kd_pretax": _num(mk.get("kd_pretax")) if _num(mk.get("kd_pretax")) is not None
                     else (rf or 0) + (_num(mk.get("credit_spread")) or 0.02),
        "marginal_tax": _num(mk.get("marginal_tax")) if _num(mk.get("marginal_tax")) is not None else 0.22,
        "target_dv": _num(mk.get("target_dv")),
        "terminal_beta": 1.0,
        "g1": _clip(h["cagr"], -0.05, 0.30) if h["cagr"] is not None else 0.05,
        "g_terminal": min(rf, 0.04) if rf is not None else 0.03,
        "target_margin": tm,
        "sales_to_capital": _clip(s2c, 0.5, 5.0),
        "roic_terminal": None,   # filled after rates (WACC_T + 3pp)
        "eff_tax_start": _clip(h["eff_tax_avg3"], 0, 0.5) if h["eff_tax_avg3"] is not None else 0.22,
        "roe_start": h["roe_avg3"], "roe_terminal": None,
        "payout": _clip(h["payout_avg3"], 0, 0.9) if h["payout_avg3"] is not None else 0.4,
    }
    src = {"g1": "historical revenue CAGR bounded to [-5%, 30%]", "g_terminal": "min(rf, 4%)",
           "target_margin": margin_src, "sales_to_capital": s2c_src,
           "eff_tax_start": "3-period average effective tax", "terminal_beta": "1.0 (mature firm)",
           "roic_terminal": "terminal WACC + 3 pp", "roe_terminal": "ke + 2 pp",
           "payout": "3-period average payout ratio"}
    return a, src

# ----------------------------------------------------------------- intrinsic
def fcff_dcf(d, h, a, r, years=10, growth_mult=1.0):
    rev0 = latest(d, "revenue")
    m0 = h["margin_last"] if h["margin_last"] is not None else a["target_margin"]
    gT, roicT = a["g_terminal"], a["roic_terminal"]
    rows, df, prev = [], 1.0, rev0
    for t in range(1, years + 1):
        g = lin(a["g1"] * growth_mult, gT, years, t) if t < years else gT
        if t == 1:
            g = a["g1"] * growth_mult
        rev = prev * (1 + g)
        margin = lin(m0, a["target_margin"], 5, t) if t <= 5 else a["target_margin"]
        ebit = rev * margin
        tax = lin(a["eff_tax_start"], a["marginal_tax"], years, t)
        nopat = ebit * (1 - tax) if ebit > 0 else ebit
        reinv = (rev - prev) / a["sales_to_capital"]
        fcff = nopat - reinv
        w = r["wacc"] if t <= 5 else lin(r["wacc"], r["wacc_T"], years - 4, t - 4)
        df = df / (1 + w)
        rows.append({"year": t, "growth": g, "revenue": rev, "margin": margin, "ebit": ebit, "tax": tax,
                     "nopat": nopat, "reinvestment": reinv, "fcff": fcff, "wacc": w, "df": df, "pv": fcff * df})
        prev = rev
    rev11 = prev * (1 + gT)
    nopat11 = rev11 * a["target_margin"] * (1 - a["marginal_tax"])
    rr = gT / roicT if roicT else None
    fcff11 = nopat11 * (1 - rr) if rr is not None else None
    tv = fcff11 / (r["wacc_T"] - gT) if (fcff11 is not None and r["wacc_T"] > gT) else None
    pv_tv = tv * df if tv is not None else None
    pv_sum = sum(x["pv"] for x in rows)
    ev = pv_sum + pv_tv if pv_tv is not None else None
    bridge = {"cash": latest(d, "cash") or 0, "non_operating_assets": latest(d, "non_operating_assets") or 0,
              "total_debt": latest(d, "total_debt") or 0, "lease_liabilities": latest(d, "lease_liabilities") or 0,
              "minority_interest": latest(d, "minority_interest") or 0}
    equity = (ev + bridge["cash"] + bridge["non_operating_assets"] - bridge["total_debt"]
              - bridge["lease_liabilities"] - bridge["minority_interest"]) if ev is not None else None
    vps = equity * per_share_factor(d) if equity is not None else None
    return {"model": "FCFF DCF", "rows": rows, "pv_explicit": pv_sum, "terminal_fcff": fcff11,
            "terminal_reinvestment_rate": rr, "tv": tv, "pv_tv": pv_tv, "ev": ev,
            "tv_share": (pv_tv / ev) if (ev and pv_tv is not None and ev > 0) else None,
            "bridge": bridge, "equity": equity, "value_per_share": vps,
            "rev_cagr_10y": (prev / rev0) ** (1 / years) - 1 if rev0 and prev > 0 else None}

def excess_return(d, h, a, r, years=10, growth_mult=1.0):
    bv0 = latest(d, "equity_parent")
    ke, gT = r["ke"], a["g_terminal"]
    roe0 = a["roe_start"] if a["roe_start"] is not None else ke
    roeT = a["roe_terminal"]
    roe0 = roeT + (roe0 - roeT) * growth_mult   # scenario lever: excess ROE scaled
    rows, bv, pv = [], bv0, 0.0
    for t in range(1, years + 1):
        roe = lin(roe0, roeT, years, t)
        ni = roe * bv
        exc = (roe - ke) * bv
        pv_t = exc / (1 + ke) ** t
        pv += pv_t
        bv_new = bv + ni * (1 - a["payout"])
        rows.append({"year": t, "roe": roe, "bv_open": bv, "net_income": ni, "excess": exc, "pv": pv_t})
        bv = bv_new
    tv = (roeT - ke) * bv / (ke - gT) if ke > gT else None
    pv_tv = tv / (1 + ke) ** years if tv is not None else None
    equity = bv0 + pv + pv_tv if pv_tv is not None else None
    vps = equity * per_share_factor(d) if equity is not None else None
    return {"model": "Excess-return (financial firm)", "rows": rows, "bv0": bv0, "pv_excess": pv,
            "tv": tv, "pv_tv": pv_tv, "equity": equity, "value_per_share": vps,
            "tv_share": (pv_tv / (equity - bv0)) if equity and equity != bv0 and pv_tv is not None else None,
            "ev": None, "terminal_reinvestment_rate": gT / roeT if roeT else None}

def intrinsic(d, h, a, r, financial, growth_mult=1.0):
    return (excess_return if financial else fcff_dcf)(d, h, a, r, growth_mult=growth_mult)


def scenarios_of(d, h, a, r, financial, S):
    """Bear/base/bull intrinsic values; the scenario levers differ by firm type."""
    gd, md, rd = S["scn_growth_delta"], S["scn_margin_delta"], S["scn_rate_delta"]
    scn = {}
    for name, sgn in (("bear", -1), ("base", 0), ("bull", 1)):
        a2, r2 = dict(a), dict(r)
        if financial:
            a2["roe_start"] = a["roe_start"] + sgn * md
            r2["ke"] = r["ke"] - sgn * rd
        else:
            a2["g1"] = a["g1"] + sgn * gd
            a2["target_margin"] = a["target_margin"] + sgn * md
            r2["wacc"] = r["wacc"] - sgn * rd
            r2["wacc_T"] = r["wacc_T"] - sgn * rd
        res = intrinsic(d, h, a2, r2, financial)
        scn[name] = {"value": res["value_per_share"], "g1": a2.get("g1"),
                     "target_margin": a2.get("target_margin"), "roe_start": a2.get("roe_start"),
                     "rate": r2["ke"] if financial else r2["wacc"]}
    return scn


def scenario_central(d, h, a, r, financial, S):
    """Probability-weighted intrinsic value per share, or None if any scenario fails."""
    scn = scenarios_of(d, h, a, r, financial, S)
    vals = [scn[k]["value"] for k in ("bear", "base", "bull")]
    if None in vals:
        return None
    return sum(pi * v for pi, v in zip(S["scenario_prob"], vals))

# ----------------------------------------------------------------- decision
def decide(d, h, rel, financial, r):
    sector = d["meta"].get("sector")
    fs = []
    # F1
    t1 = SECTORS.get(sector, {}).get("tilt", 0)
    fs.append(("F1", "Industry & business model", t1,
               f"Sector '{sector}': " + {1: "predictable cash flows favour intrinsic value",
                                          0: "no structural preference", -1: "cash flows hard to forecast; market pricing more informative"}[t1]))
    # F2
    c = h["cagr"]
    if c is None:
        t2, why = 0, "growth history unavailable"
    else:
        t2 = 2 if c <= .10 else 1 if c <= .20 else -1 if c <= .35 else -2
        why = f"Revenue CAGR {c:.1%}: " + ("mature, forecastable" if t2 > 0 else "high growth, long-run cash flows uncertain")
    fs.append(("F2", "Maturity & growth", t2, why))
    # F3
    if financial:
        roe = h["roe_avg3"]
        t3 = 1 if (roe and roe > 0) else -2
        why = f"Average ROE {roe:.1%}" if roe is not None else "ROE unavailable"
    else:
        last_ebit = latest(d, "ebit")
        cv = h["margin_cv"]
        if last_ebit is not None and last_ebit <= 0:
            t3, why = -2, "Latest EBIT is negative: intrinsic value rests on recovery assumptions"
        elif cv is None:
            t3, why = 0, "Margin volatility not measurable"
        else:
            t3 = 2 if cv < .15 else 1 if cv < .35 else 0 if cv < .60 else -1
            why = f"EBIT margin coefficient of variation {cv:.2f}"
            if h["fcff_negative_share"] > .5:
                t3 = max(-2, t3 - 1); why += "; historical FCFF negative in most periods"
    fs.append(("F3", "Profitability & cash-flow stability", t3, why))
    # F4
    n = h["n_periods"]
    t4 = 1 if n >= 5 else 0 if n >= 3 else -2
    fs.append(("F4", "Information availability & reliability", t4, f"{n} periods of financial history"))
    # F5
    pref = SECTORS.get(sector, {}).get("pref", [])
    usable = {k: v for k, v in rel["multiples"].items() if v["usable"]}
    gate_rel = not usable
    if gate_rel:
        t5, why = 0, "No usable multiple: relative valuation gated off"
    else:
        best = next((usable[p] for p in pref if p in usable), max(usable.values(), key=lambda v: v["n"]))
        nv, cv = best["n"], best["cv"] or 0
        t5 = -2 if (nv >= 5 and cv < .5) else -1 if nv >= 5 else 0 if nv >= 3 else 1
        why = f"{nv} valid peers on main multiple, dispersion CV {cv:.2f}"
        # A tight peer set still misleads when the target is not a typical member of it. Return on
        # equity is what drives both P/B and P/E, so if the target sits outside the peers'
        # interquartile range on ROE, the median multiple does not describe this company.
        t_roe, p_roes = _roe_of(d), peer_roes(d.get("peers", []))
        if t_roe is not None and len(p_roes) >= 4:
            q1, q3 = _pct(sorted(p_roes), .25), _pct(sorted(p_roes), .75)
            if q1 is not None and q3 is not None and not (q1 <= t_roe <= q3):
                t5 += 1
                side = "above" if t_roe > q3 else "below"
                why += (f"; but the target's ROE of {t_roe:.1%} sits {side} the peer interquartile range "
                        f"({q1:.1%} to {q3:.1%}), so the median multiple does not describe it")
    fs.append(("F5", "Availability of suitable peers", t5, why))
    # F6
    if financial:
        t6, why = 0, "Financial firm: FCFF/WACC switched off; excess-return model and P/B, P/E used"
    else:
        de = r["de"]
        t6 = -1 if de > 1.5 else 0
        why = f"Target D/E {de:.2f}" + (" (high leverage makes WACC unstable)" if t6 else "")
    fs.append(("F6", "Capital structure & financial sector", t6, why))
    total = sum(f[2] for f in fs)
    w_i = _clip(0.5 + 0.05 * total, 0.2, 0.8)
    gate_note = ""
    if gate_rel:
        w_i, gate_note = 1.0, "relative valuation unavailable"
    return {"factors": [{"id": f[0], "name": f[1], "tilt": f[2], "reason": f[3]} for f in fs],
            "total_tilt": total, "w_intrinsic": w_i, "w_relative": 1 - w_i, "gate": gate_note}

# ----------------------------------------------------------------- reverse
def reverse_solve(d, h, a, r, financial, price):
    f = lambda k: (intrinsic(d, h, a, r, financial, growth_mult=k)["value_per_share"] or -1e18) - price
    lo, hi = -2.0, 6.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        # No growth level in the tested range reaches the market price, so the disagreement with
        # the market is not about growth. Say which way it fails and what the bound is worth,
        # rather than returning nothing: the register then solves on the discount rate instead.
        vlo = intrinsic(d, h, a, r, financial, growth_mult=lo)["value_per_share"]
        vhi = intrinsic(d, h, a, r, financial, growth_mult=hi)["value_per_share"]
        above = flo > 0
        return {"multiplier": None, "bracketed": False, "above_price": above,
                "value_at_low_growth": vlo, "value_at_high_growth": vhi,
                "note": ("Growth alone cannot explain the gap to the market price. Even at the bottom of the "
                         f"tested range the model returns {vlo:,.0f} per share against a price of {price:,.0f}, "
                         "so the market is pricing something other than slower growth: a higher discount rate, "
                         "weaker margins, or a discount this model does not carry."
                         if above else
                         "Even at the top of the tested growth range the model stays below the market price "
                         f"({vhi:,.0f} against {price:,.0f}), so the market is pricing more than growth alone.")}
    for _ in range(80):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    k = (lo + hi) / 2
    res = intrinsic(d, h, a, r, financial, growth_mult=k)
    out = {"multiplier": k}
    if financial:
        out["implied_roe_start"] = a["roe_terminal"] + (a["roe_start"] - a["roe_terminal"]) * k
    else:
        out["implied_g1"] = a["g1"] * k
        out["implied_rev_cagr_10y"] = res["rev_cagr_10y"]
    return out

# ----------------------------------------------------------------- run
def run(data, overrides=None, settings=None):
    d = deepcopy(data)
    S = {**DEFAULT_SETTINGS, **(settings or {})}
    financial = bool(d["meta"].get("is_financial")) or d["meta"].get("sector") == "Financials"
    h = analyse_history(d)
    from .checks import missing_required
    miss = missing_required(d)
    if miss:
        # A blank calculator must refuse an incomplete template, not crash on it.
        return {"ok": False, "financial": financial, "history": h, "settings": S,
                "assumptions": {}, "defaults": {}, "assumption_sources": {}, "overrides": {},
                "rates": {}, "intrinsic": {"model": "not computed", "rows": []}, "scenarios": {},
                "intrinsic_central": None,
                "relative": {"multiples": {}, "composite": None, "claims": None},
                "decision": {"factors": [], "total_tilt": 0, "w_intrinsic": None,
                             "w_relative": None, "gate": "inputs incomplete"},
                "sens_rate": [], "sens_ops": [], "reverse": None, "risks": [],
                "price": _num(d["meta"].get("price")), "fair_value": None,
                "checks": [{"severity": "ERROR", "code": "MISSING_INPUT",
                            "message": "Required inputs missing: " + ", ".join(miss)}],
                "recommendation": {"call": "NO RECOMMENDATION", "upside": None, "confidence": None,
                                   "rationale": f"{len(miss)} required input(s) missing. "
                                                "Complete the template, then recalculate."}}
    a, a_src = default_assumptions(d, h)
    defaults = dict(a)
    ov = {k: v for k, v in (overrides or {}).items() if v is not None}
    a.update(ov)
    r = discount_rates(d, h, a)
    if a.get("roic_terminal") is None:
        a["roic_terminal"] = r["wacc_T"] + 0.03
        defaults["roic_terminal"] = a["roic_terminal"]
    if a.get("roe_terminal") is None:
        a["roe_terminal"] = r["ke"] + 0.02
        defaults["roe_terminal"] = a["roe_terminal"]
    if a.get("roe_start") is None:
        a["roe_start"] = r["ke"]

    base = intrinsic(d, h, a, r, financial)
    scn = scenarios_of(d, h, a, r, financial, S)
    p = S["scenario_prob"]
    vals = [scn[k]["value"] for k in ("bear", "base", "bull")]
    intr_central = sum(pi * v for pi, v in zip(p, vals)) if None not in vals else None

    rel = relative_valuation(d, h, financial)
    dec = decide(d, h, rel, financial, r)
    # the model proposes the weights; the user may select otherwise ("help users select")
    if ov.get("w_intrinsic") is not None and not dec["gate"]:
        dec["w_suggested"] = dec["w_intrinsic"]
        dec["w_intrinsic"] = _clip(float(ov["w_intrinsic"]), 0.0, 1.0)
        dec["w_relative"] = 1 - dec["w_intrinsic"]
        dec["weight_overridden"] = True

    # sensitivity grids
    sens_rate = []
    rate_key = "ke" if financial else "wacc"
    for dw in (-0.02, -0.01, 0, 0.01, 0.02):
        row = []
        for dg in (-0.01, -0.005, 0, 0.005, 0.01):
            a2, r2 = dict(a), dict(r)
            a2["g_terminal"] = a["g_terminal"] + dg
            r2[rate_key] = r[rate_key] + dw
            if not financial:
                r2["wacc_T"] = r["wacc_T"] + dw
            v = intrinsic(d, h, a2, r2, financial)["value_per_share"]
            row.append(v)
        sens_rate.append({"rate": r[rate_key] + dw, "values": row})
    sens_ops = []
    if not financial:
        for dm in (-0.04, -0.02, 0, 0.02, 0.04):
            row = []
            for dg in (-0.10, -0.05, 0, 0.05, 0.10):
                a2 = dict(a); a2["g1"] = a["g1"] + dg; a2["target_margin"] = a["target_margin"] + dm
                row.append(intrinsic(d, h, a2, r, financial)["value_per_share"])
            sens_ops.append({"target_margin": a["target_margin"] + dm, "values": row})

    price = _num(d["meta"]["price"])
    rev = reverse_solve(d, h, a, r, financial, price) if price else None

    # blend
    comp = rel["composite"]
    wi, wr = dec["w_intrinsic"], dec["w_relative"]
    fv = None
    if intr_central is not None:
        if comp:
            fv = {"central": wi * intr_central + wr * comp["value"],
                  "low": wi * scn["bear"]["value"] + wr * comp["low"],
                  "high": wi * scn["bull"]["value"] + wr * comp["high"]}
        else:
            fv = {"central": intr_central, "low": scn["bear"]["value"], "high": scn["bull"]["value"]}
        fv["low"], fv["high"] = min(fv["low"], fv["high"], fv["central"]), max(fv["low"], fv["high"], fv["central"])

    out = {"ok": True, "financial": financial, "history": h, "assumptions": a, "defaults": defaults,
           "assumption_sources": a_src, "overrides": ov, "rates": r, "intrinsic": base,
           "scenarios": scn, "intrinsic_central": intr_central, "relative": rel, "decision": dec,
           "sens_rate": sens_rate, "sens_ops": sens_ops, "reverse": rev, "settings": S, "price": price,
           "fair_value": fv}
    from .checks import run_checks
    out["checks"] = run_checks(d, out)
    out["recommendation"] = recommend(out, S)
    from .risks import build_risks
    try:
        out["risks"] = build_risks(d, out)
    except Exception as e:  # noqa: BLE001 - a risk-register failure must not break the valuation
        out["risks"] = []
        out["checks"].append({"severity": "INFO", "code": "RISK_REGISTER",
                              "message": f"Risk register could not be built: {e}"})
    return out

def recommend(o, S):
    errs = [c for c in o["checks"] if c["severity"] == "ERROR"]
    fv, price = o["fair_value"], o["price"]
    if errs or not fv or not price:
        return {"call": "NO RECOMMENDATION", "upside": None, "confidence": None,
                "rationale": "Resolve ERROR checks first." if errs else "Fair value or price unavailable."}
    up = fv["central"] / price - 1
    call = "BUY" if up >= S["buy_threshold"] else "SELL" if up <= S["sell_threshold"] else "HOLD"
    width = (fv["high"] - fv["low"]) / fv["central"] if fv["central"] > 0 else float("inf")
    comp = o["relative"]["composite"]
    gap = abs(o["intrinsic_central"] - comp["value"]) / abs(fv["central"]) if comp and fv["central"] else 0
    conf = "High" if (width < .40 and gap < .25) else "Low" if (width > .80 or gap > .50) else "Medium"
    return {"call": call, "upside": up, "confidence": conf, "range_width": width, "method_gap": gap,
            "rationale": (f"Central value {fv['central']:,.0f} vs price {price:,.0f} ({up:+.1%}); "
                          f"BUY if >= {S['buy_threshold']:+.0%}, SELL if <= {S['sell_threshold']:+.0%}.")}
