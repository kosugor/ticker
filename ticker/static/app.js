const elements = {
  status: document.querySelector("#connection-status"),
  latestFunds: document.querySelector("#latest-funds"),
  latestFundCount: document.querySelector("#latest-fund-count"),
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric", month: "short", day: "numeric",
});

function formatDate(value) {
  if (!value) return "—";
  return dateFormatter.format(new Date(`${value}T00:00:00`));
}

function formatNumber(value, maximumFractionDigits = 6) {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(Number(value));
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

function groupedBySociety(funds) {
  return funds.reduce((groups, fund) => {
    const society = groups.get(fund.society_id) || [];
    society.push(fund);
    groups.set(fund.society_id, society);
    return groups;
  }, new Map());
}

function renderLatest(data) {
  const funds = data.fund_values || [];
  elements.latestFundCount.textContent = `${funds.length} ${funds.length === 1 ? "fund" : "funds"}`;
  elements.latestFunds.replaceChildren();

  if (!funds.length) {
    const empty = document.createElement("p");
    empty.className = "empty panel-empty";
    empty.textContent = "No fund values have been collected yet.";
    elements.latestFunds.append(empty);
    return;
  }

  for (const [society, societyFunds] of groupedBySociety(funds)) {
    const article = document.createElement("article");
    article.className = "panel society-card";
    const heading = document.createElement("div");
    heading.className = "society-heading";
    const latestDate = societyFunds[0].value_date;
    heading.innerHTML = `<div><p class="card-label">Society · Latest complete date</p><h3></h3><p class="society-date"></p></div><span class="count-badge">${societyFunds.length}</span>`;
    heading.querySelector(".society-date").textContent = formatDate(latestDate);
    heading.querySelector("h3").textContent = society;
    article.append(heading);

    const table = document.createElement("table");
    table.innerHTML = "<thead><tr><th>Fund</th><th class=\"numeric\">Unit value</th></tr></thead>";
    const body = document.createElement("tbody");
    societyFunds.forEach((fund) => {
      const row = body.insertRow();
      row.insertCell().textContent = fund.fund_id;
      const valueCell = row.insertCell();
      valueCell.className = "numeric";
      valueCell.textContent = `${formatNumber(fund.investment_unit_value)} ${fund.investment_unit_currency}`;
    });
    table.append(body);
    const wrapper = document.createElement("div");
    wrapper.className = "table-wrap";
    wrapper.append(table);
    article.append(wrapper);
    elements.latestFunds.append(article);
  }
}

async function loadLatest() {
  try {
    renderLatest(await getJson("/latest-values"));
    setStatus("online", "API connected");
  } catch (error) {
    elements.latestFundCount.textContent = "";
    elements.latestFunds.innerHTML = `<p class="empty panel-empty">Latest fund values could not be loaded.</p>`;
    setStatus("error", "API unavailable");
  }
}

document.querySelector("#refresh-latest").addEventListener("click", loadLatest);
loadLatest();
