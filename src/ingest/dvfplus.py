"""DVF+ open-data (Cerema / DGALN, Licence Ouverte 2.0): French property sales since 2014,
one line per sale. The April 2026 release (2026.1) covers January 2014 to December 2025.
The October 2026 release had no csv files in its folder when this was written (a correction
note was posted there), so the April release is used.

Only the Paris file is extracted. It holds individual sales and stays in data/raw."""
from __future__ import annotations

import io
import zipfile

from src.config import RAW
from src.ingest.http import fetch_bytes, record

FOLDER = "https://cerema.app.box.com/v/dvfplus-opendata"
FILE_ID = "2192472020739"  # versions_anterieures/avril_2026/csv/R11_Ile_de_France/DVF_PLUS_2026_1_CSV_R011_ED251.zip
URL = f"https://cerema.app.box.com/index.php?rm=box_download_shared_file&vanity_name=dvfplus-opendata&file_id=f_{FILE_ID}"
MEMBER = "1_DONNEES_LIVRAISON/dvf_plus_d75.csv"
DEST = RAW / "dvfplus" / "dvf_plus_d75.csv"


def main(force: bool = False) -> None:
    if DEST.exists() and not force:
        print(DEST.name, "already there")
        return
    DEST.parent.mkdir(parents=True, exist_ok=True)
    blob = fetch_bytes(URL, retries=5, timeout=900)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        DEST.write_bytes(z.read(MEMBER))
    record(DEST, URL, "DVF+ open-data 2026.1 (Cerema), Île-de-France csv, Paris member; Licence Ouverte 2.0")
    print(DEST.name, DEST.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
