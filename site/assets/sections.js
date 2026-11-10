/* Hover read-out for the server-rendered index charts (price panel + volume panel share one crosshair). */
(function () {
  document.querySelectorAll(".schart").forEach((wrap) => {
    const D = JSON.parse(wrap.querySelector('script[type="application/json"]').textContent);
    const svgs = [...wrap.querySelectorAll("svg.chart")];
    const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; wrap.appendChild(tip);
    const N = D.periods.length, step = (D.W - D.l - D.r) / N;
    const hide = () => { tip.hidden = true; svgs.forEach((s) => s.querySelector(".xh").setAttribute("visibility", "hidden")); };
    svgs.forEach((svg) => {
      const hit = svg.querySelector(".hit");
      hit.addEventListener("mousemove", (e) => {
        const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
        const p = pt.matrixTransform(svg.getScreenCTM().inverse());
        const i = Math.max(0, Math.min(N - 1, Math.floor((p.x - D.l) / step)));
        const x = D.l + (i + 0.5) * step;
        svgs.forEach((s) => { const xh = s.querySelector(".xh"); xh.setAttribute("x1", x); xh.setAttribute("x2", x); xh.setAttribute("visibility", "visible"); });
        tip.innerHTML = `<b>${D.periods[i].replace("Q", " Q")}</b>` +
          D.series.map((s) => `<div><span style="color:${s.color}">●</span> ${s.label}: ${s.values[i] == null ? "–" : s.values[i].toFixed(1)}</div>`).join("") +
          `<div class="k">Retained sales: ${D.n[i].toLocaleString("en-GB")}</div>`;
        const b = wrap.getBoundingClientRect();
        tip.hidden = false;
        let left = e.clientX - b.left + 14; if (left + 300 > b.width) left = Math.max(0, left - 320);
        tip.style.left = left + "px"; tip.style.top = (e.clientY - b.top - 20) + "px";
      });
      hit.addEventListener("mouseleave", hide);
    });
  });
})();
