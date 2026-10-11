"use strict";
let mode = "replay";
let forecast = null;
let forecastVersion = 0;
let planVersion = 0;
const $ = (id) => document.getElementById(id);
const fmt = (x, d = 1) =>
  Number(x).toLocaleString("en-GB", {
    maximumFractionDigits: d,
    minimumFractionDigits: d,
  });
const time = (t) =>
  new Date(t).toLocaleTimeString("en-GB", {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
  });
const date = (t) =>
  new Date(t).toLocaleDateString("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
const ns = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs = {}, text = "") {
  const e = document.createElementNS(ns, tag);
  Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (text) e.textContent = text;
  return e;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  let r;
  try {
    r = await fetch(path, { ...options, signal: controller.signal });
  } catch (e) {
    if (e.name === "AbortError")
      throw new Error("Request timed out. Please retry.");
    throw e;
  } finally {
    clearTimeout(timeout);
  }
  if (!r.ok) {
    let detail = "Request failed. Please try again.";
    try {
      const j = await r.json();
      detail =
        typeof j.detail === "string"
          ? j.detail
          : (j.detail || []).map((x) => x.msg).join("; ");
    } catch {}
    throw new Error(detail);
  }
  return r.json();
}
function chart(slots) {
  const w = 700,
    h = 280,
    p = { l: 44, r: 8, t: 10, b: 28 };
  const max =
    Math.ceil(
      Math.max(
        ...slots.map((x) => x.upper),
        ...slots.map((x) => x.actual || 0),
      ) / 50,
    ) * 50 || 50;
  const x = (i) => p.l + (i * (w - p.l - p.r)) / (slots.length - 1),
    y = (v) => h - p.b - (v * (h - p.t - p.b)) / max;
  const s = svgEl("svg", { viewBox: `0 0 ${w} ${h}` });
  for (let i = 0; i < 5; i++) {
    const v = (max * i) / 4;
    s.append(
      svgEl("line", {
        x1: p.l,
        x2: w - p.r,
        y1: y(v),
        y2: y(v),
        stroke: "#263842",
        "stroke-dasharray": "3 5",
      }),
      svgEl(
        "text",
        {
          x: p.l - 8,
          y: y(v) + 4,
          fill: "#98aeb7",
          "font-size": 10,
          "text-anchor": "end",
        },
        String(Math.round(v)),
      ),
    );
  }
  const path = (key, reverse = false) =>
    slots
      .map((a, i) => [x(i), y(a[key])])
      .filter((a) => Number.isFinite(a[1]))
      [reverse ? "reverse" : "slice"]()
      .map((a) => a.join(","))
      .join(" ");
  s.append(
    svgEl("polygon", {
      points: path("upper") + " " + path("lower", true),
      fill: "#78ad8033",
    }),
    svgEl("polyline", {
      points: path("prediction"),
      fill: "none",
      stroke: "#aceda0",
      "stroke-width": 2.5,
    }),
  );
  if (slots.every((a) => a.actual != null))
    s.append(
      svgEl("polyline", {
        points: path("actual"),
        fill: "none",
        stroke: "#65cabe",
        "stroke-width": 1.8,
        "stroke-dasharray": "4 3",
      }),
    );
  for (const i of [0, 12, 24, 36, 47])
    s.append(
      svgEl(
        "text",
        {
          x: x(i),
          y: h - 5,
          fill: "#98aeb7",
          "font-size": 10,
          "text-anchor": i === 47 ? "end" : "middle",
        },
        time(slots[i].timestamp),
      ),
    );
  slots.forEach((a, i) => {
    const c = svgEl("circle", {
      cx: x(i),
      cy: y(a.prediction),
      r: 5,
      fill: "transparent",
    });
    c.append(
      svgEl(
        "title",
        {},
        `${time(a.timestamp)} · ${fmt(a.prediction)} gCO₂/kWh (${fmt(a.lower)}–${fmt(a.upper)})`,
      ),
    );
    s.append(c);
  });
  $("chart").replaceChildren(s);
}
function table(id, rows) {
  const body = $(id);
  body.replaceChildren();
  for (const values of rows) {
    const tr = document.createElement("tr");
    for (const value of values) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    body.append(tr);
  }
}
async function loadForecast() {
  const version = ++forecastVersion;
  const requestedMode = mode;
  invalidatePlan();
  error("");
  forecast = null;
  $("result-panel").hidden = true;
  $("schedule-button").disabled = true;
  $("refresh").disabled = true;
  $("mode-note").textContent = "Loading forecast…";
  $("chart").replaceChildren();
  $("forecast-table").replaceChildren();
  $("average").textContent = "—";
  $("lowest").textContent = "—";
  $("lowest-time").textContent = "Loading…";
  $("forecast-date").textContent = "";
  $("forecast-note").textContent = "";
  $("download").removeAttribute("href");
  $("download").setAttribute("aria-disabled", "true");
  try {
    const data = await api(`/api/v1/forecast?mode=${requestedMode}`);
    if (version !== forecastVersion) return;
    forecast = data;
    const slots = data.slots;
    const low = slots.reduce((a, b) => (a.prediction < b.prediction ? a : b));
    $("average").textContent = fmt(
      slots.reduce((a, b) => a + b.prediction, 0) / slots.length,
      0,
    );
    $("lowest").textContent = fmt(low.prediction, 0);
    $("lowest-time").textContent =
      `${time(low.timestamp)} · ${date(low.timestamp)}`;
    $("forecast-date").textContent =
      `${date(data.origin)} · horizon starts ${time(data.origin)} UK time`;
    $("mode-note").textContent = data.notice;
    $("forecast-note").textContent =
      requestedMode === "replay"
        ? "Historical simulation from a model fitted before this date; reconstructed later, not issued at that time. Actuals shown for comparison."
        : "Live data retrieved " +
          date(data.retrieved_at) +
          " " +
          time(data.retrieved_at) +
          " UK time" +
          ". Model trained through " +
          date(data.training_data_end) +
          ".";
    $("download").href =
      `/api/v1/forecast.csv?mode=${requestedMode}&expected_forecast_id=${data.forecast_id}`;
    $("download").removeAttribute("aria-disabled");
    chart(slots);
    table(
      "forecast-table",
      slots.map((x) => [
        `${date(x.timestamp)} ${time(x.timestamp)}`,
        fmt(x.prediction),
        fmt(x.lower),
        fmt(x.upper),
        x.actual == null ? "—" : fmt(x.actual),
      ]),
    );
    $("schedule-button").disabled = false;
  } catch (e) {
    if (version !== forecastVersion) return;
    error(e.message);
    $("mode-note").textContent =
      "Forecast could not be loaded. Select historical replay to explore the saved example.";
    $("average").textContent = "—";
    $("lowest").textContent = "—";
    $("lowest-time").textContent = "Unavailable";
    $("chart").replaceChildren();
    $("forecast-table").replaceChildren();
  } finally {
    if (version === forecastVersion) $("refresh").disabled = false;
  }
}
function invalidatePlan() {
  planVersion++;
  $("result-panel").hidden = true;
  $("schedule-button").disabled = !forecast;
}
async function setMode(value) {
  mode = value;
  for (const v of ["replay", "live"]) {
    $(`${v}-mode`).classList.toggle("active", mode === v);
    $(`${v}-mode`).setAttribute("aria-pressed", String(mode === v));
  }
  await loadForecast();
}
$("replay-mode").addEventListener("click", () => setMode("replay"));
$("live-mode").addEventListener("click", () => setMode("live"));
$("refresh").addEventListener("click", loadForecast);
$("objective").addEventListener("change", () => {
  $("prices-label").hidden = $("objective").value === "carbon";
});
$("charging-form").addEventListener("input", invalidatePlan);
$("charging-form").addEventListener("change", invalidatePlan);
$("charging-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!forecast) return;
  invalidatePlan();
  const version = planVersion;
  const shownForecast = forecast.forecast_id;
  error("");
  $("schedule-button").disabled = true;
  const f = new FormData(event.currentTarget);
  const objective = f.get("objective");
  const body = {
    mode,
    expected_forecast_id: shownForecast,
    capacity_kwh: Number(f.get("capacity")),
    max_charge_kw: Number(f.get("power")),
    initial_soc: Number(f.get("initial")) / 100,
    target_soc: Number(f.get("target")) / 100,
    available_slots: Number(f.get("hours")) * 2,
    efficiency: Number(f.get("efficiency")) / 100,
    objective,
  };
  if (objective !== "carbon")
    body.prices_p_per_kwh = String(f.get("prices"))
      .split(",")
      .map((x) => (x.trim() === "" ? null : Number(x)));
  try {
    const r = await api("/api/v1/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (version !== planVersion || shownForecast !== forecast?.forecast_id)
      return;
    if (r.forecast_id !== shownForecast)
      throw new Error("Forecast changed. Refresh and try again.");
    $("result-panel").hidden = false;
    $("savings-title").textContent =
      `${fmt(r.estimated_carbon_reduction_pct)}% ${r.estimated_carbon_reduction_pct >= 0 ? "lower" : "change in"} estimated carbon`;
    $("energy").textContent = `${fmt(r.grid_energy_kwh)} kWh`;
    $("carbon").textContent = `${fmt(r.carbon_kg, 2)} kgCO₂`;
    $("baseline").textContent = `${fmt(r.immediate_carbon_kg, 2)} kgCO₂`;
    $("cost").textContent =
      r.cost_gbp == null ? "Not supplied" : `£${fmt(r.cost_gbp, 2)}`;
    const s = svgEl("svg", { viewBox: "0 0 1100 110" });
    const max = Math.max(...r.slots.map((a) => a.charge_kw), 1);
    r.slots.forEach((a, i) => {
      const h = (a.charge_kw / max) * 78;
      const rect = svgEl("rect", {
        x: (i * 1080) / r.slots.length + 5,
        y: 83 - h,
        width: Math.max(2, 1080 / r.slots.length - 4),
        height: h || 2,
        rx: 2,
        fill: a.charge_kw ? "#aceda0" : "#2b3d46",
      });
      rect.append(
        svgEl("title", {}, `${time(a.timestamp)}: ${fmt(a.charge_kw)} kW`),
      );
      s.append(rect);
      if (i % Math.max(1, Math.round(r.slots.length / 8)) === 0)
        s.append(
          svgEl(
            "text",
            {
              x: (i * 1080) / r.slots.length + 5,
              y: 103,
              fill: "#98aeb7",
              "font-size": 11,
            },
            time(a.timestamp),
          ),
        );
    });
    $("schedule-chart").replaceChildren(s);
    table(
      "schedule-table",
      r.slots
        .filter((a) => a.charge_kw > 0)
        .map((a) => [
          `${date(a.timestamp)} ${time(a.timestamp)}`,
          fmt(a.charge_kw, 2),
          fmt(a.grid_kwh, 3),
          `${fmt(a.soc * 100)}%`,
        ]),
    );
  } catch (e) {
    if (version === planVersion) error(e.message);
  } finally {
    if (version === planVersion) $("schedule-button").disabled = !forecast;
  }
});
$("weather-button").addEventListener("click", async () => {
  $("weather-button").disabled = true;
  try {
    const r = await api("/api/v1/weather");
    const cities = document.createElement("div");
    cities.className = "weather-cities";
    for (const x of r.locations) {
      const d = document.createElement("div");
      const name = document.createElement("div");
      name.textContent = x.location;
      const t = document.createElement("strong");
      t.textContent = `${fmt(x.temperature_2m)}°C`;
      const wind = document.createElement("span");
      wind.textContent = `Wind ${fmt(x.wind_speed_10m)} km/h`;
      d.append(name, t, wind);
      cities.append(d);
    }
    $("weather").replaceChildren(cities);
  } catch (e) {
    error(e.message);
    $("weather-button").disabled = false;
  }
});
async function loadEvidence() {
  try {
    const card = await api("/api/v1/model");
    $("mae").textContent = fmt(card.summary.lightgbm.mae);
    $("coverage").textContent = fmt(card.summary.lightgbm.coverage * 100) + "%";
    const names = {
      lightgbm: "LightGBM",
      persistence: "Persistence",
      weekly_seasonal: "Weekly seasonal",
      daily_seasonal: "Daily seasonal",
      seven_day_mean: "Seven-day clock-time mean",
    };
    table(
      "model-table",
      Object.entries(names).map(([key, name]) => [
        name,
        fmt(card.summary[key].mae, 2),
        fmt(card.summary[key].rmse, 2),
      ]),
    );
    $("data-range").textContent =
      `${card.source_rows.toLocaleString()} real NESO observations · ${date(card.training_data_start)}–${date(card.training_data_end)}`;
    $("gate-status").textContent = card.candidate_gate_passed
      ? "Candidate passed the retrospective baseline and coverage checks. Prospective validation is pending."
      : "Candidate has not passed all retrospective checks. It remains a research comparison.";
  } catch (e) {
    error(e.message);
  }
}
loadForecast();
loadEvidence();
