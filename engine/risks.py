"""Key-risk register (instruction: "Key risks, assumptions, and limitations").

Every risk is derived from the computed valuation, so it updates with the data. Where a driver
can move the recommendation, the register reports the break-even level of that driver: the value
at which the blended fair value equals the market price. Analyst-entered risks (Risks sheet of
the input template) are merged in and marked as such.
"""
from __future__ import annotations

from .core import _num, latest, scenario_central

SEV = {"High": 3, "Medium": 2, "Low": 1}


NO_BE = "no level in a plausible range reverses the call"


def _solve(fn, lo, hi, target, iters=60):
    """Bisection for fn(x) = target on [lo, hi].

    fn returns None where the model cannot be evaluated (for example a terminal rate at or below
    terminal growth). Such a point is a discontinuity, not a root, so the search is abandoned
    rather than allowed to converge onto it, and a solution that lands on either bound is
    rejected: it means the crossing is outside the plausible range.
    """
    span = hi - lo
    if span <= 0:
        return None
    a0, b0 = lo, hi
    flo, fhi = fn(lo), fn(hi)
    if flo is None or fhi is None:
        return None
    flo, fhi = flo - target, fhi - target
    if flo * fhi > 0:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        fm = fn(mid)
        if fm is None:
            return None
        fm -= target
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    x = (lo + hi) / 2
    if (x - a0) < 0.01 * span or (b0 - x) < 0.01 * span:
        return None
    return x


def build_risks(d, o):
    """Return a list of risk rows: category, risk, measure, break-even, severity, source."""
    R = []
    add = lambda cat, risk, measure, sev, be=None, src="model": R.append(
        {"category": cat, "risk": risk, "measure": measure, "break_even": be,
         "severity": sev, "source": src})

    h, a, r = o["history"], o["assumptions"], o["rates"]
    fin, S, price = o["financial"], o["settings"], o["price"]
    comp = o["relative"]["composite"]
    wi, wr = o["decision"]["w_intrinsic"], o["decision"]["w_relative"]

    def blended(intr):
        if intr is None:
            return None
        return wi * intr + wr * comp["value"] if comp else intr

    def fv_if(assump=None, rates=None):
        a2 = {**a, **(assump or {})}
        r2 = {**r, **(rates or {})}
        return blended(scenario_central(d, h, a2, r2, fin, S))

    # ---- 1. how much of the value sits beyond the forecast horizon
    ts = o["intrinsic"].get("tv_share")
    if ts is not None:
        sev = "High" if ts > 0.75 else "Medium" if ts > 0.6 else "Low"
        add("Forecast horizon",
            "Most of the intrinsic value lies beyond the 10-year forecast, so it rests on "
            "terminal assumptions rather than on projected cash flows.",
            f"Terminal value is {ts:.0%} of enterprise value", sev)

    # ---- 2. what the market price already assumes
    rev = o.get("reverse")
    if rev and price:
        if fin and rev.get("implied_roe_start") is not None:
            gap = rev["implied_roe_start"] - a["roe_start"]
            add("Market expectation",
                "The market price assumes a higher starting ROE than the model uses; the gap must "
                "be closed by performance or by a lower price.",
                f"Price implies ROE {rev['implied_roe_start']:.1%} vs model {a['roe_start']:.1%}",
                "High" if abs(gap) > 0.05 else "Medium" if abs(gap) > 0.02 else "Low")
        elif rev.get("implied_g1") is not None:
            gap = rev["implied_g1"] - a["g1"]
            add("Market expectation",
                "The market price embeds a different growth path from the model's; the valuation "
                "gap is an expectation gap, not only a cash-flow gap.",
                f"Price implies year-1 growth {rev['implied_g1']:.1%} vs model {a['g1']:.1%}"
                + (f"; implied 10-year CAGR {rev['implied_rev_cagr_10y']:.1%}"
                   if rev.get("implied_rev_cagr_10y") is not None else ""),
                "High" if abs(gap) > 0.08 else "Medium" if abs(gap) > 0.03 else "Low")

    # ---- 3-4. break-even on the two drivers that can flip the call
    if price:
        rd = S["scn_rate_delta"]
        if fin:
            be = _solve(lambda x: fv_if(assump={"roe_start": x}), -0.10, 0.60, price)
            add("Profitability",
                "The recommendation reverses if return on equity settles at the level shown.",
                f"Model uses starting ROE {a['roe_start']:.1%}", "High",
                f"ROE {be:.1%}" if be is not None else NO_BE)
            be = _solve(lambda x: fv_if(rates={"ke": x}),
                        a["g_terminal"] + rd + 0.01, 0.40, price)
            add("Discount rate",
                "The recommendation reverses at the cost of equity shown; it moves with the "
                "risk-free rate, the equity risk premium and the country risk premium.",
                f"Model uses ke {r['ke']:.2%}", "Medium",
                f"ke {be:.2%}" if be is not None else NO_BE)
        else:
            be = _solve(lambda x: fv_if(assump={"target_margin": x}), -0.20, 0.80, price)
            add("Operating margin",
                "The recommendation reverses if the target EBIT margin settles at the level shown.",
                f"Model uses target margin {a['target_margin']:.1%}"
                + (f"; 3-period history {h['margin_avg3']:.1%}" if h["margin_avg3"] is not None else ""),
                "High", f"EBIT margin {be:.1%}" if be is not None else NO_BE)

            spread = r["wacc"] - r["wacc_T"]
            be = _solve(lambda x: fv_if(rates={"wacc": x, "wacc_T": x - spread}),
                        a["g_terminal"] + spread + rd + 0.01, 0.40, price)
            add("Discount rate",
                "The recommendation reverses at the WACC shown; it moves with the risk-free rate, "
                "the equity risk premium and the country risk premium.",
                f"Model uses WACC {r['wacc']:.2%} (terminal {r['wacc_T']:.2%})", "Medium",
                f"WACC {be:.2%}" if be is not None else NO_BE)

            hi_g = r["wacc_T"] - rd - 0.01
            be = _solve(lambda x: fv_if(assump={"g_terminal": x}), -0.02, hi_g, price) if hi_g > -0.02 else None
            add("Terminal growth",
                "The recommendation reverses at the terminal growth rate shown. A rate close to the "
                "discount rate makes the terminal value unstable.",
                f"Model uses {a['g_terminal']:.2%}; spread to terminal WACC "
                f"{(r['wacc_T'] - a['g_terminal'])*100:.1f} pp", "Medium",
                f"g {be:.2%}" if be is not None else NO_BE)

    # ---- 5. peer comparability
    usable = [v for v in o["relative"]["multiples"].values() if v["usable"]]
    if usable:
        worst = max(usable, key=lambda v: v["cv"] or 0)
        cv = worst["cv"] or 0
        n = min(v["n"] for v in usable)
        sev = "High" if cv > 0.6 or n < 4 else "Medium" if cv > 0.35 else "Low"
        add("Peer comparability",
            "Relative value depends on how alike the peers really are; wide dispersion means the "
            "median carries little information.",
            f"{n} valid peers at the narrowest multiple; widest dispersion CV {cv:.2f}", sev)
    else:
        add("Peer comparability",
            "No usable multiple, so the valuation rests on the intrinsic model alone.",
            "Fewer than 3 valid peers on every multiple", "High")

    # ---- 6. methods disagree
    if comp and o["intrinsic_central"]:
        # same denominator as the confidence measure in core.recommend(), so both agree
        base = abs((o["fair_value"] or {}).get("central") or 0)
        gap = abs(o["intrinsic_central"] - comp["value"]) / base if base else 0
        if gap > 0.15:
            add("Method divergence",
                "The two methods point to different values; the blended figure hides that "
                "disagreement, so the weights matter as much as the inputs.",
                f"Intrinsic {o['intrinsic_central']:,.0f} vs relative {comp['value']:,.0f} "
                f"({gap:.0%} apart), weighted {wi:.0%}/{wr:.0%}",
                "High" if gap > 0.4 else "Medium")

    # ---- 7. earnings stability
    cv = h["margin_cv"]
    if cv is not None and not fin:
        sev = "High" if cv > 0.6 else "Medium" if cv > 0.35 else "Low"
        if sev != "Low":
            add("Earnings stability",
                "Margins have moved enough in the past that a single target margin may not hold.",
                f"EBIT-margin coefficient of variation {cv:.2f} over {h['n_periods']} periods", sev)
    if h["fcff_negative_share"] > 0.3 and not fin:
        add("Cash conversion",
            "Free cash flow was negative in part of the history, so reinvestment may exceed the "
            "model's sales-to-capital assumption.",
            f"FCFF negative in {h['fcff_negative_share']:.0%} of measured periods", "Medium")

    # ---- 8. leverage
    if not fin and r["de"] > 0.8:
        add("Capital structure",
            "Leverage raises the equity beta and makes the valuation more sensitive to rates.",
            f"Target D/E {r['de']:.2f}, D/V {r['dv']:.1%}",
            "High" if r["de"] > 1.5 else "Medium")

    # ---- 9. data depth
    if h["n_periods"] < 5:
        add("Information quality",
            "A short history gives the defaults a thin base, so overrides carry more weight.",
            f"{h['n_periods']} periods of financial history", "Medium" if h["n_periods"] >= 3 else "High")

    # ---- 10. analyst-entered risks
    for x in d.get("risks", []) or []:
        if not (x.get("risk") or "").strip():
            continue
        add(x.get("category") or "Analyst-identified", x["risk"], x.get("measure") or "",
            (x.get("severity") or "Medium").title(), x.get("break_even"), "analyst")

    R.sort(key=lambda z: (-SEV.get(z["severity"], 0), z["source"] != "model"))
    return R
