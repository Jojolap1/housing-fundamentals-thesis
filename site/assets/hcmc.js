/* Ho Chi Minh City: administrative land values (Resolution 87/2025), tables only. */
(function () {
  const $ = (s) => document.querySelector(s);
  const fmt = (v) => (v == null ? "–" : v.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
  Promise.all(["meta", "wards", "streets"].map((k) => fetch(`data/hcmc_${k}.json`).then((r) => r.json())))
    .then(([meta, wards, streets]) => {
      $("#n-seg").textContent = meta.segments.toLocaleString("en-GB");
      $("#n-units").textContent = meta.units;
      table(wards, "#w", ["ward", "type", "segments", "median", "q25", "q75", "max", "median_commercial"],
        (r) => `<td>${r.ward}</td><td>${r.type}</td><td class="num">${r.segments}</td><td class="num">${fmt(r.median)}</td>
          <td class="num">${fmt(r.q25)} – ${fmt(r.q75)}</td><td class="num">${fmt(r.max)}</td><td class="num">${fmt(r.median_commercial)}</td>`,
        "median", (r, q) => r.ward.toUpperCase().includes(q), 200);
      table(streets, "#s", ["street", "ward", "segments", "min", "max"],
        (r) => `<td>${r.street}</td><td>${r.ward}</td><td class="num">${r.segments}</td><td class="num">${fmt(r.min)}</td><td class="num">${fmt(r.max)}</td>`,
        "max", (r, q) => r.street.toUpperCase().includes(q) || r.ward.toUpperCase().includes(q), 300);
    });

  function table(rows, id, cols, render, sortK, match, limit) {
    let key = sortK, dir = -1;
    const draw = () => {
      const q = $(`${id}-search`).value.trim().toUpperCase();
      const r = rows.filter((x) => !q || match(x, q)).sort((a, b) => {
        const va = a[key], vb = b[key];
        return typeof va === "string" ? dir * va.localeCompare(vb) : dir * ((va ?? -1) - (vb ?? -1));
      });
      $(`${id}-count`).textContent = `${r.length.toLocaleString("en-GB")} rows${r.length > limit ? `, first ${limit} shown` : ""}`;
      $(`${id}-body`).innerHTML = r.slice(0, limit).map((x) => `<tr>${render(x)}</tr>`).join("");
    };
    document.querySelectorAll(`${id}-head th[data-k]`).forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.k; dir = key === k ? -dir : (typeof rows[0][k] === "string" ? 1 : -1); key = k; draw();
    }));
    $(`${id}-search`).addEventListener("input", draw);
    draw();
  }
})();
