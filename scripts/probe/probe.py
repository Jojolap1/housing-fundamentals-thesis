"""Lists what a few public download locations expose (no data kept): used to decide how a
source can be fetched automatically. Output: data/processed/probe_report.txt."""
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) research-reproducibility-check"}
BOX = "https://cerema.app.box.com/v/dvfplus-opendata"
out = []


def get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def items(html: str) -> list[dict]:
    m = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        return []
    found = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("items"), list):
                found.extend(i for i in o["items"] if isinstance(i, dict) and "typedID" in i)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json.loads(m.group(1)))
    return found


def box(url: str, depth: int, budget: list[int], path: str = "") -> None:
    for page in range(1, 6):
        try:
            html = get(url + (f"?page={page}" if page > 1 else ""))
        except Exception as e:
            out.append(f"{path} ERROR {e!r}")
            return
        its = items(html)
        if not its:
            if page == 1:
                out.append(f"{path} no items parsed; html {len(html)} chars; markers: "
                           + str([k for k in ("postStreamData", "shared-folder", "typedID") if k in html]))
            return
        for i in its:
            name, tid = i.get("name"), i.get("typedID")
            out.append(f"{path}/{name} | {tid} | {i.get('itemSize') or i.get('size')}")
            keep = depth < 1 or re.search(r"csv|75|ile|r11|idf|france|d\d\d|lisez|readme", str(name), re.I)
            if tid.startswith("d_") and depth < 3 and budget[0] > 0 and keep:
                budget[0] -= 1
                box(f"{BOX}/folder/{tid[2:]}", depth + 1, budget, f"{path}/{name}")
        if len(its) < 20:
            return


def listing(fid: str) -> list[tuple[str, str, object]]:
    res = []
    for page in range(1, 8):
        html = get(f"{BOX}/folder/{fid}" + (f"?page={page}" if page > 1 else ""))
        m = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
        sf = json.loads(m.group(1)).get("/app-api/enduserapp/shared-folder", {}) if m else {}
        res += [(i.get("name"), i.get("typedID"), i.get("itemSize")) for i in sf.get("items", [])]
        if page >= sf.get("pageCount", 1):
            break
    return res


import csv
import io
import zipfile

url = "https://cerema.app.box.com/index.php?rm=box_download_shared_file&vanity_name=dvfplus-opendata&file_id=f_2192472020739"
with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
    blob = r.read()
out.append(f"=== zip {len(blob)} bytes")
z = zipfile.ZipFile(io.BytesIO(blob))
for info in z.infolist():
    out.append(f"{info.filename} | {info.file_size}")
for info in z.infolist():
    if not info.filename.lower().endswith(".csv") or not re.search(r"75|mutation", info.filename, re.I):
        continue
    with z.open(info) as f:
        head = f.readline().decode("utf-8", "ignore").strip()
        sep = max(";|,\t", key=head.count)
        cols = head.split(sep)
        out.append(f"--- {info.filename}: sep {sep!r}, {len(cols)} columns: {cols}")
        rd = csv.reader(io.TextIOWrapper(f, "utf-8", errors="ignore"), delimiter=sep)
        want = [c for c in cols if c in ("datemut", "anneemut", "coddep", "libnatmut", "vefa", "valeurfonc", "nblocmut", "nblocapt", "nblocdep",
                                         "nbapt1pp", "nbapt2pp", "nbapt3pp", "nbapt4pp", "nbapt5pp", "sbati", "sbatapt", "codtypbien", "libtypbien", "l_codinsee", "l_section")]
        idx = [cols.index(c) for c in want]
        n, years, types, shown = 0, {}, {}, 0
        for row in rd:
            if len(row) != len(cols):
                continue
            rec = dict(zip(want, (row[i] for i in idx)))
            if rec.get("coddep") != "75":
                continue
            n += 1
            years[rec.get("anneemut")] = years.get(rec.get("anneemut"), 0) + 1
            types[rec.get("libtypbien")] = types.get(rec.get("libtypbien"), 0) + 1
            if shown < 3 and rec.get("libtypbien", "").upper().startswith("UN APPARTEMENT"):
                out.append("  sample: " + json.dumps(rec, ensure_ascii=False))
                shown += 1
        out.append(f"  Paris rows {n}; by year {dict(sorted(years.items()))}")
        out.append("  types: " + json.dumps(dict(sorted(types.items(), key=lambda kv: -kv[1])[:12]), ensure_ascii=False))
open(sys.argv[1], "w").write("\n".join(out) + "\n")
print("\n".join(out)[:4000])
