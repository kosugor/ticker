const elements = {
  status: document.querySelector("#connection-status"),
  latestRate: document.querySelector("#latest-rate"),
  latestRateDate: document.querySelector("#latest-rate-date"),
  latestFundsBody: document.querySelector("#latest-funds-body"),
  latestFundCount: document.querySelector("#latest-fund-count"),
  ratesBody: document.querySelector("#rates-body"),
  ratesCount: document.querySelector("#rates-count"),
  fundsBody: document.querySelector("#funds-body"),
  fundsCount: document.querySelector("#funds-count"),
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric", month: "short", day: "numeric",
});
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
});

function formatDate(value) {
  if (!value) return "—";
  return dateFormatter.format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value) {
  if (!value) return "—";
  return dateTimeFormatter.format(new Date(value));
}

function formatNumber(value, maximumFractionDigits = 6) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(Number(value));
}

function cell(row, value, className = "") {
  const td = row.insertCell();
  td.textContent = value;
  if (className) td.className = className;
  return td;
}

function showEmpty(body, columnCount, message) {
  body.replaceChildren();
  const row = body.insertRow();
  const td = cell(row, message, "empty");
  td.colSpan = columnCount;
}

function setStatus(state, message) {
  elements.status.className = `connection ${state}`;
  elements.status.lastElementChild.textContent = message;
}

async function getJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function renderLatest(data) {
  const rate = data.exchange_rate;
  elements.latestRate.textContent = rate ? formatNumber(rate.middle_rate, 4) : "—";
  elements.latestRateDate.textContent = rate
    ? `${rate.eur_unit} EUR · Effective ${formatDate(rate.effective_date)}`
    : "No exchange rate has been collected yet.";

  const funds = data.fund_values;
  elements.latestFundCount.textContent = funds.length;
  elements.latestFundsBody.replaceChildren();
  if (!funds.length) {
    showEmpty(elements.latestFundsBody, 3, "No fund values have been collected yet.");
    return;
  }
  funds.forEach((fund) => {
    const row = elements.latestFundsBody.insertRow();
    cell(row, fund.fund_id);
    cell(row, formatDate(fund.value_date));
    cell(row, `${formatNumber(fund.investment_unit_value)} ${fund.investment_unit_currency}`, "numeric");
  });
}

function renderRates(rates) {
  elements.ratesCount.textContent = `${rates.length} ${rates.length === 1 ? "record" : "records"}`;
  elements.ratesBody.replaceChildren();
  if (!rates.length) {
    showEmpty(elements.ratesBody, 4, "No exchange rates match these filters.");
    return;
  }
  rates.forEach((rate) => {
    const row = elements.ratesBody.insertRow();
    cell(row, formatDate(rate.effective_date));
    cell(row, formatNumber(rate.eur_unit), "numeric");
    cell(row, formatNumber(rate.middle_rate, 4), "numeric");
    cell(row, formatDateTime(rate.fetched_at_utc));
  });
}

function renderFunds(funds) {
  elements.fundsCount.textContent = `${funds.length} ${funds.length === 1 ? "record" : "records"}`;
  elements.fundsBody.replaceChildren();
  if (!funds.length) {
    showEmpty(elements.fundsBody, 5, "No fund values match these filters.");
    return;
  }
  funds.forEach((fund) => {
    const row = elements.fundsBody.insertRow();
    cell(row, fund.fund_id);
    cell(row, formatDate(fund.value_date));
    cell(row, `${formatNumber(fund.investment_unit_value)} ${fund.investment_unit_currency}`, "numeric");
    cell(row, `${formatNumber(fund.fund_assets_value, 2)} ${fund.fund_assets_currency}`, "numeric");
    const sourceCell = row.insertCell();
    const link = document.createElement("a");
    link.className = "source-link";
    link.href = fund.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View source";
    sourceCell.append(link);
  });
}

function queryFromForm(form) {
  const query = new URLSearchParams();
  new FormData(form).forEach((value, key) => {
    const trimmed = value.trim();
    if (trimmed) query.set(key, trimmed);
  });
  return query.toString();
}

async function loadLatest() {
  try {
    renderLatest(await getJson("/latest-values"));
    setStatus("online", "API connected");
  } catch (error) {
    elements.latestRate.textContent = "—";
    elements.latestRateDate.textContent = error.message;
    showEmpty(elements.latestFundsBody, 3, "Latest fund values could not be loaded.");
    setStatus("error", "API unavailable");
  }
}

async function loadRates(form = document.querySelector("#rates-filter")) {
  showEmpty(elements.ratesBody, 4, "Loading exchange rates…");
  try {
    renderRates(await getJson(`/exchange-rates?${queryFromForm(form)}`));
  } catch (error) {
    elements.ratesCount.textContent = "";
    showEmpty(elements.ratesBody, 4, `Could not load exchange rates: ${error.message}`);
  }
}

async function loadFunds(form = document.querySelector("#funds-filter")) {
  showEmpty(elements.fundsBody, 5, "Loading fund values…");
  try {
    renderFunds(await getJson(`/fund-values?${queryFromForm(form)}`));
  } catch (error) {
    elements.fundsCount.textContent = "";
    showEmpty(elements.fundsBody, 5, `Could not load fund values: ${error.message}`);
  }
}

function connectFilter(form, loader) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loader(form);
  });
  form.addEventListener("reset", () => requestAnimationFrame(() => loader(form)));
}

document.querySelector("#refresh-latest").addEventListener("click", loadLatest);
connectFilter(document.querySelector("#rates-filter"), loadRates);
connectFilter(document.querySelector("#funds-filter"), loadFunds);
loadLatest();
loadRates();
loadFunds();
