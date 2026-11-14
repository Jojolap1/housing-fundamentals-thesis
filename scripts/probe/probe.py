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


out.append("=== Cerema Box: April 2026 release")
todo = [("avril_2026", "375539396618", 0)]
while todo:
    path, fid, depth = todo.pop(0)
    try:
        its = listing(fid)
    except Exception as e:
        out.append(f"{path} ERROR {e!r}")
        continue
    if not its:
        out.append(f"{path} (empty)")
    for name, tid, size in its:
        show = depth < 2 or re.search(r"75|R11|national|lisez|readme|doc", str(name), re.I)
        if show:
            out.append(f"{path}/{name} | {tid} | {size}")
        if tid.startswith("d_") and depth < 3 and (depth < 1 or re.search(r"csv|parquet|R11", str(name), re.I)):
            todo.append((f"{path}/{name}", tid[2:], depth + 1))
out.append("=== correction note, October 2026")
try:
    out.append(get("https://cerema.app.box.com/index.php?rm=box_download_shared_file&shared_name=dvfplus-opendata&file_id=f_2572450285271")[:600])
except Exception as e:
    out.append(f"ERROR {e!r}")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
print("\n".join(out)[:3000])
