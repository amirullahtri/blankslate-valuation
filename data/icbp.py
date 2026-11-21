"""ICBP dataset, valuation date 30 September 2026.

SOURCE: stockanalysis.com (IDX:ICBP), data sourced from S&P Global Market Intelligence,
pages last updated 2026-10-30 (statements) and 2026-11-20 (price/statistics), retrieved 2026-11-21.
The TTM column ends 30 September 2026, so the income statement, the balance sheet and the share
price all sit on the valuation date. Still to be reconciled line by line against the audited
filings from IDX (FY2021-FY2025 and the TW III 2026 interim report).

Units: millions IDR. Debt is split into borrowings and leases because the source's "Total Debt"
row includes leases; the split reconciles exactly against its components in all six columns.
"""
ICBP = {
 "meta": {"name":"PT Indofood CBP Sukses Makmur Tbk","ticker":"ICBP","sector":"Consumer staples",
          "is_financial":False,"currency":"IDR","unit":1e6,"shares":11662,"share_unit":1e6,
          "price":6675,"valuation_date":"2026-09-30","peers_as_of":"2026-09-30"},
 "last_updated":"2026-11-21 (balance sheet and net sales reconciled to the 30 Sep 2026 interim filing; see sources[RECONCILIATION])",
 "periods":["2021","2022","2023","2024","2025","2026 TTM"],
 "fin":{
  # --- income statement -------------------------------------------------------------------
  "revenue":        [56803733, 64797516, 67909901, 72597188, 74850923, 83029836],
  "ebit":           [11753721, 12634959, 14797733, 16318844, 15873652, 16503535],
  "d_and_a":        [ 1632353,  1703375,  1694290,  1786206,  1859436,  1975922],
  "interest_expense":[1837077,  2148657,  2024713,  2142348,  2153025,  2247201],
  "pretax_income":  [ 9986133,  7561193, 11540647, 11638497, 13836214, 12936669],
  "income_tax":     [ 2074190,  1838999,  3075524,  2825120,  3080105,  2864368],
  "net_income":     [ 6399431,  4587367,  6990572,  7079369,  9224927,  8282536],
  "dividends_paid": [-2507310, -2507310, -2192439, -2332382, -2915477, -3090406],
  # --- balance sheet ----------------------------------------------------------------------
  "cash":           [20662197, 15897488, 21687436, 27709890, 31622827, 33549611],
  "total_debt":     [41576001, 45837391, 43761637, 45420213, 47186416, 50300305],
  "lease_liabilities":[ 176459,   168660,   228695,   204439,   245111,   245748],
  "minority_interest":[20850607,20954496, 21353864, 21826509, 22163261, 22470724],
  "equity_parent":  [34090000, 36518511, 40750169, 45217376, 51519743, 55330715],
  "non_operating_assets":[11068718,11169243, 8368853, 6418825, 7430623, 8003152],
  "goodwill_intangibles":[55731915,55598677,55452233,55318995,55185757,55085828],
  "total_assets":   [118015311,115305536,119267076,126040905,135544351,143525285],
  # --- cash flow --------------------------------------------------------------------------
  "cfo":            [ 7989039,  8804494, 12415005, 12454982, 12104427, 12343256],
  "capex":          [-2249751, -1788876, -1823830, -2162129, -3634570, -2198980]},
 "market":{"rf":0.0711,           # SBN 10y at 30 Sep 2026; local-currency, so no default-spread deduction
           "erp":0.0423,          # Damodaran mature-market ERP, table updated 5 Jan 2026
           "crp":0.0246,          # Damodaran country risk premium, Indonesia (Baa2)
           "beta":0.9164,         # emerging-market industry unlevered beta relevered at ICBP's D/E
           "beta_method":"industry-relevered",
           "credit_spread":0.0055,# synthetic company spread only; sovereign risk sits in the SBN yield
           "marginal_tax":0.22,   # Indonesian statutory rate
           "target_dv":None},     # current market D/V carried forward
 # Peer fields follow PEER_FIELDS. total_debt holds the source's "Total Debt", which already
 # includes leases, so lease_liabilities is 0 for every peer to avoid double counting.
 # minority_interest is derived as EV - market cap - total debt + cash; the identity was verified
 # on ICBP itself, where it returns 22,470,724 against a reported 22,470,724.
 # The reported betas are 5-year local regressions and are recorded as published, not as usable
 # risk measures: see sources["market.beta"] and the BETA_IMPLAUSIBLE check.
 "peers":[
  {"name":"MYOR Mayora Indah","market_cap":30616700,"total_debt":4750000,"lease_liabilities":0,
   "minority_interest":290000,"cash":4260000,"revenue":39660000,"ebitda":6020000,"ebit":4210000,
   "net_income":3440000,"equity_book":19170000,"beta":-0.12,"source":"stockanalysis.com IDX:MYOR statistics, 2026-11-21"},
  {"name":"UNVR Unilever Indonesia","market_cap":61528026,"total_debt":561510,"lease_liabilities":0,
   "minority_interest":8490,"cash":2030000,"revenue":33660000,"ebitda":5160000,"ebit":4680000,
   "net_income":8510000,"equity_book":4210000,"beta":0.27,"source":"stockanalysis.com IDX:UNVR statistics, 2026-11-21"},
  {"name":"CMRY Cisarua Mountain Dairy","market_cap":34516988,"total_debt":459,"lease_liabilities":0,
   "minority_interest":0,"cash":3000000,"revenue":12780000,"ebitda":2560000,"ebit":2330000,
   "net_income":2150000,"equity_book":6920000,"beta":0.20,"source":"stockanalysis.com IDX:CMRY statistics, 2026-11-21"},
  {"name":"GOOD Garudafood","market_cap":11215758,"total_debt":2250000,"lease_liabilities":0,
   "minority_interest":417680,"cash":777680,"revenue":15120000,"ebitda":1430000,"ebit":1020000,
   "net_income":655480,"equity_book":4500000,"beta":0.13,"source":"stockanalysis.com IDX:GOOD statistics, 2026-11-21"},
  {"name":"STTP Siantar Top","market_cap":11826626,"total_debt":0,"lease_liabilities":0,
   "minority_interest":30000,"cash":5760000,"revenue":5670000,"ebitda":1190000,"ebit":1070000,
   "net_income":1180000,"equity_book":8210000,"beta":0.49,"source":"stockanalysis.com IDX:STTP statistics, 2026-11-21"},
  {"name":"ROTI Nippon Indosari","market_cap":3145205,"total_debt":883540,"lease_liabilities":0,
   "minority_interest":0,"cash":182490,"revenue":3750000,"ebitda":477110,"ebit":290880,
   "net_income":177090,"equity_book":1650000,"beta":-0.20,"source":"stockanalysis.com IDX:ROTI statistics, 2026-11-21"},
  {"name":"ULTJ Ultrajaya Milk","market_cap":21315920,"total_debt":37460,"lease_liabilities":0,
   "minority_interest":92540,"cash":2570000,"revenue":10710000,"ebitda":2490000,"ebit":2250000,
   "net_income":1820000,"equity_book":8410000,"beta":0.14,"source":"stockanalysis.com IDX:ULTJ statistics, 2026-11-21"},
  {"name":"SIDO Sido Muncul","market_cap":10245529,"total_debt":6670,"lease_liabilities":0,
   "minority_interest":0,"cash":883250,"revenue":3850000,"ebitda":1430000,"ebit":1310000,
   "net_income":1030000,"equity_book":3270000,"beta":0.06,"source":"stockanalysis.com IDX:SIDO statistics, 2026-11-21"}],
 "sources":{
   "RECONCILIATION":"Checked against the company's own interim report, PT Indofood CBP Sukses Makmur Tbk "
                    "and its subsidiaries, interim consolidated financial statements as of 30 September 2026 and "
                    "for the nine-month period then ended (unaudited), 100 pages, bilingual, downloaded from "
                    "indofoodcbp.com/menu/financial-statements. Three results. (1) Net sales reconcile exactly: "
                    "the filing reports 64,445,695 for 9M2026 and 56,266,782 for 9M2025, equal to the sum of the "
                    "three quarterly figures used here. (2) The balance sheet at the valuation date reconciles "
                    "line by line: cash and equivalents 30,942,061 plus short-term investments 2,607,550 = the "
                    "33,549,611 used here; long-term investments 8,003,152; goodwill 54,006,155; lease "
                    "liabilities 97,643 current and 148,105 long-term = 245,748; non-controlling interests "
                    "22,470,724. The December 2025 comparative column matches as well. So the "
                    "enterprise-to-equity bridge rests on figures taken from the filing. (3) One definitional "
                    "differences remain, both of them definitional rather than errors, and both accounted for "
                    "exactly: operating profit (see fin.ebit) and the placement of the final tax on interest "
                    "income (see fin.pretax_income). The FY2025 audited filing was checked the same way: net "
                    "sales 74,850,923 and the FY2024 comparative 72,597,188 both match exactly, as does gross "
                    "profit, and income for the year agrees at 10,756,109.",
   "fin.ebit":"Operating profit excluding operating foreign-exchange gains and dividend income, which is the "
              "aggregator's 'Operating Income' line and not the filing's 'LABA USAHA / INCOME FROM OPERATIONS'. "
              "The gap is accounted for exactly, to the last rupiah, by those two items and nothing else: "
              "FY2025 filing 16,655,530 against 15,873,652 here, a gap of 781,878, equal to note 27's operating "
              "FX gain of 745,859 plus dividend income of 36,019. 9M2026 filing 13,666,573 against 12,643,435, a "
              "gap of 1,023,138, equal to an operating FX gain of 952,647 plus dividend income of 70,491. FY2024 "
              "carried no operating FX gain at all (note 27 shows a dash), and there the two bases agree to "
              "within 2,346. Both exclusions are deliberate. This model carries the target EBIT margin forward "
              "for ten years, and neither a currency movement on operating balances nor dividends received from "
              "other companies is a margin a forecast can extend; including them would project a currency gain "
              "as if it were trading performance. Measured: on the filing's basis the target margin rises from "
              "21.19% to 22.78% and the fair value from 11,210 to 12,028 per share, +818 or +7.3%, with the call "
              "unchanged at BUY. The lower basis is the headline; the higher one is disclosed, not hidden.",
   "fin.pretax_income":"Profit before tax PLUS the final tax on interest income, which the filing presents as a "
                       "separate line above profit before tax and the aggregator folds into income tax. The "
                       "offset is exact: for FY2025 the filing reports 13,721,309 before tax and 2,965,200 of "
                       "tax, against 13,836,214 and 3,080,105 here, both higher by the 114,905 of final tax on "
                       "interest income disclosed in the filing. Income for the year is identical in both at "
                       "10,756,109, so nothing is double counted and the effective rate moves by less than "
                       "0.2 pp. The same line runs at 89,392 for 9M2026 and 139,160 for FY2024.",
   "fin.interest_expense":"Interest expense only. The filing's 'Beban keuangan / Finance expenses' is a wider "
                          "line (5,017,575 for 9M2026) that bundles interest with foreign-exchange losses on the "
                          "USD borrowings; the aggregator separates the two, reporting interest expense and "
                          "currency exchange loss on their own lines. The separated figure is the one a cost of "
                          "debt can be built from, so it is used here, and the currency effect is handled "
                          "explicitly in market.credit_spread instead.",
   "fin.*":"stockanalysis.com IDX:ICBP income statement, balance sheet and cash flow statement "
           "(source: S&P Global Market Intelligence, page last updated 2026-10-30), retrieved 2026-11-21. "
           "TTM column ends 30 Sep 2026.",
   "fin.total_debt":"Borrowings only: short-term debt + current portion of long-term debt + long-term debt. "
                    "Checked against the source's Total Debt row in all six columns: borrowings + leases equals "
                    "41,752,460 / 46,006,051 / 43,990,332 / 45,624,652 / 47,431,527 / 50,546,053 with no residual.",
   "fin.goodwill_intangibles":"Goodwill 54,006,155 (unchanged in all six periods, from the 2020 Pinehill "
                              "acquisition) plus other intangible assets of 1,725,760 / 1,592,522 / 1,446,078 / "
                              "1,312,840 / 1,179,602 / 1,079,673. Checked against the source's Tangible Book Value "
                              "row: 55,330,715 - 55,085,828 = 244,887 on the TTM, equal to the reported figure.",
   "fin.non_operating_assets":"Long-term investments; ICBP reports equity-method earnings separately "
                              "(324,191 TTM), so these are treated as non-operating and added in the bridge.",
   "meta.price":"IDX:ICBP close on 30 Sep 2026 = 6,675 (stockanalysis.com price history). Cross-checked two ways: "
                "6,675 / 710.22 TTM EPS = 9.40, equal to the reported Q3 2026 PE of 9.40; and "
                "6,675 x 11,662m / 83,029,836 revenue = 0.938, equal to the reported PS of 0.94.",
   "market.rf":"SBN 10y 7.707% on 2 Nov 2026, which Investing.com data puts 0.60 pp above its 30 Sep 2026 level, "
               "giving 7.11% at the valuation date (cross-checked against a 2 Oct 2026 Indo-GB 10y range of "
               "7.10-7.25% and 7.14% at end-Q2 2026). Taken as the rupiah risk-free rate without deduction. "
               "Damodaran's rule subtracts the sovereign default spread from a government bond yield, which would "
               "give 7.11% - 1.62% = 5.49%, but that 1.62% is derived from Indonesia's foreign-currency rating "
               "(Baa2). A government's default risk on its own currency is far smaller, so subtracting the "
               "foreign-currency spread from a rupiah bond over-deducts. The 5.49% variant is carried as a "
               "sensitivity and cuts the WACC by roughly 1.0 pp. Note the two routes give the same cost of debt: "
               "5.49% + 0.55% + 1.62% = 7.11% + 0.55% = 7.66%.",
   "market.erp":"Damodaran, Country Default Spreads and Risk Premiums, table last updated 5 Jan 2026: Aaa countries "
                "carry a 0.00% country premium on a 4.23% ERP, so the mature-market premium is 4.23%.",
   "market.crp":"Damodaran, same table: Indonesia (Moody's Baa2), adjusted default spread 1.62%, country risk "
                "premium 2.46%, total ERP 6.69%.",
   "market.beta":"Bottom-up, from an industry sample rather than local regressions. Damodaran, Betas by Sector "
                 "(Emerging Markets), betaemerg.xls, analysis as of January 2026 (file last saved 7 Jan 2026): "
                 "Food Processing, 1,030 firms, average levered beta 0.7204 at a 38.00% D/E, unlevered beta 0.5602, "
                 "unlevered beta corrected for cash 0.6083. Relevered at ICBP's market D/E of "
                 "50,546,053 / 77,843,850 = 64.93% and a 22% marginal rate: 0.6083 x [1 + 0.78 x 0.6493] = 0.9164. "
                 "The emerging-market sample is used in preference to the US one, which carries only 78 firms and a "
                 "0.47 cash-corrected unlevered beta; on the US sample the relevered figure would be 0.708 and the "
                 "WACC about 0.85 pp lower. The local 5-year regressions are not usable at all: ICBP's own is 0.07 "
                 "and the eight peers run -0.20 to 0.49 with a median of 0.135, which would imply a cost of equity "
                 "below the cost of debt. Thin free float is the likely cause - ICBP floats 2.27bn of 11.66bn "
                 "shares, 19.5%.",
   "market.credit_spread":"Synthetic rating. EBIT 16,503,535 / interest expense 2,247,201 = 7.34x interest coverage, "
                          "equal to the reported figure. Damodaran's ratings and coverage table (January 2026) maps "
                          "6.50-8.50x for large non-financial firms to Aa2/AA and a 0.55% spread. No sovereign "
                          "component is added because the 7.11% SBN yield already carries it, giving a 7.66% pre-tax "
                          "cost of debt. ICBP's own cash interest cost is lower, 2,247,201 / 50,546,053 = 4.45%, "
                          "because the borrowings are USD senior notes; that rate is not usable in a rupiah "
                          "valuation, and the same currency mismatch drives the recurring FX losses in pretax income "
                          "(-2,618,210 TTM, -3,381,100 in FY2022).",
   "market.marginal_tax":"Indonesian statutory corporate rate 22%, consistent with Damodaran's table. The effective "
                         "rate has run 20.8-26.7% over the six periods and 22.14% on the TTM.",
   "peers.*":"stockanalysis.com statistics pages for each ticker (source: S&P Global Market Intelligence), "
             "retrieved 2026-11-21. Figures carry 3-4 significant digits as displayed, which is adequate for "
             "multiples but not for a bridge; peers are used for multiples only.",
   "peers.market_cap":"Repriced to the valuation date. The statistics pages quote market value at the 20 Nov 2026 "
                      "close, so each peer's market cap is scaled by its 30 Sep 2026 close over its 20 Nov 2026 "
                      "close, taken from that peer's own price history: MYOR 1,390/1,515; UNVR 1,620/1,520; "
                      "CMRY 4,350/4,150; GOOD 304/264; STTP 9,025/8,150; ROTI 560/438; ULTJ 2,050/2,010; "
                      "SIDO 348/340. Share counts are unchanged over the period. Seven of the eight traded higher "
                      "on 30 Sep than on 20 Nov, so repricing raises the peer multiples rather than lowering them. "
                      "Balance-sheet and income items are not date-scaled.",
   "peers.selection":"Indonesian listed packaged food and beverage producers selling branded consumer staples "
                     "through general trade and modern trade. INDF is excluded because it consolidates ICBP, so its "
                     "multiples are not independent. UNVR is retained as a peer on public market data only."},
}
