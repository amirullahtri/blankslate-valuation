"""BBCA dataset, valuation date 30 September 2026.

Second company, carried to show the calculator switching methods rather than to produce a
reported recommendation. Because meta.is_financial is True the engine turns FCFF/WACC off and
values equity with the excess-return model, and the relative layer drops the EV multiples and
keeps only P/E and P/B.

SOURCE: stockanalysis.com (IDX:BBCA), data sourced from S&P Global Market Intelligence,
retrieved 2026-11-21. The TTM column ends 30 September 2026, matching the valuation date.

Units: millions IDR.
"""
BBCA = {
 "meta": {"name":"PT Bank Central Asia Tbk","ticker":"BBCA","sector":"Financials",
          "is_financial":True,"currency":"IDR","unit":1e6,"shares":122947,"share_unit":1e6,
          "price":6075,"valuation_date":"2026-09-30","peers_as_of":"2026-09-30"},
 "last_updated":"2026-11-21 (aggregator; pending reconciliation to the IDX filings)",
 "periods":["2021","2022","2023","2024","2025","2026 TTM"],
 "fin":{
  # Revenue is the bank's revenue line after provisions for loan losses. EBIT is left out:
  # a bank has no operating-income line that FCFF could use, and the engine does not read it.
  "revenue":        [69144054, 82942762, 97444628, 104516601, 107985614, 111352059],
  "ebit":           [None]*6,
  "d_and_a":        [ 2138107,  2377420,  2935074,   2017454,   2411177,   2670405],
  "interest_expense":[9491401,  8251682, 12268952,  12532290,  13364495,  14388812],
  "pretax_income":  [38841174, 50467033, 60179757,  68217850,  71260876,  73270997],
  "income_tax":     [ 7401015,  9711461, 11521662,  13366576,  13697783,  13882655],
  "net_income":     [31422660, 40735722, 48639122,  54836305,  57537287,  59355699],
  "dividends_paid": [-13732840,-19107633,-26195948,-34208826,-37595047,-46832386],
  "cash":           [111482987,56311333, 31777383,  49073750,  39780282,  67299198],
  "total_debt":     [ 2421982,  2745355,  3544515,   4633595,   2493429,   2426983],
  "lease_liabilities":[0]*6,
  "minority_interest":[136172,   163049,   181337,    194466,    221077,    241697],
  "equity_parent":  [202712762,221018606,242356256,262640621,281466478,283419338],
  "non_operating_assets":[0]*6,
  "total_assets":   [1228344680,1314731674,1408107010,1449301328,1586828536,1641511008],
  "cfo":            [-7587786,-20533347, -5539861,  33300628, -34372101, -35777566],
  "capex":          [-3061820, -2631226, -4697731,  -3565731,  -1914929,  -2687379]},
 "market":{"rf":0.0711,
           "erp":0.0423,
           "crp":0.0246,
           "beta":0.5857,         # industry levered beta, used as published; banks are not unlevered
           "beta_method":"industry-levered",
           "credit_spread":None,  # not used: FCFF/WACC is off for a financial firm
           "marginal_tax":0.22,
           "target_dv":None},
 # P/E and P/B only. Book equity is the parent's share; market caps are as displayed on the
 # retrieval date, see sources["peers.timing"].
 "peers":[
  {"name":"BBRI Bank Rakyat Indonesia","market_cap":473120519,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":148630000,"ebitda":None,"ebit":None,
   "net_income":63560000,"equity_book":345680000,"beta":0.22,"source":"stockanalysis.com IDX:BBRI statistics, 2026-11-21"},
  {"name":"BMRI Bank Mandiri","market_cap":374270103,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":139840000,"ebitda":None,"ebit":None,
   "net_income":64100000,"equity_book":302800000,"beta":-0.03,"source":"stockanalysis.com IDX:BMRI statistics, 2026-11-21"},
  {"name":"BBNI Bank Negara Indonesia","market_cap":126344157,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":53500000,"ebitda":None,"ebit":None,
   "net_income":21040000,"equity_book":174260000,"beta":0.20,"source":"stockanalysis.com IDX:BBNI statistics, 2026-11-21"},
  {"name":"BRIS Bank Syariah Indonesia","market_cap":65503621,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":25320000,"ebitda":None,"ebit":None,
   "net_income":7980000,"equity_book":51040000,"beta":0.25,"source":"stockanalysis.com IDX:BRIS statistics, 2026-11-21"},
  {"name":"BBTN Bank Tabungan Negara","market_cap":15011940,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":17540000,"ebitda":None,"ebit":None,
   "net_income":4200000,"equity_book":37560000,"beta":0.43,"source":"stockanalysis.com IDX:BBTN statistics, 2026-11-21"},
  {"name":"BDMN Bank Danamon","market_cap":43493913,"total_debt":0,"lease_liabilities":0,
   "minority_interest":0,"cash":0,"revenue":20110000,"ebitda":None,"ebit":None,
   "net_income":4520000,"equity_book":62700000,"beta":0.63,"source":"stockanalysis.com IDX:BDMN statistics, 2026-11-21"}],
 "sources":{
   "fin.*":"stockanalysis.com IDX:BBCA income statement, balance sheet and cash flow statement "
           "(source: S&P Global Market Intelligence), retrieved 2026-11-21. TTM column ends 30 Sep 2026.",
   "fin.revenue":"The statement's Revenue line, which is revenues before loan losses less the provision for "
                 "loan losses. On the TTM that is 114,594,010 - 3,241,951 = 111,352,059.",
   "fin.interest_expense":"Interest paid on deposits. For a bank this is a cost of raw material, not a "
                          "financing cost, so it is not added back anywhere in the equity valuation.",
   "fin.cfo":"Reported operating cash flow is negative in five of six periods because deposit and loan "
             "movements run through operating activities for a bank. It is recorded as published and is not "
             "used in the excess-return model.",
   "meta.shares":"122,947m basic shares on the TTM, down from 123,275m in FY2021-FY2024, so a small buyback "
                 "has run. Book value per share 2,307.19.",
   "meta.price":"IDX:BBCA close on 30 Sep 2026 = 6,075 (stockanalysis.com price history). At 482.77 TTM EPS "
                "that is a PE of 12.58 and a P/B of 2.63.",
   "market.beta":"Damodaran, Betas by Sector (Emerging Markets), betaemerg.xls, analysis as of January 2026: "
                 "Bank (Money Center), 455 firms, average levered beta 0.5857. Used as published, without "
                 "unlevering and relevering: for a financial firm debt is raw material rather than financing, "
                 "so a debt-to-equity adjustment has no meaning. Cost of equity "
                 "7.11% + 0.5857 x 6.69% = 11.03%. The local regressions are unusable here for the same reason "
                 "as at ICBP: the six peers run -0.03 to 0.63 with a median of 0.235.",
   "market.rf":"As ICBP: SBN 10y 7.11% at 30 Sep 2026.",
   "peers.selection":"Indonesian listed commercial banks. BBRI, BMRI and BBNI are the state-owned majors, BRIS "
                     "the sharia bank, BBTN the mortgage lender and BDMN a mid-size private bank, so the set "
                     "spans the range of returns on equity from 8.6% to 21.8% rather than only BBCA's close "
                     "comparators.",
   "peers.market_cap":"Repriced to the valuation date. The statistics pages quote market value at the 20 Nov 2026 "
                      "close, so each peer's market cap is scaled by its 30 Sep 2026 close over its 20 Nov 2026 "
                      "close, taken from that peer's own price history: BBRI 3,140/3,080; BMRI 4,010/3,890; "
                      "BBNI 3,390/3,560; BRIS 1,420/1,160; BBTN 1,070/1,005; BDMN 4,450/4,600. Share counts are "
                      "unchanged over the period. Book equity and net income are not date-scaled.",
   "limitations":"Carried as a demonstration case. Deposits, loan book quality, capital adequacy and the "
                 "regulatory minimum are not modelled, and none of them can be ignored in a real bank "
                 "valuation.",
   "peers.*":"stockanalysis.com statistics pages for each ticker (source: S&P Global Market Intelligence), "
             "retrieved 2026-11-21. EV fields are left at zero because the engine uses only P/E and P/B for a "
             "financial firm."},
}
