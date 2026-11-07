/* City page: maps (hexagons, districts), fundamental-vs-market chart, street table.
   All data are pre-aggregated by the pipeline (n >= 5 per cell-year). */
(function () {
  const CITY = document.body.dataset.city;
  const CFG = {
    paris: { cur: "€", center: [2.343, 48.857], zoom: 11.2, l1: "Arrondissement", l2: "Quartier",
             rentUnit: "€/m²/month (reference rent)", ptiNote: "years of IRIS median disposable income, couple = 1.5 UC" },
    singapore: { cur: "S$", center: [103.82, 1.355], zoom: 10.6, l1: "Planning area", l2: "Subzone",
                 rentUnit: "S$/month per flat (HDB approvals)", ptiNote: "4-room HDB price / planning-area median household income from work (2020)" },
  }[CITY];

  const SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
  const DIV = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f2b3ad", "#e34948", "#a32a29"];
  const DIV_DARK_MID = "#383835";

  const METRICS = {
    ppm2: { label: "Median price per m²", unit: () => CFG.cur + "/m²", fmt: (v) => fmtInt(v), seq: true },
    rent: { label: CITY === "paris" ? "Median reference rent per m²" : "Median monthly rent per flat",
            field: CITY === "paris" ? "rent_m2" : "rent_month", unit: () => CFG.rentUnit,
            fmt: (v) => (CITY === "paris" ? v.toFixed(1) : fmtInt(v)), seq: true },
    yield: { label: "Median gross rental yield", unit: () => "% per year", fmt: (v) => (100 * v).toFixed(2) + "%", seq: true },
    pti: { label: "Median price-to-income", unit: () => "years", fmt: (v) => v.toFixed(1), seq: true },
    gap: { label: "Median valuation gap (model)", unit: () => "predicted price / fundamental value − 1",
           fmt: (v) => (v >= 0 ? "+" : "") + (100 * v).toFixed(0) + "%", seq: false },
    mis: { label: "Relative mispricing (residual)", unit: () => "log price vs comparable dwellings",
           fmt: (v) => (v >= 0 ? "+" : "") + (100 * v).toFixed(1) + "%", seq: false },
  };

  function fmtInt(v) { return Math.round(v).toLocaleString("en-GB"); }
  const $ = (s) => document.querySelector(s);
  const isDark = () => matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light"
    || document.documentElement.dataset.theme === "dark";

  Promise.all(["meta", "hex", "l1", "l2", "fundamental", "streets"].map((k) =>
    fetch(`data/${CITY}_${k}.json`).then((r) => r.json()))).then(([meta, hex, l1, l2, fund, streets]) => {
    const DATA = { hex, l1, l2 };
    const years = meta.years;
    $("#period").textContent = `${meta.period[0]} → ${meta.period[1]}`;
    $("#ntotal").textContent = fmtInt(meta.n_total);
    const ySel = $("#year");
    years.forEach((y) => ySel.add(new Option(yearLabel(y), y)));
    ySel.value = years.includes(2025) ? 2025 : years[years.length - 1];
    buildMap(DATA);
    buildChart(fund);
    buildTable(streets, years);
  });

  function yearLabel(y) {
    if (CITY === "paris" && y === 2021) return "2021 (Jul–Dec)";
    if (CITY === "paris" && y === 2026) return "2026 (Jan–Jun)";
    if (CITY === "singapore" && y === 2026) return "2026 (to date)";
    return String(y);
  }

  /* ----------------------------------------------------------------- map */
  function buildMap(DATA) {
    const tiles = (dark) => [`https://basemaps.cartocdn.com/${dark ? "dark_all" : "light_all"}/{z}/{x}/{y}.png`];
    const map = new maplibregl.Map({
      container: "map", center: CFG.center, zoom: CFG.zoom, attributionControl: { compact: true },
      style: {
        version: 8,
        sources: { base: { type: "raster", tiles: tiles(isDark()), tileSize: 256,
          attribution: "© OpenStreetMap contributors © CARTO" } },
        layers: [{ id: "base", type: "raster", source: "base" }],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const tip = document.createElement("div");
    tip.className = "tip"; tip.hidden = true;
    $("#map").appendChild(tip);

    function key() { return { layer: $("#layer").value, metric: $("#metric").value, year: +$("#year").value }; }
    function field(m) { return (METRICS[m].field || m); }

    function breaks(values, seq) {
      const v = values.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
      if (!v.length) return null;
      if (seq) {
        const q = [1, 2, 3, 4, 5, 6].map((i) => v[Math.floor((i / 7) * (v.length - 1))]);
        return q;
      }
      const m = Math.max(Math.abs(v[Math.floor(0.05 * (v.length - 1))]), Math.abs(v[Math.floor(0.95 * (v.length - 1))])) || 1;
      return [-m, -m / 2, -m / 6, m / 6, m / 2, m].map((x) => x); // symmetric around 0
    }

    function render() {
      const { layer, metric, year } = key();
      const fc = DATA[layer];
      const f = `${field(metric)}_${year}`;
      const vals = fc.features.map((ft) => ft.properties[f]);
      const seq = METRICS[metric].seq;
      const br = breaks(vals, seq);
      const pal = seq ? SEQ : DIV.map((c, i) => (i === 3 && isDark() ? DIV_DARK_MID : c));
      const expr = br ? ["case", ["!", ["has", f]], "rgba(0,0,0,0)",
        ["step", ["get", f], pal[0], br[0], pal[1], br[1], pal[2], br[2], pal[3], br[3], pal[4], br[4], pal[5], br[5], pal[6]]]
        : "rgba(0,0,0,0)";
      if (map.getSource("d")) map.getSource("d").setData(fc);
      else {
        map.addSource("d", { type: "geojson", data: fc });
        map.addLayer({ id: "fill", type: "fill", source: "d", paint: { "fill-opacity": 0.78 } });
        map.addLayer({ id: "line", type: "line", source: "d", paint: { "line-color": isDark() ? "#1a1a19" : "#fcfcfb", "line-width": 0.6 } });
      }
      map.setPaintProperty("fill", "fill-color", expr);
      legend(metric, br, pal);
      $("#map-title").textContent = `${METRICS[metric].label}, ${yearLabel(year)} — ${layer === "hex" ? "H3 hexagons (res. 9)" : layer === "l1" ? CFG.l1 : CFG.l2}`;
      $("#gap-note").hidden = !(metric === "gap");
      $("#mis-note").hidden = !(metric === "mis");
    }

    function legend(metric, br, pal) {
      const L = $("#legend");
      if (!br) { L.innerHTML = "<span>No published cells for this selection (n ≥ 5 rule).</span>"; return; }
      const M = METRICS[metric];
      const lab = (x) => M.fmt(x);
      const txt = pal.map((_, i) => (i === 0 ? `< ${lab(br[0])}` : i === pal.length - 1 ? `≥ ${lab(br[br.length - 1])}`
        : `${lab(br[i - 1])} – ${lab(br[i])}`));
      L.innerHTML = `<span style="flex-basis:100%"><b>${M.label}</b> (${M.unit()})</span>
        ${pal.map((c, i) => `<span class="cls"><span class="sw" style="background:${c}"></span>${txt[i]}</span>`).join("")}
        <span class="cls"><span class="swatch-na"></span> not published (n &lt; 5) or no data</span>`;
    }

    map.on("load", () => {
      render();
      ["#layer", "#metric", "#year"].forEach((s) => $(s).addEventListener("change", render));
      map.on("mousemove", "fill", (e) => {
        const p = e.features[0].properties; const { metric, year } = key();
        const g = (m) => p[`${m}_${year}`];
        if (g("n") === undefined) { tip.hidden = true; return; }
        const M = METRICS[metric]; const v = g(field(metric));
        tip.innerHTML = `<b>${p.name || (key().layer === "hex" ? "Hexagon" : "")}</b>
          <div>${M.label}: <b style="display:inline">${v !== undefined ? M.fmt(v) : "–"}</b></div>
          <div class="k">Median price/m²: ${fmtInt(g("ppm2"))} ${CFG.cur}</div>
          <div class="k">IQR: ${fmtInt(g("ppm2_q25"))} – ${fmtInt(g("ppm2_q75"))}</div>
          <div class="k">Transactions: ${g("n")}</div>
          <div class="k">YoY: ${g("yoy") !== undefined ? (g("yoy") >= 0 ? "+" : "") + g("yoy").toFixed(1) + "%" : "–"}</div>`;
        tip.hidden = false;
        const r = $("#map").getBoundingClientRect();
        let x = e.point.x + 14, y = e.point.y + 14;
        if (x + 200 > r.width) x = e.point.x - 210;
        if (y + 140 > r.height) y = e.point.y - 150;
        tip.style.left = x + "px"; tip.style.top = y + "px";
        map.getCanvas().style.cursor = "crosshair";
      });
      map.on("mouseleave", "fill", () => { tip.hidden = true; map.getCanvas().style.cursor = ""; });
    });
  }

  /* --------------------------------------------- fundamental vs market chart */
  function buildChart(rows) {
    const W = 760, H = 320, m = { l: 64, r: 120, t: 16, b: 34 };
    const xs = rows.map((r) => r.year);
    const vals = rows.flatMap((r) => [r.price_m2_median, r.vstar_m2_base, r.vstar_m2_lo, r.vstar_m2_hi]).filter(Number.isFinite);
    const yMax = Math.max(...vals) * 1.08, yMin = 0;
    const X = (v) => m.l + ((v - xs[0]) / Math.max(1, xs[xs.length - 1] - xs[0])) * (W - m.l - m.r);
    const Y = (v) => H - m.b - ((v - yMin) / (yMax - yMin)) * (H - m.t - m.b);
    const ticks = niceTicks(yMin, yMax, 5);
    const line = (k) => rows.filter((r) => Number.isFinite(r[k])).map((r, i) => `${i ? "L" : "M"}${X(r.year)},${Y(r[k])}`).join("");
    const bandRows = rows.filter((r) => Number.isFinite(r.vstar_m2_lo) && Number.isFinite(r.vstar_m2_hi));
    const band = bandRows.map((r, i) => `${i ? "L" : "M"}${X(r.year)},${Y(r.vstar_m2_hi)}`).join("") +
      bandRows.slice().reverse().map((r) => `L${X(r.year)},${Y(r.vstar_m2_lo)}`).join("") + "Z";
    const last = rows[rows.length - 1];
    const svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Market price per m² versus fundamental value per m², by year">
      ${ticks.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--grid)" stroke-width="1"/>
        <text x="${m.l - 8}" y="${Y(t) + 4}" text-anchor="end">${fmtInt(t)}</text>`).join("")}
      <line x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--axis)"/>
      ${xs.map((x) => `<text x="${X(x)}" y="${H - 12}" text-anchor="middle">${x}</text>`).join("")}
      <path d="${band}" fill="var(--band-fund)" stroke="none"/>
      <path d="${line("vstar_m2_base")}" fill="none" stroke="var(--series-fund)" stroke-width="2"/>
      <path d="${line("price_m2_median")}" fill="none" stroke="var(--series-market)" stroke-width="2"/>
      ${rows.map((r) => `<circle cx="${X(r.year)}" cy="${Y(r.price_m2_median)}" r="4" fill="var(--series-market)" stroke="var(--surface-1)" stroke-width="2"/>`).join("")}
      ${rows.filter((r) => Number.isFinite(r.vstar_m2_base)).map((r) => `<circle cx="${X(r.year)}" cy="${Y(r.vstar_m2_base)}" r="4" fill="var(--series-fund)" stroke="var(--surface-1)" stroke-width="2"/>`).join("")}
      <text class="lbl" x="${X(last.year) + 10}" y="${Y(last.price_m2_median) + 4}">Market</text>
      ${Number.isFinite(last.vstar_m2_base) ? `<text class="lbl" x="${X(last.year) + 10}" y="${Y(last.vstar_m2_base) + 4}">Fundamental</text>` : ""}
      <line id="xh" y1="${m.t}" y2="${H - m.b}" stroke="var(--axis)" stroke-dasharray="3 3" visibility="hidden"/>
      <rect x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}" fill="transparent" id="hit"/>
    </svg>`;
    const wrap = $("#chart");
    wrap.innerHTML = svg;
    const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; wrap.appendChild(tip);
    const s = wrap.querySelector("svg"), xh = s.querySelector("#xh");
    s.querySelector("#hit").addEventListener("mousemove", (e) => {
      const pt = s.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      const p = pt.matrixTransform(s.getScreenCTM().inverse());
      const r = rows.reduce((a, b) => (Math.abs(X(b.year) - p.x) < Math.abs(X(a.year) - p.x) ? b : a));
      xh.setAttribute("x1", X(r.year)); xh.setAttribute("x2", X(r.year)); xh.setAttribute("visibility", "visible");
      const gap = Number.isFinite(r.gap_base) ? `${r.gap_base >= 0 ? "+" : ""}${(100 * r.gap_base).toFixed(0)}%` : "–";
      tip.innerHTML = `<b>${yearLabel(r.year)}</b>
        <div><span style="color:var(--series-market)">●</span> Market (median): ${fmtInt(r.price_m2_median)} ${CFG.cur}/m²</div>
        <div><span style="color:var(--series-fund)">●</span> Fundamental (baseline): ${Number.isFinite(r.vstar_m2_base) ? fmtInt(r.vstar_m2_base) : "–"}</div>
        <div class="k">Sensitivity range: ${Number.isFinite(r.vstar_m2_lo) ? fmtInt(r.vstar_m2_lo) + " – " + fmtInt(r.vstar_m2_hi) : "–"}</div>
        <div class="k">Valuation gap (baseline): ${gap}</div>
        <div class="k">Risk-free rate: ${(100 * r.rf).toFixed(2)}%</div>`;
      const b = wrap.getBoundingClientRect();
      tip.hidden = false;
      let x = e.clientX - b.left + 14; if (x + 220 > b.width) x -= 240;
      tip.style.left = x + "px"; tip.style.top = (e.clientY - b.top - 20) + "px";
    });
    s.querySelector("#hit").addEventListener("mouseleave", () => { tip.hidden = true; xh.setAttribute("visibility", "hidden"); });

    // Table view of the same numbers (accessibility).
    $("#chart-table").innerHTML = `<table><thead><tr><th>Year</th><th class="num">Market ${CFG.cur}/m²</th>
      <th class="num">Fundamental (base)</th><th class="num">Range low</th><th class="num">Range high</th><th class="num">Gap (base)</th><th class="num">n</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${yearLabel(r.year)}</td><td class="num">${fmtInt(r.price_m2_median)}</td>
      <td class="num">${Number.isFinite(r.vstar_m2_base) ? fmtInt(r.vstar_m2_base) : "–"}</td>
      <td class="num">${Number.isFinite(r.vstar_m2_lo) ? fmtInt(r.vstar_m2_lo) : "–"}</td>
      <td class="num">${Number.isFinite(r.vstar_m2_hi) ? fmtInt(r.vstar_m2_hi) : "–"}</td>
      <td class="num">${Number.isFinite(r.gap_base) ? (100 * r.gap_base).toFixed(0) + "%" : "–"}</td>
      <td class="num">${fmtInt(r.n)}</td></tr>`).join("")}</tbody></table>`;
  }

  function niceTicks(lo, hi, n) {
    const step0 = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= step0);
    const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
    return out;
  }

  /* ---------------------------------------------------------- street table */
  function buildTable(rows, years) {
    const yS = $("#t-year"); years.forEach((y) => yS.add(new Option(yearLabel(y), y)));
    yS.value = years.includes(2025) ? 2025 : years[years.length - 1];
    let sortK = "ppm2", dir = -1;
    function draw() {
      const y = +yS.value, q = $("#t-search").value.trim().toUpperCase();
      const r = rows.filter((x) => x.year === y && (!q || x.street.includes(q))).sort((a, b) => dir * ((a[sortK] ?? -1e9) - (b[sortK] ?? -1e9)));
      $("#t-count").textContent = `${r.length} streets with ≥ 5 sales in ${yearLabel(y)}`;
      $("#t-body").innerHTML = r.slice(0, 400).map((x) => `<tr><td>${x.street}</td><td>${x.district}</td>
        <td class="num">${x.n}</td><td class="num">${fmtInt(x.ppm2)}</td>
        <td class="num">${fmtInt(x.ppm2_q25)} – ${fmtInt(x.ppm2_q75)}</td>
        <td class="num">${x.yoy != null ? (x.yoy >= 0 ? "+" : "") + x.yoy.toFixed(1) + "%" : "–"}</td>
        <td class="num">${x.mis != null ? (x.mis >= 0 ? "+" : "") + (100 * x.mis).toFixed(1) + "%" : "–"}</td></tr>`).join("");
    }
    document.querySelectorAll("#t-head th[data-k]").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.k; dir = sortK === k ? -dir : -1; sortK = k; draw();
    }));
    yS.addEventListener("change", draw); $("#t-search").addEventListener("input", draw);
    draw();
  }
})();
