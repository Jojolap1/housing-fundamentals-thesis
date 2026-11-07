"""ECB euro foreign exchange reference rates (daily), SGD and USD per EUR."""
from src.config import RAW
from src.ingest.http import download

URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.SGD+USD.EUR.SP00.A"
       "?startPeriod=2017-01-01&format=csvdata")


def main(force: bool = False) -> None:
    download(URL, RAW / "fx" / "ecb_eurofxref_sgd_usd.csv", note="ECB reference rates", force=force)


if __name__ == "__main__":
    main()
