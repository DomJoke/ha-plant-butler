"""Runtime model of a single plant and the hub holding all plants."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .care import suggest_watering
from .const import (
    CONF_AREA,
    CONF_CLIMATE_STRENGTH,
    CONF_FERTILIZER_INTERVAL,
    CONF_FERTILIZER_WINTER_INTERVAL,
    CONF_HUMIDITY_SENSOR,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_NEED,
    CONF_LOCATION_LIGHT,
    CONF_MOISTURE_MAX,
    CONF_MOISTURE_MIN,
    CONF_MOISTURE_SENSOR,
    CONF_NAME,
    CONF_PLANT_SIZE,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    CONF_TEMPERATURE_SENSOR,
    CONF_WATER_NEED,
    CONF_WATERING_INTERVAL,
    DEFAULT_CLIMATE_STRENGTH,
    DOMAIN,
    EVENT_NOTIFICATION,
    MOISTURE_HYSTERESIS,
    SENSOR_KEYS,
    SEVERITIES,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_OK,
    SEVERITY_WARNING,
    STORAGE_VERSION,
    TASK_FERTILIZE,
    TASK_WATER,
    WATER_LEVELS,
    WATERING_DETECT_RISE,
    WINTER_WATER_FACTOR,
)
from .logic import (
    climate_factor,
    dli_increment,
    light_level_for_dli,
    light_mismatch,
    moisture_slope_per_day,
    worst_severity,
)
from .notifications import Notifier

_LOGGER = logging.getLogger(__name__)

TICK_INTERVAL = timedelta(minutes=10)
WATERED_GRACE = timedelta(hours=2)
SAMPLE_WINDOW = timedelta(hours=48)
DLI_HISTORY_DAYS = 7
LIGHT_PROBLEM_DAYS = 3

type PlantButlerConfigEntry = ConfigEntry[ButlerHub]


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class Problem:
    """An active problem of a plant."""

    key: str
    severity: str


@dataclass
class Evaluation:
    """Derived state of a plant at a point in time."""

    moisture: float | None = None
    illuminance: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    needs_water: bool = False
    needs_fertilizer: bool = False
    fertilizing_enabled: bool = True
    next_watering: datetime | None = None
    next_fertilizing: datetime | None = None
    water_overdue_days: float = 0.0
    fertilizer_overdue_days: float = 0.0
    climate_factor: float = 1.0
    watering_interval_effective: float = 7.0
    dli_today: float | None = None
    dli_yesterday: float | None = None
    light_level: str | None = None
    light_problem: str | None = None
    temperature_problem: str | None = None
    problems: list[Problem] = field(default_factory=list)
    status: str = SEVERITY_OK


def default_state(now: datetime) -> dict[str, Any]:
    """Return the initial persisted state of a plant."""
    return {
        "created": _iso(now),
        "last_watered": None,
        "last_fertilized": None,
        "water_progress": 0.0,
        "fert_progress": 0.0,
        "progress_updated": _iso(now),
        "water_due_since": None,
        "fert_due_since": None,
        "moisture_dry": False,
        "dli_today": 0.0,
        "dli_date": None,
        "dli_history": [],
        "overrides": {},
        "winter_rest": False,
        "applied_area": None,
        "notified": {},
        "notify_enabled": True,
    }


class PlantRuntime:
    """A plant: settings, persisted care state and evaluation logic."""

    def __init__(
        self, hass: HomeAssistant, hub: ButlerHub, subentry: ConfigSubentry
    ) -> None:
        """Initialize the plant."""
        self.hass = hass
        self.hub = hub
        self.subentry = subentry
        self.id = subentry.subentry_id
        state = hub.store_data["plants"].setdefault(
            self.id, default_state(dt_util.utcnow())
        )
        for key, value in default_state(dt_util.utcnow()).items():
            state.setdefault(key, value)
        self.state: dict[str, Any] = state
        self.slug = slugify(subentry.data.get(CONF_NAME) or subentry.title) or "plant"
        self.device_id: str | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._samples: deque[tuple[datetime, float]] = deque(maxlen=2000)
        self._last_lux: tuple[datetime, float] | None = None
        self.evaluation = Evaluation()

    # ------------------------------------------------------------------ settings
    @property
    def name(self) -> str:
        """Return the plant name."""
        return self.subentry.data.get(CONF_NAME) or self.subentry.title

    @property
    def settings(self) -> dict[str, Any]:
        """Effective settings: subentry data, level defaults, then overrides."""
        overrides = self.state["overrides"]
        settings = dict(self.subentry.data)
        level = overrides.get(CONF_WATER_NEED, settings.get(CONF_WATER_NEED, "medium"))
        mmin, mmax, _ = WATER_LEVELS.get(level, WATER_LEVELS["medium"])
        settings.setdefault(CONF_MOISTURE_MIN, mmin)
        settings.setdefault(CONF_MOISTURE_MAX, mmax)
        settings.update(overrides)
        if CONF_WATERING_INTERVAL not in settings:
            settings.update(
                {
                    k: v
                    for k, v in suggest_watering(settings).items()
                    if k not in settings
                }
            )
        return settings

    def sensor(self, key: str) -> str | None:
        """Return the entity id configured for a sensor role."""
        return self.subentry.data.get(key) or None

    @property
    def area_id(self) -> str | None:
        """Return the configured area id."""
        return self.subentry.data.get(CONF_AREA) or None

    @property
    def area_name(self) -> str | None:
        """Return the area name."""
        if (area_id := self.area_id) and (
            area := ar.async_get(self.hass).async_get_area(area_id)
        ):
            return area.name
        return None

    @property
    def winter_rest(self) -> bool:
        """Return whether winter rest is active."""
        return bool(self.state["winter_rest"])

    async def async_set_setting(self, key: str, value: Any) -> None:
        """Override a setting from an entity."""
        overrides = self.state["overrides"]
        overrides[key] = value
        if key == CONF_WATER_NEED:
            mmin, mmax, _ = WATER_LEVELS[value]
            overrides.update({CONF_MOISTURE_MIN: mmin, CONF_MOISTURE_MAX: mmax})
        if key in (
            CONF_WATER_NEED,
            CONF_LIGHT_NEED,
            CONF_LOCATION_LIGHT,
            CONF_PLANT_SIZE,
        ):
            # Re-run the care assistant for the new level/location
            overrides.update(suggest_watering(self.settings))
        self._changed()

    async def async_set_notifications(self, value: bool) -> None:
        """Mute or unmute notifications and announcements for this plant."""
        self.state["notify_enabled"] = value
        self._changed()

    async def async_set_winter_rest(self, value: bool) -> None:
        """Toggle winter rest."""
        self._advance(dt_util.utcnow())
        self.state["winter_rest"] = value
        self._changed()

    # ---------------------------------------------------------------- listeners
    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Listen for updates."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def _changed(self) -> None:
        """Re-evaluate, persist and notify listeners."""
        self.evaluate(dt_util.utcnow())
        self.hub.async_schedule_save()
        for update_callback in list(self._listeners):
            update_callback()
        self.hub.async_plant_updated()

    # ---------------------------------------------------------------- lifecycle
    @callback
    def async_start(self) -> None:
        """Subscribe to sensors and timers."""
        entities = [e for key in SENSOR_KEYS if (e := self.sensor(key))]
        if entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, entities, self._async_sensor_changed
                )
            )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_tick, TICK_INTERVAL)
        )
        now = dt_util.utcnow()
        if (lux := self._read(CONF_ILLUMINANCE_SENSOR)) is not None:
            self._last_lux = (now, lux)
        if (moisture := self._read(CONF_MOISTURE_SENSOR)) is not None:
            self._samples.append((now, moisture))
        self._advance(now)
        self._changed()

    @callback
    def async_stop(self) -> None:
        """Unsubscribe."""
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _async_tick(self, now: datetime) -> None:
        self._advance(dt_util.utcnow())
        self._changed()

    @callback
    def _async_sensor_changed(self, event: Event) -> None:
        now = dt_util.utcnow()
        entity_id = event.data["entity_id"]
        self._advance(now)
        if entity_id == self.sensor(CONF_MOISTURE_SENSOR):
            moisture = self._read(CONF_MOISTURE_SENSOR)
            if moisture is not None:
                self._samples.append((now, moisture))
                self._detect_watering(now, moisture)
        self._changed()

    # ------------------------------------------------------------------ actions
    async def async_mark_done(self, task: str) -> None:
        """Mark a care task as done now."""
        now = dt_util.utcnow()
        self._advance(now)
        if task == TASK_WATER:
            self._mark_watered(now)
        elif task == TASK_FERTILIZE:
            self.state["last_fertilized"] = _iso(now)
            self.state["fert_progress"] = 0.0
            self.state["fert_due_since"] = None
        self._changed()

    def _mark_watered(self, now: datetime) -> None:
        self.state["last_watered"] = _iso(now)
        self.state["water_progress"] = 0.0
        self.state["water_due_since"] = None
        self.state["moisture_dry"] = False
        self._samples.clear()

    def _detect_watering(self, now: datetime, moisture: float) -> None:
        """Mark as watered when soil moisture rises sharply."""
        window = [v for t, v in self._samples if now - t <= timedelta(hours=2)]
        if not window or moisture - min(window) < WATERING_DETECT_RISE:
            return
        last = _parse(self.state["last_watered"])
        if last and now - last < WATERED_GRACE:
            return
        _LOGGER.debug("%s: watering detected by soil sensor", self.name)
        self._mark_watered(now)
        self._samples.append((now, moisture))

    # -------------------------------------------------------------- calculation
    def _read(self, key: str) -> float | None:
        if not (entity_id := self.sensor(key)):
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _sensor_unavailable(self) -> bool:
        for key in SENSOR_KEYS:
            if (entity_id := self.sensor(key)) is None:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return True
        return False

    def climate_factor(self) -> float:
        """Return the current climate factor."""
        strength = self.hub.options.get(CONF_CLIMATE_STRENGTH, DEFAULT_CLIMATE_STRENGTH)
        return climate_factor(
            self._read(CONF_TEMPERATURE_SENSOR),
            self._read(CONF_HUMIDITY_SENSOR),
            float(strength),
        )

    def watering_interval_now(self) -> float:
        """Effective watering interval in days right now."""
        base = float(self.settings[CONF_WATERING_INTERVAL]) or 1.0
        season = WINTER_WATER_FACTOR if self.winter_rest else 1.0
        return max(base * season * self.climate_factor(), 0.25)

    def fertilizer_interval_now(self) -> float | None:
        """Effective fertilizing interval in days, None when paused/disabled."""
        settings = self.settings
        interval = float(settings.get(CONF_FERTILIZER_INTERVAL) or 0)
        if interval <= 0:
            return None
        if self.winter_rest:
            winter = float(settings.get(CONF_FERTILIZER_WINTER_INTERVAL) or 0)
            return winter if winter > 0 else None
        return interval

    def _advance(self, now: datetime) -> None:
        """Advance schedules and light integration up to `now`."""
        state = self.state
        last = _parse(state["progress_updated"]) or now
        days = max((now - last).total_seconds() / 86400, 0.0)
        if days > 0:
            state["water_progress"] += days / self.watering_interval_now()
            if (fert := self.fertilizer_interval_now()) is not None:
                state["fert_progress"] += days / fert
            state["progress_updated"] = _iso(now)

        # Light: roll over at local midnight, then integrate
        today = dt_util.as_local(now).date().isoformat()
        if state["dli_date"] != today:
            if state["dli_date"] is not None:
                history = state["dli_history"]
                history.append(round(state["dli_today"], 2))
                del history[:-DLI_HISTORY_DAYS]
            state["dli_date"] = today
            state["dli_today"] = 0.0
        if self.sensor(CONF_ILLUMINANCE_SENSOR):
            if self._last_lux is not None:
                t0, lux0 = self._last_lux
                seconds = (now - t0).total_seconds()
                if 0 < seconds < 6 * 3600:
                    state["dli_today"] += dli_increment(lux0, seconds)
            lux = self._read(CONF_ILLUMINANCE_SENSOR)
            self._last_lux = (now, lux) if lux is not None else None

    def _forecast_dry(
        self, now: datetime, moisture: float, limit: float
    ) -> datetime | None:
        last = _parse(self.state["last_watered"])
        samples = [
            (t, v)
            for t, v in self._samples
            if now - t <= SAMPLE_WINDOW and (last is None or t >= last)
        ]
        slope = moisture_slope_per_day(samples)
        if slope is None or slope > -0.1:
            return None
        days = min((moisture - limit) / -slope, 60.0)
        return now + timedelta(days=max(days, 0.0))

    def evaluate(self, now: datetime) -> Evaluation:
        """Compute the derived state."""
        settings = self.settings
        state = self.state
        ev = Evaluation()
        ev.moisture = self._read(CONF_MOISTURE_SENSOR)
        ev.illuminance = self._read(CONF_ILLUMINANCE_SENSOR)
        ev.temperature = self._read(CONF_TEMPERATURE_SENSOR)
        ev.humidity = self._read(CONF_HUMIDITY_SENSOR)
        ev.climate_factor = round(self.climate_factor(), 2)
        interval = self.watering_interval_now()
        ev.watering_interval_effective = round(interval, 2)
        problems: list[Problem] = []

        # ---- water
        mmin = float(settings[CONF_MOISTURE_MIN])
        mmax = float(settings[CONF_MOISTURE_MAX])
        last_watered = _parse(state["last_watered"])
        recently_watered = (
            last_watered is not None and now - last_watered < WATERED_GRACE
        )
        progress = state["water_progress"]
        if ev.moisture is not None:
            if ev.moisture < mmin:
                state["moisture_dry"] = True
            elif ev.moisture >= mmin + MOISTURE_HYSTERESIS:
                state["moisture_dry"] = False
            needs = state["moisture_dry"] and not recently_watered
        else:
            needs = progress >= 1.0
        if needs:
            if state["water_due_since"] is None:
                if ev.moisture is None:
                    since = now - timedelta(days=(progress - 1.0) * interval)
                else:
                    since = now
                state["water_due_since"] = _iso(since)
            due = _parse(state["water_due_since"]) or now
            ev.next_watering = due
            ev.water_overdue_days = max((now - due).total_seconds() / 86400, 0.0)
        else:
            state["water_due_since"] = None
            forecast = (
                self._forecast_dry(now, ev.moisture, mmin)
                if ev.moisture is not None
                else None
            )
            ev.next_watering = forecast or now + timedelta(
                days=max(1.0 - progress, 0.0) * interval
            )
        ev.needs_water = needs
        if needs:
            if ev.water_overdue_days > 0.5 * interval or (
                ev.moisture is not None and ev.moisture < mmin / 2
            ):
                sev = SEVERITY_CRITICAL
            elif ev.water_overdue_days > 1.0:
                sev = SEVERITY_WARNING
            else:
                sev = SEVERITY_INFO
            problems.append(Problem("needs_water", sev))
        if ev.moisture is not None and ev.moisture > mmax:
            problems.append(
                Problem(
                    "too_wet", SEVERITY_WARNING if ev.moisture >= 95 else SEVERITY_INFO
                )
            )

        # ---- fertilizer
        fert = self.fertilizer_interval_now()
        ev.fertilizing_enabled = float(settings.get(CONF_FERTILIZER_INTERVAL) or 0) > 0
        if fert is None:
            ev.needs_fertilizer = False
            state["fert_due_since"] = None
        else:
            fprog = state["fert_progress"]
            ev.needs_fertilizer = fprog >= 1.0
            if ev.needs_fertilizer:
                if state["fert_due_since"] is None:
                    state["fert_due_since"] = _iso(
                        now - timedelta(days=(fprog - 1.0) * fert)
                    )
                due = _parse(state["fert_due_since"]) or now
                ev.next_fertilizing = due
                ev.fertilizer_overdue_days = max(
                    (now - due).total_seconds() / 86400, 0.0
                )
                problems.append(
                    Problem(
                        "needs_fertilizer",
                        SEVERITY_WARNING
                        if ev.fertilizer_overdue_days > 7
                        else SEVERITY_INFO,
                    )
                )
            else:
                state["fert_due_since"] = None
                ev.next_fertilizing = now + timedelta(days=(1.0 - fprog) * fert)

        # ---- temperature
        if ev.temperature is not None:
            tmin = float(settings[CONF_TEMPERATURE_MIN])
            tmax = float(settings[CONF_TEMPERATURE_MAX])
            if ev.temperature < tmin:
                ev.temperature_problem = "too_cold"
                sev = (
                    SEVERITY_CRITICAL if ev.temperature < tmin - 3 else SEVERITY_WARNING
                )
                problems.append(Problem("too_cold", sev))
            elif ev.temperature > tmax:
                ev.temperature_problem = "too_hot"
                sev = (
                    SEVERITY_CRITICAL if ev.temperature > tmax + 5 else SEVERITY_WARNING
                )
                problems.append(Problem("too_hot", sev))

        # ---- light
        need = settings.get(CONF_LIGHT_NEED, "bright_indirect")
        history: list[float] = state["dli_history"]
        if self.sensor(CONF_ILLUMINANCE_SENSOR):
            ev.dli_today = round(state["dli_today"], 2)
            if history:
                ev.dli_yesterday = history[-1]
                ev.light_level = light_level_for_dli(history[-1])
            recent = history[-LIGHT_PROBLEM_DAYS:]
            if len(recent) == LIGHT_PROBLEM_DAYS:
                mismatches = {
                    light_mismatch(light_level_for_dli(d), need) for d in recent
                }
                if len(mismatches) == 1 and (mismatch := mismatches.pop()):
                    ev.light_problem = mismatch
                    problems.append(Problem(mismatch, SEVERITY_WARNING))
        elif location := settings.get(CONF_LOCATION_LIGHT):
            ev.light_level = location
            if mismatch := light_mismatch(location, need):
                ev.light_problem = mismatch
                problems.append(Problem(mismatch, SEVERITY_INFO))

        if self._sensor_unavailable():
            problems.append(Problem("sensor_unavailable", SEVERITY_INFO))

        ev.problems = problems
        ev.status = worst_severity(p.severity for p in problems)
        self.evaluation = ev
        self._notify_problems(problems)
        return ev

    def _notify_problems(self, problems: list[Problem]) -> None:
        """Fire an event for new or escalated problems."""
        notified: dict[str, str] = self.state["notified"]
        current = {p.key: p.severity for p in problems}
        notifier = self.hub.notifier
        for key in set(notified) - set(current):
            if notifier is not None:
                notifier.async_problem_resolved(self, key)
        for key, severity in current.items():
            previous = notified.get(key)
            if previous is None or SEVERITIES.index(severity) > SEVERITIES.index(
                previous
            ):
                if notifier is not None:
                    notifier.async_problem_changed(self, key, severity)
                self.hass.bus.async_fire(
                    EVENT_NOTIFICATION,
                    {
                        "plant": self.name,
                        "plant_id": self.id,
                        "device_id": self.device_id,
                        "area": self.area_name,
                        "problem": key,
                        "severity": severity,
                    },
                )
        self.state["notified"] = current


class ButlerHub:
    """All plants of a config entry plus persistence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the hub."""
        self.hass = hass
        self.entry = entry
        self.options = dict(entry.options)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.store_data: dict[str, Any] = {"plants": {}}
        self.plants: dict[str, PlantRuntime] = {}
        self._listeners: list[Callable[[], None]] = []
        self.notifier: Notifier | None = None

    async def async_load(self) -> None:
        """Load persisted data and create plant runtimes."""
        if (data := await self._store.async_load()) is not None:
            self.store_data = data
            self.store_data.setdefault("plants", {})
        subentries = {
            sid: sub
            for sid, sub in self.entry.subentries.items()
            if sub.subentry_type == "plant"
        }
        for stale in set(self.store_data["plants"]) - set(subentries):
            del self.store_data["plants"][stale]
        for sid, sub in subentries.items():
            self.plants[sid] = PlantRuntime(self.hass, self, sub)
        self.notifier = Notifier(self.hass, self)

    @callback
    def async_start(self) -> None:
        """Start all plants."""
        for plant in self.plants.values():
            plant.async_start()
        if self.notifier is not None:
            self.notifier.async_start()
        self.async_schedule_save()

    @callback
    def async_stop(self) -> None:
        """Stop all plants."""
        for plant in self.plants.values():
            plant.async_stop()
        if self.notifier is not None:
            self.notifier.async_stop()

    async def async_save_now(self) -> None:
        """Persist immediately."""
        await self._store.async_save(self.store_data)

    @callback
    def async_schedule_save(self) -> None:
        """Persist with a short delay."""
        self._store.async_delay_save(lambda: self.store_data, 5)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Listen for any plant update (used by the checklist)."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def async_plant_updated(self) -> None:
        """Notify hub listeners."""
        for update_callback in list(self._listeners):
            update_callback()

    async def async_remove_store(self) -> None:
        """Delete persisted data."""
        await self._store.async_remove()
