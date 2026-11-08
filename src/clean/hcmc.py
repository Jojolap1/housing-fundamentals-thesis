"""Extract the HCMC land price table (Resolution 87/2025/NQ-HĐND) from the gazette PDFs.

Each annex table has 7 columns: (1) No., (2) street, (3) segment from, (4) segment to,
(5) residential land, (6) commercial/service land, (7) non-agricultural production land
other than commercial; prices in thousand VND per m². Column positions are read from the
"(1) ... (7)" header row of each page. A record starts at a number in column (1) and
collects every following line until the next number. The ward or commune comes from the
table title "BẢNG GIÁ ĐẤT <PHƯỜNG|XÃ|ĐẶC KHU> <name>".

Prices are kept exactly as printed, including the few segments where the commercial price
exceeds the residential one (e.g. Đống Đa, ward Tân Sơn Hòa: 60,800 / 63,600 / 53,000).

These are ADMINISTRATIVE land values used for taxes and fees: they are neither transaction
prices nor asking prices, and they cover land only.

Quality checks (data/processed/hcmc_extraction_qc.csv): records without exactly three
prices, and gaps in the numbering within a ward.
"""
from __future__ import annotations

import glob
import re

import pandas as pd
import pdfplumber

from src.config import INTERIM, PROCESSED, RAW

PRICE = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
TITLE = re.compile(r"BẢNG GIÁ ĐẤT\s+(PHƯỜNG|XÃ|ĐẶC KHU)\s+(.+)$")
ANNEX = re.compile(r"Phụ lục\s+([IVX]+)")


def _lines(page) -> list[list[dict]]:
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines, cur, top = [], [], None
    for w in words:
        if top is None or abs(w["top"] - top) <= 3:
            cur.append(w)
            top = w["top"] if top is None else top
        else:
            lines.append(sorted(cur, key=lambda x: x["x0"]))
            cur, top = [w], w["top"]
    if cur:
        lines.append(sorted(cur, key=lambda x: x["x0"]))
    return lines


def _bounds(lines) -> tuple[list[float], float] | None:
    """Column boundaries and vertical position of the '(1) (2) ... (7)' header row."""
    for ln in lines:
        marks = [(w["x0"] + w["x1"]) / 2 for w in ln if re.fullmatch(r"\(\w\)", w["text"])]
        if len(marks) >= 6:
            xs = sorted(marks)
            return [(a + b) / 2 for a, b in zip(xs, xs[1:])], ln[0]["top"]
    return None


def _col(w: dict, bounds: list[float]) -> int:
    """Column of a word, from its horizontal centre (0..6)."""
    return sum((w["x0"] + w["x1"]) / 2 > b for b in bounds)


def parse_pdf(path: str) -> list[dict]:
    recs, cur = [], None
    annex, ward_type, ward, bounds = None, None, None, None
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            lines = _lines(page)
            found = _bounds(lines)
            header_top = -1.0
            if found:
                bounds, header_top = found
            for ln in lines:
                text = " ".join(w["text"] for w in ln)
                if m := ANNEX.search(text):
                    annex = m.group(1)
                if m := TITLE.search(text):
                    if cur:
                        recs.append(cur)
                        cur = None
                    ward_type, ward = m.group(1), m.group(2).strip()
                    continue
                # skip the page header block (column titles repeated on every page) and running heads
                if ln[0]["top"] <= header_top + 2 or bounds is None or ward is None or "CÔNG BÁO" in text:
                    continue
                first = ln[0]
                expected = 1 if cur is None or cur["ward"] != ward else cur["stt"] + 1
                if _col(first, bounds) == 0 and first["text"].isdigit() and int(first["text"]) == expected:
                    if cur:
                        recs.append(cur)
                    cur = {"annex": annex, "ward_type": ward_type, "ward": ward, "stt": int(first["text"]),
                           "street": [], "from": [], "to": [], "prices": [[], [], []],
                           "file": path.split("/")[-1], "page": pno}
                    ln = ln[1:]
                if cur is None:
                    continue
                for w in ln:
                    c = _col(w, bounds)
                    if c >= 4 and re.fullmatch(r"[\d.]+", w["text"]):
                        cur["prices"][min(c - 4, 2)].append(w["text"])
                    elif c <= 3:
                        cur[{0: "street", 1: "street", 2: "from", 3: "to"}[c]].append(w["text"])
    if cur:
        recs.append(cur)
    return recs


def _join_wrapped(tokens: list[str]) -> list[str]:
    """Rejoin prices wrapped over two lines by the PDF layout ("146.31" + "0" -> "146.310");
    keep only tokens that are then well-formed prices."""
    out: list[str] = []
    for t in tokens:
        if out and not PRICE.match(out[-1]) and re.fullmatch(r"\d{1,2}", t):
            out[-1] += t
        else:
            out.append(t)
    return [t for t in out if PRICE.match(t)]


def to_frame(recs: list[dict]) -> pd.DataFrame:
    """One row per priced segment. A numbered entry with k prices in each of the three
    columns is a street split into k sub-segments: it becomes k rows (multi_segment=True),
    whose from/to text cannot be split reliably and is kept whole. Entries whose price
    columns do not line up are kept with prices_ok=False and excluded from statistics."""
    rows = []
    for r in recs:
        r["prices"] = [_join_wrapped(x) for x in r["prices"]]
        n = [len(x) for x in r["prices"]]
        base = {"annex": r["annex"], "ward_type": r["ward_type"], "ward": r["ward"], "stt": r["stt"],
                "street": " ".join(r["street"]), "segment_from": " ".join(r["from"]),
                "segment_to": " ".join(r["to"]), "file": r["file"], "page": r["page"]}
        if n[0] >= 1 and n[0] == n[1] == n[2]:
            for k in range(n[0]):
                rows.append(base | {"sub": k + 1, "multi_segment": n[0] > 1, "prices_ok": True,
                                    "price_residential": r["prices"][0][k], "price_commercial": r["prices"][1][k],
                                    "price_nonagri": r["prices"][2][k]})
        else:
            rows.append(base | {"sub": 1, "multi_segment": False, "prices_ok": False,
                                "price_residential": None, "price_commercial": None, "price_nonagri": None})
    d = pd.DataFrame(rows)
    for c in ("price_residential", "price_commercial", "price_nonagri"):
        # printed in thousand VND/m² ("56.700" = 56,700 thousand = 56.7 million VND per m²)
        d[c] = pd.to_numeric(d[c].str.replace(".", "", regex=False), errors="coerce") * 1000
    return d


def qc(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (f, w), g in d.groupby(["file", "ward"], sort=False):
        s = sorted(g["stt"])
        gaps = sorted(set(range(1, s[-1] + 1)) - set(s))
        out.append({"file": f, "ward": w, "entries": g["stt"].nunique(), "priced_segments": int(g["prices_ok"].sum()),
                    "max_stt": s[-1], "missing_stt": len(gaps), "entries_unreadable": int((~g["prices_ok"]).sum())})
    return pd.DataFrame(out)


def aggregates(d: pd.DataFrame) -> None:
    """Published statistics (administrative land values, residential, VND/m²)."""
    ok = d[d["prices_ok"]]
    q = lambda p: (lambda s: s.quantile(p))  # noqa: E731
    w = ok.groupby(["annex", "ward_type", "ward"]).agg(
        segments=("price_residential", "size"), median=("price_residential", "median"),
        q25=("price_residential", q(0.25)), q75=("price_residential", q(0.75)),
        max=("price_residential", "max"), median_commercial=("price_commercial", "median")).reset_index()
    w.round(0).to_csv(PROCESSED / "hcmc_land_price_by_ward.csv", index=False)
    st = ok.groupby(["ward", "street"]).agg(segments=("price_residential", "size"),
                                            min=("price_residential", "min"), max=("price_residential", "max"),
                                            median=("price_residential", "median")).reset_index()
    st.round(0).to_csv(PROCESSED / "hcmc_land_price_by_street.csv", index=False)


def main() -> pd.DataFrame:
    recs = []
    for f in sorted(glob.glob(str(RAW / "hcmc" / "nq87_*.pdf"))):
        recs += parse_pdf(f)
    d = to_frame(recs)
    d.to_parquet(INTERIM / "hcmc_land_prices.parquet", index=False)
    q = qc(d)
    q.to_csv(PROCESSED / "hcmc_extraction_qc.csv", index=False)
    aggregates(d)
    print(int(d["prices_ok"].sum()), "priced segments from", d[["file", "ward", "stt"]].drop_duplicates().shape[0],
          "numbered entries in", d["ward"].nunique(), "wards/communes; unreadable entries:", int((~d["prices_ok"]).sum()),
          "; wards with numbering gaps:", int((q["missing_stt"] > 0).sum()))
    return d


if __name__ == "__main__":
    main()
