"""KPIダッシュボード生成: state/kpi_history.json から自己完結型HTMLを出力。

- KPIタイル(売上・粗利・受注・出品数)
- 売上/粗利の日次推移ラインチャート(ホバーでクロスヘア+ツールチップ)
- テーブルビュー(アクセシビリティ用の代替表現)
- ライト/ダークモード対応
色は検証済みパレット(series1: 青, series2: 緑。CVD ΔE・コントラスト全チェックPASS)。
"""
from __future__ import annotations

import json
from pathlib import Path

from .storage import Store

_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>muzaiko ダッシュボード</title>
<style>
.viz-root {
  color-scheme: light;
  --surface-1: #fcfcfb; --surface-2: #f0efec;
  --text-primary: #0b0b0b; --text-secondary: #52514e;
  --grid: #e4e3df; --series-1: #2a78d6; --series-2: #008300;
  background: var(--surface-1); color: var(--text-primary);
  font-family: "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif;
  margin: 0; padding: 24px; min-height: 100vh;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19; --surface-2: #383835;
    --text-primary: #ffffff; --text-secondary: #c3c2b7;
    --grid: #33332f; --series-1: #3987e5; --series-2: #008300;
  }
}
:root[data-theme="dark"] .viz-root {
  color-scheme: dark;
  --surface-1: #1a1a19; --surface-2: #383835;
  --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --grid: #33332f; --series-1: #3987e5; --series-2: #008300;
}
h1 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.updated { color: var(--text-secondary); font-size: 12px; margin-bottom: 20px; }
.tiles { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }
.tile { background: var(--surface-2); border-radius: 8px; padding: 14px 18px; min-width: 130px; }
.tile .label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.tile .value { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tile .unit { font-size: 13px; font-weight: 400; color: var(--text-secondary); }
.chart-box { position: relative; max-width: 860px; }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); margin: 4px 0 8px; }
.legend .chip { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
svg { width: 100%; height: auto; display: block; }
.tooltip { position: absolute; pointer-events: none; background: var(--surface-2);
  color: var(--text-primary); border-radius: 6px; padding: 8px 10px; font-size: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.18); display: none; white-space: nowrap; z-index: 2; }
table { border-collapse: collapse; margin-top: 28px; font-size: 13px; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 14px; text-align: right; border-bottom: 1px solid var(--grid); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--text-secondary); font-weight: 500; }
.empty { color: var(--text-secondary); padding: 40px 0; }
</style>
</head>
<body class="viz-root" data-palette="#2a78d6,#008300">
<h1>muzaiko ダッシュボード</h1>
<div class="updated">最終更新: __UPDATED__</div>
<div class="tiles">__TILES__</div>
<h1>売上・粗利の推移</h1>
<div class="legend">
  <span><span class="chip" style="background:var(--series-1)"></span>売上高</span>
  <span><span class="chip" style="background:var(--series-2)"></span>粗利益</span>
</div>
<div class="chart-box" id="chart-box"><div class="tooltip" id="tooltip"></div></div>
__TABLE__
<script>
const DATA = __DATA__;
(function () {
  const box = document.getElementById("chart-box");
  if (DATA.length < 2) {
    box.insertAdjacentHTML("beforeend",
      '<div class="empty">データが2日分たまるとグラフが表示されます</div>');
    return;
  }
  const W = 860, H = 300, M = {t: 12, r: 70, b: 26, l: 56};
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const ymax = Math.max(1, ...DATA.map(d => Math.max(d.revenue, d.profit)));
  const ymin = Math.min(0, ...DATA.map(d => d.profit));
  const x = i => M.l + iw * i / (DATA.length - 1);
  const y = v => M.t + ih * (1 - (v - ymin) / (ymax - ymin));
  const css = v => getComputedStyle(document.body).getPropertyValue(v).trim();
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    (parent || svg).appendChild(e); return e;
  };
  // 目盛り(控えめなグリッド、1軸のみ)
  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const v = ymin + (ymax - ymin) * t / ticks;
    el("line", {x1: M.l, x2: W - M.r, y1: y(v), y2: y(v),
                stroke: css("--grid"), "stroke-width": 1});
    const label = el("text", {x: M.l - 8, y: y(v) + 4, "text-anchor": "end",
                              "font-size": 11, fill: css("--text-secondary")});
    label.textContent = Math.round(v).toLocaleString();
  }
  // X軸ラベル(最初・中間・最後)
  [0, Math.floor((DATA.length - 1) / 2), DATA.length - 1].forEach(i => {
    const label = el("text", {x: x(i), y: H - 6, "text-anchor": "middle",
                              "font-size": 11, fill: css("--text-secondary")});
    label.textContent = DATA[i].date.slice(5);
  });
  // 系列(2pxライン+終端に直接ラベル)
  const series = [["revenue", "--series-1", "売上高"], ["profit", "--series-2", "粗利益"]];
  for (const [key, colorVar, name] of series) {
    const pts = DATA.map((d, i) => `${x(i)},${y(d[key])}`).join(" ");
    el("polyline", {points: pts, fill: "none", stroke: css(colorVar), "stroke-width": 2,
                    "stroke-linejoin": "round", "stroke-linecap": "round"});
    const last = DATA[DATA.length - 1];
    const label = el("text", {x: W - M.r + 6, y: y(last[key]) + 4,
                              "font-size": 11, fill: css("--text-secondary")});
    label.textContent = name;
  }
  // ホバー: クロスヘア+マーカー+ツールチップ
  const crosshair = el("line", {y1: M.t, y2: H - M.b, stroke: css("--text-secondary"),
                                "stroke-width": 1, "stroke-dasharray": "3,3", opacity: 0});
  const markers = series.map(([, colorVar]) =>
    el("circle", {r: 4.5, fill: css(colorVar), stroke: css("--surface-1"),
                  "stroke-width": 2, opacity: 0}));
  const tooltip = document.getElementById("tooltip");
  svg.addEventListener("mousemove", ev => {
    const rect = svg.getBoundingClientRect();
    const mx = (ev.clientX - rect.left) * W / rect.width;
    const i = Math.max(0, Math.min(DATA.length - 1,
      Math.round((mx - M.l) / iw * (DATA.length - 1))));
    const d = DATA[i];
    crosshair.setAttribute("x1", x(i)); crosshair.setAttribute("x2", x(i));
    crosshair.setAttribute("opacity", 1);
    series.forEach(([key], s) => {
      markers[s].setAttribute("cx", x(i)); markers[s].setAttribute("cy", y(d[key]));
      markers[s].setAttribute("opacity", 1);
    });
    tooltip.style.display = "block";
    tooltip.style.left = Math.min(x(i) / W * rect.width + 12, rect.width - 170) + "px";
    tooltip.style.top = "14px";
    tooltip.innerHTML = `<strong>${d.date}</strong><br>` +
      `売上高: ${d.revenue.toLocaleString()}円<br>` +
      `粗利益: ${d.profit.toLocaleString()}円<br>` +
      `受注: ${d.orders}件 / 出品: ${d.active_listings}件`;
  });
  svg.addEventListener("mouseleave", () => {
    crosshair.setAttribute("opacity", 0);
    markers.forEach(m => m.setAttribute("opacity", 0));
    tooltip.style.display = "none";
  });
  box.appendChild(svg);
})();
</script>
</body>
</html>
"""


def _tile(label: str, value: str, unit: str = "") -> str:
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""
    return (f'<div class="tile"><div class="label">{label}</div>'
            f'<div class="value">{value}{unit_html}</div></div>')


def render_dashboard(store: Store, path: Path) -> None:
    history: list[dict] = store.load_json("kpi_history.json", [])
    history.sort(key=lambda h: h.get("date", ""))
    latest = history[-1] if history else {
        "date": "-", "active_listings": 0, "orders": 0,
        "revenue": 0, "fees": 0, "cogs": 0, "profit": 0,
    }
    tiles = "".join([
        _tile("売上高(累計)", f"{latest['revenue']:,}", "円"),
        _tile("粗利益(累計)", f"{latest['profit']:,}", "円"),
        _tile("受注件数", f"{latest['orders']:,}", "件"),
        _tile("アクティブ出品", f"{latest['active_listings']:,}", "件"),
    ])
    table_rows = "".join(
        f"<tr><td>{h['date']}</td><td>{h['revenue']:,}</td><td>{h['fees']:,}</td>"
        f"<td>{h['cogs']:,}</td><td>{h['profit']:,}</td><td>{h['orders']}</td>"
        f"<td>{h['active_listings']}</td></tr>"
        for h in reversed(history[-30:])
    )
    table = (
        "<table><thead><tr><th>日付</th><th>売上高</th><th>手数料</th>"
        "<th>仕入原価</th><th>粗利益</th><th>受注</th><th>出品</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
    ) if history else ""
    html = (_TEMPLATE
            .replace("__UPDATED__", latest["date"])
            .replace("__TILES__", tiles)
            .replace("__TABLE__", table)
            .replace("__DATA__", json.dumps(history[-60:], ensure_ascii=False)))
    path.write_text(html, encoding="utf-8")
    print(f"  [出力] ダッシュボード → {path}")
