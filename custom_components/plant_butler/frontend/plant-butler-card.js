/*
 * Plant Butler card for Home Assistant.
 *
 * Shows one plant: photo or icon, status, problems, sensor values against the
 * plant's target ranges and the care tasks, which can be ticked off directly.
 *
 *   type: custom:plant-butler-card
 *   entity: sensor.monstera_status
 *   compact: false        # optional: header and tasks only
 *   show_bars: true       # optional
 *   show_tasks: true      # optional
 *
 * Plain web component without build step; served by the integration.
 */

const CARD_VERSION = "0.7.0";
const DOMAIN = "plant_butler";

const LIGHT_LEVELS = [
  "very_dark",
  "dark",
  "partial_shade",
  "bright_indirect",
  "bright_some_sun",
  "full_sun",
];

const STRINGS = {
  en: {
    status: { ok: "OK", info: "Notice", warning: "Warning", critical: "Critical" },
    problem: {
      needs_water: "Needs water",
      too_wet: "Too wet",
      needs_fertilizer: "Needs fertilizer",
      too_cold: "Too cold",
      too_hot: "Too warm",
      too_dark: "Too dark",
      too_bright: "Too bright",
      sensor_unavailable: "Sensor unavailable",
    },
    light: {
      very_dark: "Very dark",
      dark: "Dark",
      partial_shade: "Partial shade",
      bright_indirect: "Bright, indirect",
      bright_some_sun: "Some sun",
      full_sun: "Direct sun",
    },
    moisture: "Soil moisture",
    lightLabel: "Light",
    temperature: "Room",
    humidity: "Humidity",
    target: "target",
    water: "Water",
    fertilize: "Fertilize",
    today: "due today",
    tomorrow: "tomorrow",
    inDays: (n) => `in ${n} days`,
    overdue: (n) => (n === 1 ? "overdue for 1 day" : `overdue for ${n} days`),
    paused: "paused (winter rest)",
    off: "off",
    winter: "Winter rest",
    markDone: "Mark as done",
    notFound: "Entity not found",
    perWatering: "per watering",
    learned: (n) => `learned: ${n > 0 ? "+" : "−"}${Math.abs(n)} ${Math.abs(n) === 1 ? "day" : "days"}`,
    feedbackQuestion: "How was the soil before watering?",
    feedback: { moist: "Still moist", ok: "Slightly dry", dry: "Very dry" },
    amountQuestion: "How was the amount?",
    amount: { too_much: "Too much", ok: "Just right", too_little: "Too little" },
    undo: "Undo",
    units: { ml_per_l: "ml/l", ml: "ml", sticks: "pcs", g: "g" },
  },
  de: {
    status: { ok: "OK", info: "Hinweis", warning: "Warnung", critical: "Kritisch" },
    problem: {
      needs_water: "Braucht Wasser",
      too_wet: "Zu nass",
      needs_fertilizer: "Braucht Dünger",
      too_cold: "Zu kalt",
      too_hot: "Zu warm",
      too_dark: "Zu dunkel",
      too_bright: "Zu hell",
      sensor_unavailable: "Sensor nicht erreichbar",
    },
    light: {
      very_dark: "Sehr dunkel",
      dark: "Dunkel",
      partial_shade: "Halbschatten",
      bright_indirect: "Hell, indirekt",
      bright_some_sun: "Etwas Sonne",
      full_sun: "Direkte Sonne",
    },
    moisture: "Bodenfeuchte",
    lightLabel: "Licht",
    temperature: "Raum",
    humidity: "Luftfeuchte",
    target: "Soll",
    water: "Gießen",
    fertilize: "Düngen",
    today: "heute fällig",
    tomorrow: "morgen",
    inDays: (n) => `in ${n} Tagen`,
    overdue: (n) => (n === 1 ? "seit 1 Tag überfällig" : `seit ${n} Tagen überfällig`),
    paused: "pausiert (Winterruhe)",
    off: "aus",
    winter: "Winterruhe",
    markDone: "Als erledigt markieren",
    notFound: "Entität nicht gefunden",
    perWatering: "pro Gießen",
    learned: (n) => `gelernt: ${n > 0 ? "+" : "−"}${Math.abs(n)} ${Math.abs(n) === 1 ? "Tag" : "Tage"}`,
    feedbackQuestion: "Wie war die Erde vor dem Gießen?",
    feedback: { moist: "Noch feucht", ok: "Leicht trocken", dry: "Sehr trocken" },
    amountQuestion: "Wie war die Gießmenge?",
    amount: { too_much: "Zu viel", ok: "Passt", too_little: "Zu wenig" },
    undo: "Rückgängig",
    units: { ml_per_l: "ml/l", ml: "ml", sticks: "Stk.", g: "g" },
  },
};

const SEVERITY_COLOR = {
  ok: "var(--success-color, #43a047)",
  info: "var(--info-color, #039be5)",
  warning: "var(--warning-color, #ffa600)",
  critical: "var(--error-color, #db4437)",
};

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

let numberLocale;
const fmt = (value, digits = 0) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "–";
  return n.toLocaleString(numberLocale, { maximumFractionDigits: digits });
};

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

/** Whole calendar days from today to the given date (negative = past). */
const calendarDays = (iso) => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const today = new Date();
  const a = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const b = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.round((b - a) / 86400000);
};

class PlantButlerCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("plant-butler-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.values(hass.entities || {}).find(
      (e) => e.platform === DOMAIN && e.translation_key === "status"
    );
    return { entity: entity ? entity.entity_id : "" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._signature = "";
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Please set 'entity' to the status sensor of a plant");
    }
    this._config = { show_bars: true, show_tasks: true, compact: false, show_area: true, ...config };
    this._signature = "";
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signature = this._computeSignature();
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  getCardSize() {
    return this._config && this._config.compact ? 2 : 5;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }

  // ------------------------------------------------------------- data access
  get _t() {
    const lang = (this._hass && this._hass.locale && this._hass.locale.language) ||
      (this._hass && this._hass.language) || "en";
    return STRINGS[lang.slice(0, 2)] || STRINGS.en;
  }

  /** Map translation_key -> entity_id for all entities of this plant. */
  _relatedEntities() {
    const hass = this._hass;
    const statusId = this._config.entity;
    const result = {};
    const reg = hass.entities && hass.entities[statusId];
    if (reg && reg.device_id) {
      for (const entry of Object.values(hass.entities)) {
        if (entry.device_id === reg.device_id && entry.platform === DOMAIN && entry.translation_key) {
          result[entry.translation_key] = entry.entity_id;
        }
      }
      return result;
    }
    // Fallback: derive ids from the status entity id
    const base = statusId.replace(/^sensor\./, "").replace(/_status$/, "");
    for (const [key, domain] of Object.entries({
      next_watering: "sensor",
      next_fertilizing: "sensor",
      photo: "image",
    })) {
      result[key] = `${domain}.${base}_${key}`;
    }
    return result;
  }

  _computeSignature() {
    if (!this._hass || !this._config) return "";
    const st = this._hass.states[this._config.entity];
    if (!st) return "missing";
    const ids = Object.values(this._relatedEntities());
    const sensors = (st.attributes && st.attributes.sensors) || {};
    ids.push(...Object.values(sensors).filter(Boolean));
    const parts = [st.last_updated];
    for (const id of ids) {
      const s = this._hass.states[id];
      parts.push(s ? `${s.state}|${s.last_updated}` : "-");
    }
    parts.push(this._t === STRINGS.de ? "de" : "en");
    parts.push(this._feedbackUntil && Date.now() < this._feedbackUntil ? `fb${[...this._fbDone].join()}` : "");
    return parts.join(";");
  }

  _num(entityId) {
    if (!entityId) return null;
    const s = this._hass.states[entityId];
    if (!s) return null;
    const n = parseFloat(s.state);
    return Number.isFinite(n) ? { value: n, unit: s.attributes.unit_of_measurement || "" } : null;
  }

  // ---------------------------------------------------------------- actions
  _moreInfo(entityId) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true })
    );
  }

  async _markDone(task, button) {
    button.disabled = true;
    try {
      await this._hass.callService(DOMAIN, "mark_done", {
        entity_id: this._config.entity,
        task,
      });
      if (task === "water") this._openFeedback();
    } finally {
      button.disabled = false;
    }
  }

  _openFeedback() {
    this._fbDone = new Set();
    this._extendFeedback();
  }

  _extendFeedback() {
    this._feedbackUntil = Date.now() + 30000;
    clearTimeout(this._feedbackTimer);
    this._feedbackTimer = setTimeout(() => this._closeFeedback(), 30000);
    this._render();
  }

  _closeFeedback() {
    this._feedbackUntil = 0;
    clearTimeout(this._feedbackTimer);
    this._render();
  }

  async _sendFeedback(kind, value) {
    this._fbDone.add(kind);
    this._extendFeedback();
    await this._hass.callService(DOMAIN, "watering_feedback", {
      entity_id: this._config.entity,
      [kind]: value,
    });
  }

  async _undo() {
    this._closeFeedback();
    await this._hass.callService(DOMAIN, "undo_watering", { entity_id: this._config.entity });
  }

  _renderFeedback(a) {
    if (!this._feedbackUntil || Date.now() > this._feedbackUntil) return "";
    const t = this._t;
    const learning = (a.care && a.care.learning) || {};
    const done = this._fbDone || new Set();
    const active = !learning.paused;
    const askInterval = active && learning.learn_interval && !done.has("answer");
    const askAmount =
      active && learning.learn_amount && learning.awaiting_amount && !done.has("amount");
    const row = (kind, question, keys, labels) => `
        <div class="fb-q">${esc(question)}</div>
        <div class="fb-row">${keys
          .map(
            (k) =>
              `<button class="fb" data-kind="${kind}" data-answer="${k}">${esc(labels[k])}</button>`
          )
          .join("")}</div>`;
    return `
      <div class="feedback">
        ${askInterval ? row("answer", t.feedbackQuestion, ["moist", "ok", "dry"], t.feedback) : ""}
        ${askAmount ? row("amount", t.amountQuestion, ["too_much", "ok", "too_little"], t.amount) : ""}
        <div class="fb-row fb-undo"><button class="fb undo" data-undo="1"><ha-icon icon="mdi:undo-variant"></ha-icon>${esc(t.undo)}</button></div>
      </div>`;
  }

  // ---------------------------------------------------------------- rendering
  _render() {
    const t = this._t;
    numberLocale = (this._hass.locale && this._hass.locale.language) || this._hass.language;
    const st = this._hass.states[this._config.entity];
    if (!st) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="missing">${esc(t.notFound)}: ${esc(
        this._config.entity
      )}</div></ha-card>`;
      return;
    }
    const a = st.attributes;
    const ents = this._relatedEntities();
    const status = st.state in SEVERITY_COLOR ? st.state : "ok";
    const name = this._config.name || a.plant_name || a.friendly_name;
    const photoState = ents.photo && this._hass.states[ents.photo];
    const picture = photoState && photoState.attributes.entity_picture;
    const color = SEVERITY_COLOR[status];

    const avatar = picture
      ? `<img class="photo" src="${esc(picture)}" alt="">`
      : `<div class="photo icon" style="--c:${color}"><ha-icon icon="${esc(
          a.icon || "mdi:flower"
        )}"></ha-icon></div>`;

    const problems = (a.problems || [])
      .map((p) => {
        const sev = (a.problem_severities || {})[p] || "info";
        return `<span class="chip" style="--c:${SEVERITY_COLOR[sev]}">${esc(
          t.problem[p] || p
        )}</span>`;
      })
      .join("");

    const compact = this._config.compact;
    const bars = !compact && this._config.show_bars ? this._renderBars(a) : "";
    const tasks = this._config.show_tasks ? this._renderTasks(a, ents) : "";

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card class="${compact ? "compact" : ""}">
        <div class="header" data-more="${esc(this._config.entity)}">
          ${avatar}
          <div class="title">
            <div class="name">${esc(name)}</div>
            <div class="sub">${[
              this._config.show_area && a.area ? esc(a.area) : "",
              a.winter_rest ? `<ha-icon icon="mdi:snowflake"></ha-icon> ${esc(t.winter)}` : "",
            ]
              .filter(Boolean)
              .join(" · ")}</div>
          </div>
          <span class="pill" style="--c:${color}">${esc(t.status[status])}</span>
        </div>
        ${problems ? `<div class="problems">${problems}</div>` : ""}
        ${bars}
        ${tasks}
        ${this._renderFeedback(a)}
      </ha-card>`;

    this.shadowRoot.querySelector(".header").addEventListener("click", () =>
      this._moreInfo(this._config.entity)
    );
    this.shadowRoot.querySelectorAll("button[data-task]").forEach((button) =>
      button.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._markDone(button.dataset.task, button);
      })
    );
    this.shadowRoot.querySelectorAll("button[data-answer]").forEach((el) =>
      el.addEventListener("click", () => this._sendFeedback(el.dataset.kind, el.dataset.answer))
    );
    const undoButton = this.shadowRoot.querySelector("button[data-undo]");
    if (undoButton) undoButton.addEventListener("click", () => this._undo());
    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) =>
      el.addEventListener("click", () => this._moreInfo(el.dataset.entity))
    );
  }

  _bar({ label, valueText, entity, min, max, value, zone, ok, segments }) {
    const pos = clamp(((value - min) / (max - min)) * 100, 0, 100);
    const zoneHtml = zone
      ? `<div class="zone" style="left:${clamp(((zone[0] - min) / (max - min)) * 100, 0, 100)}%;width:${
          clamp(((zone[1] - min) / (max - min)) * 100, 0, 100) -
          clamp(((zone[0] - min) / (max - min)) * 100, 0, 100)
        }%"></div>`
      : "";
    const ticks = segments
      ? Array.from({ length: segments - 1 }, (_, i) =>
          `<div class="tick" style="left:${((i + 1) / segments) * 100}%"></div>`
        ).join("")
      : "";
    const dot = ok === null ? "var(--secondary-text-color)" : ok ? SEVERITY_COLOR.ok : SEVERITY_COLOR.warning;
    return `
      <div class="bar-row" ${entity ? `data-entity="${esc(entity)}"` : ""}>
        <div class="bar-label">${label}</div>
        <div class="bar-value">${valueText}</div>
        <div class="track">${zoneHtml}${ticks}<div class="dot" style="left:${pos}%;--c:${dot}"></div></div>
      </div>`;
  }

  _renderBars(a) {
    const t = this._t;
    const sensors = a.sensors || {};
    const targets = a.targets || {};
    const rows = [];

    const moisture = this._num(sensors.moisture);
    if (moisture) {
      const lo = Number(targets.moisture_min);
      const hi = Number(targets.moisture_max);
      rows.push(
        this._bar({
          label: esc(t.moisture),
          valueText: `${fmt(moisture.value)} %<span class="target"> · ${esc(t.target)} ${fmt(lo)}–${fmt(hi)} %</span>`,
          entity: sensors.moisture,
          min: 0,
          max: 100,
          value: moisture.value,
          zone: [lo, hi],
          ok: moisture.value >= lo && moisture.value <= hi,
        })
      );
    }

    const light = a.light || {};
    const need = LIGHT_LEVELS.indexOf(targets.light_need);
    const actual = LIGHT_LEVELS.indexOf(light.level);
    if (actual >= 0 && need >= 0) {
      rows.push(
        this._bar({
          label: esc(t.lightLabel),
          valueText: `${esc(t.light[light.level])}<span class="target"> · ${esc(t.target)} ${esc(
            t.light[targets.light_need]
          )}</span>`,
          entity: sensors.illuminance,
          min: 0,
          max: LIGHT_LEVELS.length,
          value: actual + 0.5,
          zone: [need, Math.min(need + 2, LIGHT_LEVELS.length)],
          ok: actual >= need && actual <= need + 1,
          segments: LIGHT_LEVELS.length,
        })
      );
    }

    const temp = this._num(sensors.temperature);
    if (temp) {
      const lo = Number(targets.temperature_min);
      const hi = Number(targets.temperature_max);
      rows.push(
        this._bar({
          label: esc(t.temperature),
          valueText: `${fmt(temp.value, 1)} ${esc(temp.unit)}<span class="target"> · ${esc(t.target)} ${fmt(lo)}–${fmt(hi)}</span>`,
          entity: sensors.temperature,
          min: lo - 8,
          max: hi + 8,
          value: temp.value,
          zone: [lo, hi],
          ok: temp.value >= lo && temp.value <= hi,
        })
      );
    }

    const hum = this._num(sensors.humidity);
    if (hum) {
      rows.push(
        this._bar({
          label: esc(t.humidity),
          valueText: `${fmt(hum.value)} %`,
          entity: sensors.humidity,
          min: 0,
          max: 100,
          value: hum.value,
          zone: null,
          ok: null,
        })
      );
    }
    return rows.length ? `<div class="bars">${rows.join("")}</div>` : "";
  }

  _whenText(iso, due) {
    const t = this._t;
    const days = iso ? calendarDays(iso) : null;
    if (days === null) return "";
    if (due || days <= 0) return days < 0 ? t.overdue(-days) : t.today;
    if (days === 1) return t.tomorrow;
    return t.inDays(days);
  }

  _renderTasks(a, ents) {
    const t = this._t;
    const care = a.care || {};
    const rows = [];

    const waterState = ents.next_watering && this._hass.states[ents.next_watering];
    const waterAmount = care.watering_amount ? `${fmt(care.watering_amount)} ml` : "";
    rows.push(
      this._taskRow({
        task: "water",
        icon: "mdi:watering-can",
        label: t.water,
        amount: waterAmount,
        due: !!a.needs_water,
        when: [
          waterState ? this._whenText(waterState.state, a.needs_water) : "",
          care.learning && care.learning.learn_interval && care.learning.interval_delta_days
            ? t.learned(care.learning.interval_delta_days)
            : "",
        ]
          .filter(Boolean)
          .join(" · "),
        entity: ents.next_watering,
      })
    );

    const fertState = ents.next_fertilizing && this._hass.states[ents.next_fertilizing];
    const fertEnabled = !fertState || fertState.attributes.enabled !== false;
    if (fertEnabled) {
      let amount = "";
      if (care.fertilizer_amount) {
        amount = `${fmt(care.fertilizer_amount, 1)} ${esc(t.units[care.fertilizer_unit] || "")}`;
        if (care.fertilizer_per_watering_ml) {
          amount += ` (≈ ${fmt(care.fertilizer_per_watering_ml, 1)} ml)`;
        }
      }
      const paused = fertState && (fertState.state === "unknown" || fertState.state === "unavailable");
      rows.push(
        this._taskRow({
          task: "fertilize",
          icon: "mdi:sprout",
          label: t.fertilize,
          amount,
          due: !!a.needs_fertilizer,
          when: paused ? t.paused : fertState ? this._whenText(fertState.state, a.needs_fertilizer) : "",
          entity: ents.next_fertilizing,
        })
      );
    }
    return `<div class="tasks">${rows.join("")}</div>`;
  }

  _taskRow({ task, icon, label, amount, due, when, entity }) {
    const t = this._t;
    return `
      <div class="task ${due ? "due" : ""}">
        <ha-icon class="task-icon" icon="${icon}"></ha-icon>
        <div class="task-text" ${entity ? `data-entity="${esc(entity)}"` : ""}>
          <div class="task-name">${esc(label)}${amount ? ` <span class="amount">– ${amount}</span>` : ""}</div>
          <div class="task-when">${esc(when)}</div>
        </div>
        <button class="check" data-task="${task}" title="${esc(t.markDone)}" aria-label="${esc(
          t.markDone
        )}: ${esc(label)}">
          <ha-icon icon="mdi:checkbox-blank-circle-outline"></ha-icon>
        </button>
      </div>`;
  }
}

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; overflow: hidden; }
  .missing { color: var(--error-color, #db4437); }
  .header { display: flex; align-items: center; gap: 12px; cursor: pointer; }
  .photo { width: 56px; height: 56px; border-radius: 50%; object-fit: cover; flex: none; }
  .compact .photo { width: 44px; height: 44px; }
  .photo.icon {
    display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--c) 18%, transparent); color: var(--c);
  }
  .photo.icon ha-icon { --mdc-icon-size: 30px; }
  .title { flex: 1; min-width: 0; }
  .name { font-size: 1.15em; font-weight: 600; color: var(--primary-text-color);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { color: var(--secondary-text-color); font-size: 0.9em; display: flex; align-items: center; gap: 4px; }
  .sub ha-icon { --mdc-icon-size: 16px; }
  .pill {
    flex: none; padding: 3px 12px; border-radius: 999px; font-size: 0.85em; font-weight: 600;
    color: var(--primary-text-color); border: 1px solid var(--c);
    background: color-mix(in srgb, var(--c) 18%, transparent);
  }
  .problems { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .chip {
    font-size: 0.8em; padding: 2px 8px; border-radius: 999px; color: var(--primary-text-color);
    background: color-mix(in srgb, var(--c) 16%, transparent);
  }
  .bars { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--divider-color); display: grid; gap: 10px; }
  .bar-row { display: grid; grid-template-columns: auto 1fr; row-gap: 4px; cursor: pointer; }
  .bar-label { color: var(--primary-text-color); font-size: 0.9em; }
  .bar-value { text-align: right; font-size: 0.9em; color: var(--primary-text-color); }
  .target { color: var(--secondary-text-color); }
  .track {
    grid-column: 1 / -1; position: relative; height: 8px; border-radius: 4px;
    background: var(--secondary-background-color, rgba(127,127,127,0.15));
  }
  .zone {
    position: absolute; top: -3px; bottom: -3px; border-radius: 3px;
    background: color-mix(in srgb, var(--success-color, #43a047) 28%, transparent);
  }
  .tick { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--card-background-color, #fff); opacity: 0.8; }
  .dot {
    position: absolute; top: 50%; width: 14px; height: 14px; border-radius: 50%;
    transform: translate(-50%, -50%); background: var(--c);
    box-shadow: 0 0 0 2px var(--card-background-color, #fff);
  }
  .tasks { margin-top: 14px; padding-top: 6px; border-top: 1px solid var(--divider-color); }
  .compact .tasks { margin-top: 10px; }
  .task { display: flex; align-items: center; gap: 12px; padding: 6px 0; }
  .task-icon { color: var(--secondary-text-color); flex: none; }
  .task.due .task-icon { color: var(--warning-color, #ffa600); }
  .task-text { flex: 1; min-width: 0; cursor: pointer; }
  .task-name { color: var(--primary-text-color); }
  .task.due .task-name { font-weight: 600; }
  .amount { font-weight: 400; color: var(--secondary-text-color); }
  .task-when { font-size: 0.85em; color: var(--secondary-text-color); }
  .task.due .task-when { color: var(--warning-color, #ffa600); }
  .check {
    flex: none; border: none; background: none; cursor: pointer; padding: 6px; border-radius: 50%;
    color: var(--secondary-text-color); opacity: 0.45;
  }
  .check ha-icon { --mdc-icon-size: 28px; }
  .task.due .check { color: var(--primary-color); opacity: 1; }
  .check:hover { background: color-mix(in srgb, var(--primary-color) 12%, transparent); opacity: 1; }
  .check:disabled { opacity: 0.3; cursor: progress; }
  .feedback {
    margin-top: 8px; padding: 10px 12px; border-radius: 12px;
    background: color-mix(in srgb, var(--primary-color) 10%, transparent);
  }
  .fb-q { font-size: 0.9em; color: var(--primary-text-color); margin-bottom: 8px; }
  .fb-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .fb-row.fb-undo { margin-bottom: 0; }
  .fb {
    border: 1px solid var(--divider-color); background: var(--card-background-color, #fff);
    color: var(--primary-text-color); border-radius: 999px; padding: 6px 12px; cursor: pointer;
    font: inherit; font-size: 0.85em; display: inline-flex; align-items: center; gap: 4px;
  }
  .fb:hover { border-color: var(--primary-color); }
  .fb.undo { color: var(--secondary-text-color); }
  .fb ha-icon { --mdc-icon-size: 16px; }
`;

class PlantButlerCardEditor extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  _render() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => {
        const de = this._hass && (this._hass.language || "").startsWith("de");
        const labels = {
          entity: de ? "Pflanze (Status-Sensor)" : "Plant (status sensor)",
          name: de ? "Name (optional)" : "Name (optional)",
          compact: de ? "Kompakt" : "Compact",
          show_bars: de ? "Sensorbalken anzeigen" : "Show sensor bars",
          show_tasks: de ? "Aufgaben anzeigen" : "Show tasks",
        };
        return labels[schema.name] || schema.name;
      };
      this._form.addEventListener("value-changed", (ev) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: ev.detail.value },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [
      { name: "entity", required: true, selector: { entity: { integration: DOMAIN, domain: "sensor" } } },
      { name: "name", selector: { text: {} } },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "compact", selector: { boolean: {} } },
          { name: "show_bars", selector: { boolean: {} } },
          { name: "show_tasks", selector: { boolean: {} } },
        ],
      },
    ];
    this._form.data = { show_bars: true, show_tasks: true, compact: false, ...this._config };
  }
}


// ===========================================================================
// Overview card: all plants grouped by room, collapsible, updates itself.
// ===========================================================================

const OV_STRINGS = {
  en: {
    plants: (n) => (n === 1 ? "1 plant" : `${n} plants`),
    due: (n) => `${n} due`,
    water: "need water",
    fertilize: "need fertilizer",
    warnings: "warnings",
    noRoom: "No room",
    noPlants: "No plants yet – add them under Settings → Devices & services → Plant Butler → Add plant.",
    nothingDue: "All done – no plant needs water or fertilizer right now.",
    overview: "Overview",
    dueView: "Due",
    todo: "To-do list",
    title: "Plants",
  },
  de: {
    plants: (n) => (n === 1 ? "1 Pflanze" : `${n} Pflanzen`),
    due: (n) => `${n} fällig`,
    water: "brauchen Wasser",
    fertilize: "brauchen Dünger",
    warnings: "Warnungen",
    noRoom: "Ohne Raum",
    noPlants: "Noch keine Pflanzen – füge sie unter Einstellungen → Geräte & Dienste → Plant Butler → Pflanze hinzufügen hinzu.",
    nothingDue: "Alles erledigt – keine Pflanze braucht gerade Wasser oder Dünger.",
    overview: "Übersicht",
    dueView: "Fällig",
    todo: "To-do-Liste",
    title: "Pflanzen",
  },
};

const SEVERITY_ORDER = ["ok", "info", "warning", "critical"];
const COLLAPSE_KEY = "plant-butler-collapsed-rooms";

const langOf = (hass) =>
  ((hass && ((hass.locale && hass.locale.language) || hass.language)) || "en").slice(0, 2);
const ovStrings = (hass) => OV_STRINGS[langOf(hass)] || OV_STRINGS.en;

/** All Plant Butler plants: status entity, name, room, state. */
const findPlants = (hass) => {
  const plants = [];
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform !== DOMAIN || entry.translation_key !== "status") continue;
    const st = hass.states[entry.entity_id];
    if (!st) continue;
    const device = entry.device_id && hass.devices ? hass.devices[entry.device_id] : null;
    const areaId = entry.area_id || (device && device.area_id) || null;
    const area = areaId && hass.areas ? hass.areas[areaId] : null;
    plants.push({
      entity: entry.entity_id,
      name: st.attributes.plant_name || st.attributes.friendly_name || entry.entity_id,
      areaId: areaId || "",
      areaName: area ? area.name : st.attributes.area || "",
      status: st.state,
      due: !!(st.attributes.needs_water || st.attributes.needs_fertilizer),
      water: !!st.attributes.needs_water,
      fertilize: !!st.attributes.needs_fertilizer,
    });
  }
  return plants;
};

const loadCollapsed = () => {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(COLLAPSE_KEY) || "[]"));
  } catch (err) {
    return new Set();
  }
};
const saveCollapsed = (set) => {
  try {
    window.localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...set]));
  } catch (err) {
    /* storage unavailable: collapsing still works for this session */
  }
};

class PlantButlerOverviewCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("plant-butler-overview-card-editor");
  }

  static getStubConfig() {
    return { filter: "all" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cards = new Map();
    this._structure = "";
    this._collapsed = loadCollapsed();
  }

  setConfig(config) {
    this._config = {
      filter: "all",
      compact: false,
      collapsible: true,
      group_by_room: true,
      show_summary: true,
      ...config,
    };
    this._structure = "";
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: "full", rows: "auto" };
  }

  _plants() {
    let plants = findPlants(this._hass);
    if (this._config.filter === "due") plants = plants.filter((p) => p.due);
    if (this._config.area) plants = plants.filter((p) => p.areaId === this._config.area);
    return plants;
  }

  _groups(plants) {
    const t = ovStrings(this._hass);
    const groups = new Map();
    for (const plant of plants) {
      const key = this._config.group_by_room ? plant.areaId : "_all";
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          name: this._config.group_by_room ? plant.areaName || t.noRoom : "",
          plants: [],
        });
      }
      groups.get(key).plants.push(plant);
    }
    const list = [...groups.values()];
    list.forEach((g) => g.plants.sort((a, b) => a.name.localeCompare(b.name)));
    // Rooms alphabetically, plants without room last
    list.sort((a, b) => (a.key === "") - (b.key === "") || a.name.localeCompare(b.name));
    return list;
  }

  _cardFor(plant) {
    const compact = !!this._config.compact;
    const key = `${plant.entity}|${compact}`;
    let card = this._cards.get(key);
    if (!card) {
      card = document.createElement("plant-butler-card");
      card.setConfig({ entity: plant.entity, compact, show_area: !this._config.group_by_room });
      this._cards.set(key, card);
    }
    card.hass = this._hass;
    return card;
  }

  _update() {
    if (!this._hass || !this._config) return;
    const plants = this._plants();
    const groups = this._groups(plants);
    const t = ovStrings(this._hass);
    // Rebuild the DOM only when plants, rooms or headers change
    const structure = JSON.stringify([
      langOf(this._hass),
      groups.map((g) => [g.key, g.name, g.plants.map((p) => [p.entity, p.status, p.due])]),
    ]);
    if (structure !== this._structure) {
      this._structure = structure;
      this._render(groups, plants, t);
    } else {
      for (const plant of plants) this._cardFor(plant);
    }
  }

  _summary(plants, t) {
    const all = this._config.filter === "due" ? findPlants(this._hass) : plants;
    const water = all.filter((p) => p.water).length;
    const fert = all.filter((p) => p.fertilize).length;
    const warn = all.filter((p) => p.status === "warning" || p.status === "critical").length;
    return `
      <div class="summary">
        <span><ha-icon icon="mdi:flower"></ha-icon><b>${esc(t.plants(all.length))}</b></span>
        <span class="${water ? "hot" : ""}"><ha-icon icon="mdi:watering-can"></ha-icon><b>${water}</b> ${esc(t.water)}</span>
        <span class="${fert ? "hot" : ""}"><ha-icon icon="mdi:sprout"></ha-icon><b>${fert}</b> ${esc(t.fertilize)}</span>
        <span class="${warn ? "bad" : ""}"><ha-icon icon="mdi:alert-outline"></ha-icon><b>${warn}</b> ${esc(t.warnings)}</span>
      </div>`;
  }

  _render(groups, plants, t) {
    const root = this.shadowRoot;
    const summary = this._config.show_summary ? this._summary(plants, t) : "";
    if (!plants.length) {
      const text = this._config.filter === "due" ? t.nothingDue : t.noPlants;
      root.innerHTML = `<style>${OV_STYLE}</style>${summary}<ha-card class="empty">${esc(text)}</ha-card>`;
      return;
    }
    const collapsible = this._config.collapsible && this._config.group_by_room;
    root.innerHTML = `<style>${OV_STYLE}</style>${summary}${groups
      .map((g) => {
        const due = g.plants.filter((p) => p.due).length;
        const worst = g.plants.reduce(
          (w, p) => (SEVERITY_ORDER.indexOf(p.status) > SEVERITY_ORDER.indexOf(w) ? p.status : w),
          "ok"
        );
        const header = this._config.group_by_room
          ? `<summary class="${collapsible ? "" : "static"}">
              <ha-icon class="chevron" icon="mdi:chevron-down"></ha-icon>
              <span class="room">${esc(g.name)}</span>
              <span class="count">${esc(t.plants(g.plants.length))}</span>
              ${due ? `<span class="due">${esc(t.due(due))}</span>` : ""}
              <span class="dot" style="--c:${SEVERITY_COLOR[worst]}"></span>
            </summary>`
          : "";
        const open = !collapsible || !this._collapsed.has(g.key);
        return `<details data-key="${esc(g.key)}" ${open ? "open" : ""}>${header}<div class="grid"></div></details>`;
      })
      .join("")}`;

    root.querySelectorAll("details").forEach((details, i) => {
      const grid = details.querySelector(".grid");
      for (const plant of groups[i].plants) grid.appendChild(this._cardFor(plant));
      const summaryEl = details.querySelector("summary");
      if (!summaryEl) return;
      summaryEl.addEventListener("click", (ev) => {
        if (!collapsible) {
          ev.preventDefault();
          return;
        }
        // Remember the state after the browser toggled it
        setTimeout(() => {
          if (details.open) this._collapsed.delete(details.dataset.key);
          else this._collapsed.add(details.dataset.key);
          saveCollapsed(this._collapsed);
        });
      });
    });
  }
}

const OV_STYLE = `
  :host { display: block; }
  .summary {
    display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: center;
    padding: 4px 4px 12px; color: var(--primary-text-color);
  }
  .summary span { display: inline-flex; align-items: center; gap: 6px; }
  .summary ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .summary .hot ha-icon { color: var(--warning-color, #ffa600); }
  .summary .bad ha-icon { color: var(--error-color, #db4437); }
  details { margin-bottom: 12px; }
  summary {
    list-style: none; display: flex; align-items: center; gap: 10px; cursor: pointer;
    padding: 10px 12px; border-radius: 12px; user-select: none;
    background: var(--secondary-background-color, rgba(127,127,127,0.12));
    color: var(--primary-text-color);
  }
  summary.static { cursor: default; }
  summary::-webkit-details-marker { display: none; }
  .chevron { transition: transform 0.2s; color: var(--secondary-text-color); }
  details:not([open]) .chevron { transform: rotate(-90deg); }
  summary.static .chevron { display: none; }
  .room { font-size: 1.1em; font-weight: 600; }
  .count { color: var(--secondary-text-color); font-size: 0.9em; }
  .due {
    font-size: 0.8em; font-weight: 600; padding: 2px 8px; border-radius: 999px;
    background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
  }
  .dot { margin-left: auto; width: 10px; height: 10px; border-radius: 50%; background: var(--c); }
  .grid {
    display: grid; gap: 12px; padding-top: 12px;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); align-items: start;
  }
  .empty { padding: 16px; color: var(--secondary-text-color); }
`;

class PlantButlerOverviewCardEditor extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  setConfig(config) {
    this._config = config;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => {
        const de = langOf(this._hass) === "de";
        const labels = {
          filter: de ? "Anzeigen" : "Show",
          area: de ? "Nur dieser Raum (optional)" : "Only this room (optional)",
          compact: de ? "Kompakte Karten" : "Compact cards",
          collapsible: de ? "Räume einklappbar" : "Collapsible rooms",
          group_by_room: de ? "Nach Raum gruppieren" : "Group by room",
          show_summary: de ? "Zusammenfassung anzeigen" : "Show summary",
        };
        return labels[schema.name] || schema.name;
      };
      this._form.addEventListener("value-changed", (ev) =>
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config: ev.detail.value }, bubbles: true, composed: true })
        )
      );
      this.appendChild(this._form);
    }
    const de = langOf(this._hass) === "de";
    this._form.hass = this._hass;
    this._form.schema = [
      {
        name: "filter",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "all", label: de ? "Alle Pflanzen" : "All plants" },
              { value: "due", label: de ? "Nur fällige Pflanzen" : "Only plants with due tasks" },
            ],
          },
        },
      },
      { name: "area", selector: { area: {} } },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "group_by_room", selector: { boolean: {} } },
          { name: "collapsible", selector: { boolean: {} } },
          { name: "compact", selector: { boolean: {} } },
          { name: "show_summary", selector: { boolean: {} } },
        ],
      },
    ];
    this._form.data = {
      filter: "all",
      compact: false,
      collapsible: true,
      group_by_room: true,
      show_summary: true,
      ...config,
    };
  }
}

// ===========================================================================
// Dashboard strategy: `strategy: {type: custom:plant-butler}`
// Generates the views each time the dashboard is opened.
// ===========================================================================

class PlantButlerDashboardStrategy extends HTMLElement {
  static async generate(config, hass) {
    const t = ovStrings(hass);
    return {
      title: t.title,
      views: [
        {
          title: t.overview,
          path: "overview",
          icon: "mdi:flower",
          type: "sections",
          max_columns: 4,
          sections: [
            {
              type: "grid",
              column_span: 4,
              cards: [{ type: "custom:plant-butler-overview-card", grid_options: { columns: "full" } }],
            },
          ],
        },
        {
          title: t.dueView,
          path: "due",
          icon: "mdi:clipboard-check-outline",
          type: "sections",
          max_columns: 4,
          sections: [
            {
              type: "grid",
              column_span: 3,
              cards: [
                {
                  type: "custom:plant-butler-overview-card",
                  filter: "due",
                  compact: true,
                  grid_options: { columns: "full" },
                },
              ],
            },
            {
              type: "grid",
              column_span: 1,
              cards: [
                { type: "heading", heading: t.todo, icon: "mdi:clipboard-check-outline" },
                { type: "todo-list", entity: "todo.plant_butler", hide_create: true },
              ],
            },
          ],
        },
      ],
    };
  }
}

if (!customElements.get("plant-butler-card")) {
  customElements.define("plant-butler-card", PlantButlerCard);
  customElements.define("plant-butler-card-editor", PlantButlerCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "plant-butler-card",
    name: "Plant Butler",
    description: "A plant with photo, status, sensor values and care tasks.",
    preview: true,
    documentationURL: "https://github.com/DomJoke/ha-plant-butler",
  });
  console.info(`%c PLANT-BUTLER-CARD %c ${CARD_VERSION} `, "background:#43a047;color:#fff", "");
}
if (!customElements.get("plant-butler-overview-card")) {
  customElements.define("plant-butler-overview-card", PlantButlerOverviewCard);
  customElements.define("plant-butler-overview-card-editor", PlantButlerOverviewCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "plant-butler-overview-card",
    name: "Plant Butler – Overview",
    description: "All plants grouped by room, collapsible, updates itself.",
    preview: false,
    documentationURL: "https://github.com/DomJoke/ha-plant-butler",
  });
}
if (!customElements.get("ll-strategy-dashboard-plant-butler")) {
  customElements.define("ll-strategy-dashboard-plant-butler", PlantButlerDashboardStrategy);
}
