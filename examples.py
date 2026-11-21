"""Example datasets shipped with the app. Synthetic examples are labelled as such."""
import copy

# Synthetic datasets used as built-in examples and as parity-test fixtures.
# They are invented, not real companies.
SAMPLE = {
 "meta": {"name":"Sample Co (synthetic)","ticker":"SMPL","sector":"Consumer staples","is_financial":False,
          "currency":"IDR","unit":1e9,"shares":10000,"share_unit":1e6,"price":1500,"valuation_date":"2026-11-10"},
 "periods":["2021","2022","2023","2024","2025"],
 "fin":{
  "revenue":[8000,8800,9500,10100,10800],"ebit":[1200,1300,1450,1500,1620],"d_and_a":[300,320,340,360,380],
  "interest_expense":[100,110,105,100,95],"pretax_income":[1150,1240,1390,1450,1570],"income_tax":[260,280,310,320,345],
  "net_income":[890,960,1080,1130,1225],"dividends_paid":[-400,-450,-500,-550,-600],
  "cash":[1500,1600,1800,1900,2100],"total_debt":[2000,2100,2000,1900,1800],"lease_liabilities":[100,110,120,130,140],
  "minority_interest":[50,55,60,65,70],"equity_parent":[6000,6500,7100,7700,8300],"non_operating_assets":[200,200,250,250,300],
  "total_assets":[10000,10800,11500,12200,13000],"cfo":[1300,1350,1500,1550,1700],"capex":[-600,-650,-700,-700,-750]},
 "market":{"rf":0.065,"erp":0.0433,"crp":0.0207,"beta":0.9,"beta_method":"user","credit_spread":0.015,"marginal_tax":0.22},
 "peers":[
  {"name":"P1","market_cap":20000,"total_debt":3000,"cash":1000,"revenue":15000,"ebitda":2800,"ebit":2300,"net_income":1500,"equity_book":9000,"beta":0.8},
  {"name":"P2","market_cap":12000,"total_debt":1000,"cash":500,"revenue":9000,"ebitda":1700,"ebit":1400,"net_income":950,"equity_book":6000,"beta":0.95},
  {"name":"P3","market_cap":30000,"total_debt":5000,"cash":2500,"revenue":22000,"ebitda":4200,"ebit":3500,"net_income":2300,"equity_book":14000,"beta":0.85},
  {"name":"P4","market_cap":8000,"total_debt":2000,"cash":300,"revenue":7000,"ebitda":900,"ebit":600,"net_income":-50,"equity_book":4000,"beta":1.1},
  {"name":"P5","market_cap":15000,"total_debt":1500,"cash":800,"revenue":10000,"ebitda":1900,"ebit":1550,"net_income":1100,"equity_book":7000,"beta":0.9},
  {"name":"P6","market_cap":90000,"total_debt":1000,"cash":800,"revenue":9000,"ebitda":1500,"ebit":1200,"net_income":800,"equity_book":5000,"beta":1.2}],
}


_stable = copy.deepcopy(SAMPLE)
_loss = copy.deepcopy(SAMPLE)
_loss["meta"].update(name="Synthetic growth platform", ticker="SYN-G", sector="Technology & internet", price=400)
_loss["fin"].update(revenue=[2000, 3500, 6000, 9000, 12000], ebit=[-1500, -1800, -1200, -600, -150],
                    net_income=[-1600, -2000, -1400, -700, -200], pretax_income=[-1550, -1900, -1300, -650, -180],
                    income_tax=[0, 0, 0, 0, 0])
_bank = copy.deepcopy(SAMPLE)
_bank["meta"].update(name="Synthetic bank", ticker="SYN-B", sector="Financials", is_financial=True)

for _x in (_stable, _loss, _bank):
    _x["last_updated"] = "2026-11-11"

EXAMPLES = {
    "Synthetic consumer staples (stable)": _stable,
    "Synthetic growth platform (loss-making)": _loss,
    "Synthetic bank (financial firm)": _bank,
}

# The reported company. Kept last so the synthetic cases stay first in the picker, and loaded
# defensively so the calculator still opens if the data file is removed.
try:
    from data.icbp import ICBP as _icbp
    EXAMPLES["ICBP - PT Indofood CBP Sukses Makmur (30 Sep 2026)"] = _icbp
except Exception:
    pass

# Second real company, kept to show the method selection switching on a financial firm.
try:
    from data.bbca import BBCA as _bbca
    EXAMPLES["BBCA - PT Bank Central Asia (30 Sep 2026)"] = _bbca
except Exception:
    pass
