const currency = location.pathname.split("/").filter(Boolean).pop().toLowerCase();
const labels = { eur: "EUR", usd: "USD" };
const color = currency === "usd" ? "#b46a2b" : "#176b4d";
const formatNumber = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });
const formatDate = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });
const $ = (selector) => document.querySelector(selector);
let allRows = [];

function setStatus(state, message) {
  const status = $("#connection-status");
  status.className = `connection ${state}`;
  status.lastElementChild.textContent = message;
}

function drawChart(rows) {
  const svg = $("#rate-chart");
  if (!rows.length) { $("#chart-empty").hidden = false; return; }
  $("#chart-empty").hidden = true;
  const width = 1000, height = 420, pad = { top: 28, right: 24, bottom: 48, left: 70 };
  const values = rows.map((row) => Number(row.middle_rate));
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const x = (index) => pad.left + index * (width - pad.left - pad.right) / Math.max(rows.length - 1, 1);
  const y = (value) => pad.top + (max - value) * (height - pad.top - pad.bottom) / range;
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  const grid = [0, .5, 1].map((fraction) => {
    const value = max - range * fraction, lineY = y(value);
    return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${lineY}" y2="${lineY}" class="chart-grid"/><text x="${pad.left - 12}" y="${lineY + 4}" text-anchor="end" class="chart-axis">${formatNumber.format(value)}</text>`;
  }).join("");
  const first = formatDate.format(new Date(`${rows[0].effective_date}T00:00:00`));
  const last = formatDate.format(new Date(`${rows.at(-1).effective_date}T00:00:00`));
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `${grid}<polyline points="${points}" class="chart-line" style="stroke:${color}"/><text x="${pad.left}" y="${height - 14}" class="chart-axis">${first}</text><text x="${width - pad.right}" y="${height - 14}" text-anchor="end" class="chart-axis">${last}</text>`;
  $("#latest-rate").textContent = `${formatNumber.format(values.at(-1))} RSD`;
  $("#chart-meta").textContent = `${rows.length.toLocaleString()} daily observations · 1 ${labels[currency]} = RSD`;
}

function updateRange() {
  if (!allRows.length) return;
  let start = Number($("#start-slider").value);
  let end = Number($("#end-slider").value);
  if (start > end) {
    if (document.activeElement === $("#start-slider")) end = start;
    else start = end;
    $("#start-slider").value = start;
    $("#end-slider").value = end;
  }
  const selected = allRows.slice(start, end + 1);
  const lastIndex = allRows.length - 1;
  const startPercent = lastIndex ? (start / lastIndex) * 100 : 0;
  const endPercent = lastIndex ? (end / lastIndex) * 100 : 100;
  $(".range-track").style.background = `linear-gradient(to right, var(--line) ${startPercent}%, var(--green) ${startPercent}%, var(--green) ${endPercent}%, var(--line) ${endPercent}%)`;
  $("#start-date").textContent = formatDate.format(new Date(`${allRows[start].effective_date}T00:00:00`));
  $("#end-date").textContent = formatDate.format(new Date(`${allRows[end].effective_date}T00:00:00`));
  drawChart(selected);
}

function configureRange(rows) {
  allRows = rows;
  for (const selector of ["#start-slider", "#end-slider"]) {
    const slider = $(selector);
    slider.max = rows.length - 1;
    slider.value = selector === "#start-slider" ? 0 : rows.length - 1;
    slider.addEventListener("input", updateRange);
  }
  updateRange();
}

async function loadChart() {
  try {
    const response = await fetch(`/exchange-rates/${currency}`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error();
    const rows = (await response.json()).reverse();
    $("#page-title").textContent = `${labels[currency]} exchange rate`;
    $("#chart-title").textContent = `1 ${labels[currency]} in Serbian dinars`;
    $("#chart-description").textContent = `Track the daily NBS middle rate for the ${labels[currency]} against the Serbian dinar.`;
    configureRange(rows); setStatus("online", "API connected");
  } catch { setStatus("error", "API unavailable"); $("#chart-empty").hidden = false; }
}
loadChart();
