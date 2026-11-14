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


out.append("=== Cerema Box: Ile-de-France folders")
for label, fid in (("csv/R11", "427362608619"), ("parquet", "427708571715")):
    html = get(f"{BOX}/folder/{fid}")
    m = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    data = json.loads(m.group(1)) if m else {}
    out.append(f"{label}: top keys {list(data)[:12]}")
    for k, v in data.items():
        txt = json.dumps(v)
        out.append(f"  {k}: {len(txt)} chars; keys {list(v)[:15] if isinstance(v, dict) else type(v).__name__}")
        for n, t, sz in re.findall(r'"name":\s*"([^"]+)".{0,400}?"typedID":\s*"([df]_\d+)".{0,300}?"(?:itemSize|size)":\s*(\d+|null)', txt)[:60]:
            out.append(f"    {n} | {t} | {sz}")
        for t, n in re.findall(r'"typedID":\s*"([df]_\d+)".{0,400}?"name":\s*"([^"]+)"', txt)[:60]:
            out.append(f"    {n} | {t}")
        if "typedID" in txt and "items" in txt:
            j = txt.find('"items"')
            out.append("    snippet: " + txt[j:j + 600])
open(sys.argv[1], "w").write("\n".join(out) + "\n")
print("\n".join(out)[:3000])
