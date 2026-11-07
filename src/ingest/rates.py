"""Risk-free rates for the user cost of housing.

- France: 10-year government bond yield, ECB long-term interest rate statistics
  (series IRS.M.FR.L.L40.CI.0000.EUR.N.Z, monthly, % p.a.).
- Singapore: 10-year Singapore Government Securities yield, SingStat Table Builder
  M700071 ("Current Banks Interest Rates (End Of Period), Monthly"), series 15.
Both are saved as tidy CSVs: month, rate_pct.
"""
import json

import pandas as pd

from src.config import INTERIM, RAW
from src.ingest.http import download

ECB = ("https://data-api.ecb.europa.eu/service/data/IRS/M.FR.L.L40.CI.0000.EUR.N.Z"
       "?startPeriod=2015-01&format=csvdata")
SINGSTAT = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M700071?limit=3000"


def main(force: bool = False) -> None:
    out = RAW / "rates"
    f = download(ECB, out / "ecb_irs_fr_10y.csv", note="ECB long-term interest rate, France 10y", force=force)
    fr = pd.read_csv(f, usecols=["TIME_PERIOD", "OBS_VALUE"]).rename(columns={"TIME_PERIOD": "month", "OBS_VALUE": "rate_pct"})
    fr.to_csv(INTERIM / "rf_paris.csv", index=False)

    j = download(SINGSTAT, out / "singstat_M700071.json", note="SingStat M700071", force=force)
    rows = json.loads(j.read_text())["Data"]["row"]
    s = next(r for r in rows if r["rowText"] == "Government Securities - 10-Year Bond Yield")
    sg = pd.DataFrame(s["columns"]).rename(columns={"key": "month", "value": "rate_pct"})
    sg["month"] = pd.to_datetime(sg["month"], format="%Y %b").dt.strftime("%Y-%m")
    sg["rate_pct"] = sg["rate_pct"].astype(float)
    sg.to_csv(INTERIM / "rf_singapore.csv", index=False)


if __name__ == "__main__":
    main()
