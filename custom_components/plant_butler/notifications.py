"""Phone notifications and spoken announcements for Plant Butler."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ACTION_PREFIX,
    CONF_FERTILIZER_AMOUNT,
    CONF_FERTILIZER_UNIT,
    CONF_TEMPERATURE_MAX,
    CONF_TEMPERATURE_MIN,
    DEFAULT_ANNOUNCE_OPTIONS,
    DEFAULT_PHONE_OPTIONS,
    DOMAIN,
    FEEDBACK_ANSWERS,
    MODE_IMMEDIATE,
    MODE_OFF,
    OPT_ANNOUNCE,
    OPT_PHONE,
    PROBLEM_TOPIC,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    TASK_FERTILIZE,
    TASK_WATER,
)
from .texts import fmt_number, messages

if TYPE_CHECKING:
    from .plant import ButlerHub, PlantRuntime

_LOGGER = logging.getLogger(__name__)

PROCESS_INTERVAL = timedelta(minutes=1)
SUMMARY_KEY = "__summary__"
UNIT_LABELS = {"ml_per_l": "ml/l", "ml": "ml", "sticks": "Stk.", "g": "g"}
DND_OFF_STATES = {"off", STATE_UNAVAILABLE, STATE_UNKNOWN, ""}


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return dt_util.parse_time(value)


def in_window(now: datetime, start: str | None, end: str | None) -> bool:
    """Whether the local time of `now` lies in [start, end) (may wrap midnight)."""
    t_start, t_end = _parse_time(start), _parse_time(end)
    if t_start is None or t_end is None or t_start == t_end:
        return False
    current = dt_util.as_local(now).time()
    if t_start < t_end:
        return t_start <= current < t_end
    return current >= t_start or current < t_end


class Notifier:
    """Sends phone notifications and announcements based on plant problems."""

    def __init__(self, hass: HomeAssistant, hub: ButlerHub) -> None:
        """Initialize from the hub options."""
        self.hass = hass
        self.hub = hub
        self.phone: dict[str, Any] = {
            **DEFAULT_PHONE_OPTIONS,
            **hub.options.get(OPT_PHONE, {}),
        }
        self.announce: dict[str, Any] = {
            **DEFAULT_ANNOUNCE_OPTIONS,
            **hub.options.get(OPT_ANNOUNCE, {}),
        }
        self.data: dict[str, dict[str, Any]] = hub.store_data.setdefault("notify", {})
        for key in ("sent", "pending", "snooze"):
            self.data.setdefault(key, {})
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ setup
    @property
    def _lang(self) -> str:
        return self.hass.config.language

    @callback
    def async_start(self) -> None:
        """Start timers and listeners."""
        for opts, job in (
            (self.phone, self._async_phone_summary),
            (self.announce, self._async_announce_summary),
        ):
            if (summary := _parse_time(opts.get("summary_time"))) is not None:
                self._unsubs.append(
                    async_track_time_change(
                        self.hass,
                        job,
                        hour=summary.hour,
                        minute=summary.minute,
                        second=0,
                    )
                )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_process, PROCESS_INTERVAL)
        )
        self._unsubs.append(
            self.hass.bus.async_listen(
                "mobile_app_notification_action", self._async_on_action
            )
        )
        if dnd := [e for dev in self.phone["devices"] if (e := self._dnd_entity(dev))]:
            self._unsubs.append(
                async_track_state_change_event(self.hass, dnd, self._async_dnd_changed)
            )

    @callback
    def async_stop(self) -> None:
        """Stop timers and listeners."""
        while self._unsubs:
            self._unsubs.pop()()

    # ------------------------------------------------------------ plant hooks
    @callback
    def async_problem_changed(
        self, plant: PlantRuntime, key: str, severity: str
    ) -> None:
        """A problem appeared or became more severe."""
        if severity == SEVERITY_CRITICAL:
            self.data["snooze"].pop(f"{plant.id}|{key}", None)
        if not self._enabled(plant):
            return
        topic = PROBLEM_TOPIC.get(key)
        snoozed = f"{plant.id}|{key}" in self.data["snooze"]
        if (
            topic in self.phone["topics"]
            and self.phone.get(severity) == MODE_IMMEDIATE
            and not snoozed
        ):
            self._phone_deliver(plant, key, severity)
        if (
            topic in self.announce["topics"]
            and self.announce.get(severity) == MODE_IMMEDIATE
        ):
            self._announce_deliver(plant, key, severity)
        self.hub.async_schedule_save()

    @callback
    def async_problem_resolved(self, plant: PlantRuntime, key: str) -> None:
        """A problem is gone: forget it and remove it from the phones."""
        prefix = f"{plant.id}|{key}|"
        sent_devices = [
            k.split("|")[3]
            for k in self.data["sent"]
            if k.startswith(prefix + "phone|")
        ]
        for bucket in ("sent", "pending"):
            for k in [k for k in self.data[bucket] if k.startswith(prefix)]:
                del self.data[bucket][k]
        self.data["snooze"].pop(f"{plant.id}|{key}", None)
        services = self._phone_services()
        for device_id in sent_devices:
            if service := services.get(device_id):
                self._call_notify(
                    service,
                    {
                        "message": "clear_notification",
                        "data": {"tag": self._tag(plant, key)},
                    },
                )
        self.hub.async_schedule_save()

    # ---------------------------------------------------------------- helpers
    def _enabled(self, plant: PlantRuntime) -> bool:
        return bool(plant.state.get("notify_enabled", True))

    def _plant(self, plant_id: str) -> PlantRuntime | None:
        return self.hub.plants.get(plant_id)

    def _active(self) -> dict[tuple[str, str], str]:
        return {
            (plant.id, problem.key): problem.severity
            for plant in self.hub.plants.values()
            for problem in plant.evaluation.problems
        }

    @staticmethod
    def _tag(plant: PlantRuntime, key: str) -> str:
        return f"{DOMAIN}_{plant.id}_{key}"

    def _status_entity(self, plant: PlantRuntime) -> str | None:
        return er.async_get(self.hass).async_get_entity_id(
            "sensor", DOMAIN, f"{plant.id}_status"
        )

    def _room(self, plant: PlantRuntime) -> str:
        return plant.area_name or messages(self._lang)["no_room"]

    # ------------------------------------------------------------------ texts
    def _amount_text(self, plant: PlantRuntime, task: str) -> str | None:
        settings = plant.settings
        lang = self._lang
        if task == TASK_WATER:
            amount = plant.watering_amount_effective()
            return f"{fmt_number(float(amount), lang)} ml" if amount else None
        amount = settings.get(CONF_FERTILIZER_AMOUNT)
        if not amount:
            return None
        unit = UNIT_LABELS.get(settings.get(CONF_FERTILIZER_UNIT) or "ml_per_l", "")
        return f"{fmt_number(float(amount), lang)} {unit}".strip()

    def problem_text(self, plant: PlantRuntime, key: str) -> str:
        """One-line text of a problem for phone notifications."""
        msg = messages(self._lang)
        ev = plant.evaluation
        settings = plant.settings
        lang = self._lang
        if key == "needs_water":
            days = int(ev.water_overdue_days)
            if days >= 2:
                text = msg["water_overdue"].format(days=days)
            elif days == 1:
                text = msg["water_overdue_1"]
            else:
                text = msg["water_due"]
            if amount := self._amount_text(plant, TASK_WATER):
                text += f" – {amount}"
            return text
        if key == "needs_fertilizer":
            text = msg["fertilize_due"]
            if amount := self._amount_text(plant, TASK_FERTILIZE):
                text += f" – {amount}"
            return text
        if key == "too_wet" and ev.moisture is not None:
            return msg["too_wet"].format(value=fmt_number(ev.moisture, lang))
        if key in ("too_cold", "too_hot") and ev.temperature is not None:
            limit = settings.get(
                CONF_TEMPERATURE_MIN if key == "too_cold" else CONF_TEMPERATURE_MAX
            )
            return msg[key].format(
                value=fmt_number(ev.temperature, lang),
                limit=fmt_number(float(limit), lang),
            )
        return msg.get(key, key).split(" (")[0].split(":")[0]

    def spoken_text(self, plant: PlantRuntime, key: str) -> str:
        """One sentence for an announcement."""
        msg = messages(self._lang)
        ev = plant.evaluation
        lang = self._lang
        room = self._room(plant)
        fields: dict[str, Any] = {"plant": plant.name, "room": room}
        if key == "needs_water":
            amount = plant.watering_amount_effective()
            fields["amount"] = (
                msg["say_amount"].format(value=fmt_number(float(amount), lang))
                if amount
                else ""
            )
            days = int(ev.water_overdue_days)
            if days >= 2:
                return msg["say_water_overdue"].format(days=days, **fields)
            return msg["say_water"].format(**fields)
        if key == "needs_fertilizer":
            return msg["say_fertilize"].format(**fields)
        if key in ("too_cold", "too_hot"):
            value = (
                fmt_number(ev.temperature, lang) if ev.temperature is not None else "?"
            )
            return msg[f"say_{key}"].format(value=value, **fields)
        template = msg.get(f"say_{key}")
        return template.format(**fields) if template else f"{plant.name}: {key}"

    def summary_lines(self, items: Iterable[tuple[PlantRuntime, str]]) -> list[str]:
        """Group summary items by room: 'Room: task, task'."""
        msg = messages(self._lang)
        rooms: dict[str, list[str]] = {}
        for plant, key in items:
            if key == "needs_water":
                text = msg["task_water"].format(plant=plant.name)
                amount = self._amount_text(plant, TASK_WATER)
            elif key == "needs_fertilizer":
                text = msg["task_fertilize"].format(plant=plant.name)
                amount = self._amount_text(plant, TASK_FERTILIZE)
            else:
                text = f"{plant.name}: {self.problem_text(plant, key)}"
                amount = None
            if amount:
                text += f" ({amount})"
            rooms.setdefault(self._room(plant), []).append(text)
        return [f"{room}: {', '.join(tasks)}" for room, tasks in sorted(rooms.items())]

    def _summary_items(self, opts: dict[str, Any]) -> list[tuple[PlantRuntime, str]]:
        items = []
        for plant in sorted(self.hub.plants.values(), key=lambda p: p.name):
            if not self._enabled(plant):
                continue
            for problem in plant.evaluation.problems:
                if PROBLEM_TOPIC.get(problem.key) not in opts["topics"]:
                    continue
                if opts.get(problem.severity, MODE_OFF) == MODE_OFF:
                    continue
                items.append((plant, problem.key))
        return items

    # ------------------------------------------------------------------ phone
    def _phone_services(self) -> dict[str, str]:
        """Map selected device ids to their notify.mobile_app_* service."""
        dev_reg = dr.async_get(self.hass)
        services: dict[str, str] = {}
        for device_id in self.phone["devices"]:
            if (device := dev_reg.async_get(device_id)) is None:
                continue
            for name in (device.name, device.name_by_user):
                if name and self.hass.services.has_service(
                    "notify", f"mobile_app_{slugify(name)}"
                ):
                    services[device_id] = f"mobile_app_{slugify(name)}"
                    break
            else:
                _LOGGER.warning("No notify service found for phone %s", device.name)
        return services

    def _dnd_entity(self, device_id: str) -> str | None:
        """The Companion app 'Do Not Disturb' sensor of a phone, if enabled."""
        for entry in er.async_entries_for_device(er.async_get(self.hass), device_id):
            if entry.domain == "sensor" and (
                entry.entity_id.endswith("do_not_disturb_sensor")
                or entry.unique_id.endswith("dnd_sensor")
            ):
                return entry.entity_id
        return None

    def _dnd_active(self, device_id: str) -> bool:
        if not (entity_id := self._dnd_entity(device_id)):
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in DND_OFF_STATES

    def _phone_blocked(self, device_id: str, severity: str, now: datetime) -> bool:
        if severity == SEVERITY_CRITICAL:
            return False
        if in_window(now, self.phone.get("quiet_start"), self.phone.get("quiet_end")):
            return True
        return bool(self.phone.get("respect_dnd")) and self._dnd_active(device_id)

    def _phone_deliver(
        self,
        plant: PlantRuntime,
        key: str,
        severity: str,
        devices: Iterable[str] | None = None,
    ) -> None:
        now = dt_util.utcnow()
        services = self._phone_services()
        for device_id, service in services.items():
            if devices is not None and device_id not in devices:
                continue
            slot = f"{plant.id}|{key}|phone|{device_id}"
            if self._phone_blocked(device_id, severity, now):
                self.data["pending"][slot] = severity
                continue
            self._send_phone(service, plant, key, severity)
            self.data["sent"][slot] = now.isoformat()
            self.data["pending"].pop(slot, None)

    def _call_notify(self, service: str, payload: dict[str, Any]) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call("notify", service, payload, blocking=False)
        )

    def _send_phone(
        self, service: str, plant: PlantRuntime, key: str, severity: str
    ) -> None:
        msg = messages(self._lang)
        title = f"{plant.name} ({plant.area_name})" if plant.area_name else plant.name
        critical = severity == SEVERITY_CRITICAL
        loud = critical and bool(self.phone.get("critical_breaks_dnd"))
        data: dict[str, Any] = {
            "tag": self._tag(plant, key),
            "group": DOMAIN,
            "channel": "alarm_stream"
            if loud
            else ("Plant Butler critical" if critical else "Plant Butler"),
            "importance": "high" if severity != SEVERITY_INFO else "default",
            "priority": "high" if severity != SEVERITY_INFO else "normal",
            "ttl": 0,
            "push": {
                "interruption-level": "critical"
                if loud
                else ("time-sensitive" if critical else "active")
            },
        }
        if status := self._status_entity(plant):
            data["clickAction"] = f"entityId:{status}"
        if self.phone.get("buttons"):
            actions = []
            if key == "needs_water":
                actions.append(
                    {
                        "action": f"{ACTION_PREFIX}|DONE|{plant.id}|{TASK_WATER}",
                        "title": msg["btn_watered"],
                    }
                )
            elif key == "needs_fertilizer":
                actions.append(
                    {
                        "action": f"{ACTION_PREFIX}|DONE|{plant.id}|{TASK_FERTILIZE}",
                        "title": msg["btn_fertilized"],
                    }
                )
            actions.append(
                {
                    "action": f"{ACTION_PREFIX}|SNOOZE|{plant.id}|{key}|1",
                    "title": msg["btn_1h"],
                }
            )
            actions.append(
                {
                    "action": f"{ACTION_PREFIX}|SNOOZE|{plant.id}|{key}|24",
                    "title": msg["btn_tomorrow"],
                }
            )
            data["actions"] = actions
        self._call_notify(
            service,
            {"title": title, "message": self.problem_text(plant, key), "data": data},
        )

    async def _async_phone_summary(self, now: datetime | None = None) -> None:
        items = self._summary_items(self.phone)
        services = self._phone_services()
        if not items or not services:
            return
        for device_id, service in services.items():
            slot = f"{SUMMARY_KEY}|summary|phone|{device_id}"
            if self.phone.get("respect_dnd") and self._dnd_active(device_id):
                self.data["pending"][slot] = SEVERITY_INFO
                continue
            self._send_phone_summary(service, items)
            self.data["pending"].pop(slot, None)
        self.hub.async_schedule_save()

    def _send_phone_summary(
        self, service: str, items: list[tuple[PlantRuntime, str]]
    ) -> None:
        msg = messages(self._lang)
        self._call_notify(
            service,
            {
                "title": msg["summary_title"],
                "message": "\n".join(self.summary_lines(items)),
                "data": {
                    "tag": f"{DOMAIN}_summary",
                    "group": DOMAIN,
                    "channel": "Plant Butler",
                },
            },
        )

    # --------------------------------------------------------------- announce
    def _announce_blocked(self, severity: str, now: datetime) -> bool:
        if not in_window(
            now, self.announce.get("quiet_start"), self.announce.get("quiet_end")
        ):
            return False
        return not (
            severity == SEVERITY_CRITICAL and self.announce.get("critical_in_quiet")
        )

    def _area_of(self, entity_id: str) -> str | None:
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return None
        if entry.area_id:
            return entry.area_id
        if entry.device_id and (
            device := dr.async_get(self.hass).async_get(entry.device_id)
        ):
            return device.area_id
        return None

    def _targets(self, area_id: str | None) -> tuple[list[str], list[str]]:
        satellites = list(self.announce["satellites"])
        speakers = list(self.announce["speakers"])
        if self.announce["where"] == "room" and area_id:
            room_sat = [e for e in satellites if self._area_of(e) == area_id]
            room_spk = [e for e in speakers if self._area_of(e) == area_id]
            if room_sat or room_spk:
                return room_sat, room_spk
        return satellites, speakers

    def _announce_deliver(self, plant: PlantRuntime, key: str, severity: str) -> None:
        if not (self.announce["satellites"] or self.announce["speakers"]):
            return
        now = dt_util.utcnow()
        slot = f"{plant.id}|{key}|announce|all"
        if self._announce_blocked(severity, now):
            self.data["pending"][slot] = severity
            return
        text = self.spoken_text(plant, key)
        if severity == SEVERITY_CRITICAL:
            text = f"{messages(self._lang)['say_attention']} {text}"
        self._speak(text, plant.area_id)
        self.data["sent"][slot] = now.isoformat()
        self.data["pending"].pop(slot, None)

    async def _async_announce_summary(self, now: datetime | None = None) -> None:
        items = self._summary_items(self.announce)
        if not items or not (self.announce["satellites"] or self.announce["speakers"]):
            return
        intro = messages(self._lang)["say_intro"]
        by_area: dict[str | None, list[str]] = {}
        for plant, key in items:
            area = plant.area_id if self.announce["where"] == "room" else None
            by_area.setdefault(area, []).append(self.spoken_text(plant, key))
        for area, sentences in by_area.items():
            self._speak(" ".join([intro, *sentences]), area)

    def _speak(self, text: str, area_id: str | None) -> None:
        satellites, speakers = self._targets(area_id)
        if satellites:
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "assist_satellite",
                    "announce",
                    {"message": text},
                    target={"entity_id": satellites},
                    blocking=False,
                )
            )
        if not speakers:
            return
        engine = self.announce.get("tts_engine") or next(
            iter(sorted(self.hass.states.async_entity_ids("tts"))), None
        )
        if engine is None:
            _LOGGER.warning("No text-to-speech engine available for announcements")
            return
        media_id = f"media-source://tts/{engine}?message={quote(text)}"
        volume = self.announce.get("volume")
        for speaker in speakers:
            state = self.hass.states.get(speaker)
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) if state else 0
            if features & MediaPlayerEntityFeature.MEDIA_ANNOUNCE:
                # Music Assistant and other players with native announcements
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "media_player",
                        "play_media",
                        {
                            "media_content_id": media_id,
                            "media_content_type": "music",
                            "announce": True,
                        },
                        target={"entity_id": speaker},
                        blocking=False,
                    )
                )
                continue
            if volume is not None and state is not None:
                self._set_volume_temporarily(
                    speaker, state.attributes.get("volume_level"), float(volume), text
                )
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "tts",
                    "speak",
                    {"media_player_entity_id": speaker, "message": text},
                    target={"entity_id": engine},
                    blocking=False,
                )
            )

    def _set_volume_temporarily(
        self, speaker: str, previous: float | None, volume_pct: float, text: str
    ) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call(
                "media_player",
                "volume_set",
                {"volume_level": volume_pct / 100},
                target={"entity_id": speaker},
                blocking=False,
            )
        )
        if previous is None:
            return

        @callback
        def _restore(_now: datetime) -> None:
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"volume_level": previous},
                    target={"entity_id": speaker},
                    blocking=False,
                )
            )

        self._unsubs.append(async_call_later(self.hass, 4 + len(text) / 12, _restore))

    # ---------------------------------------------------------------- process
    @callback
    def _async_dnd_changed(self, event: Event) -> None:
        self.hass.async_create_task(self._async_process())

    async def _async_process(self, now: datetime | None = None) -> None:
        """Send held messages, expired snoozes and critical repeats."""
        now = dt_util.utcnow()
        active = self._active()
        services = self._phone_services()
        changed = False

        for slot in list(self.data["pending"]):
            plant_id, key, channel, target = slot.split("|")
            if plant_id == SUMMARY_KEY:
                if (
                    channel == "phone"
                    and target in services
                    and not self._dnd_active(target)
                ):
                    if items := self._summary_items(self.phone):
                        self._send_phone_summary(services[target], items)
                    del self.data["pending"][slot]
                    changed = True
                continue
            plant = self._plant(plant_id)
            current = active.get((plant_id, key))
            if plant is None or current is None:
                del self.data["pending"][slot]
                changed = True
                continue
            if channel == "phone":
                if target in services and not self._phone_blocked(target, current, now):
                    self._send_phone(services[target], plant, key, current)
                    self.data["sent"][slot] = now.isoformat()
                    del self.data["pending"][slot]
                    changed = True
            elif not self._announce_blocked(current, now):
                del self.data["pending"][slot]
                self._announce_deliver(plant, key, current)
                changed = True

        for snooze_key, until in list(self.data["snooze"].items()):
            if now < (dt_util.parse_datetime(until) or now):
                continue
            del self.data["snooze"][snooze_key]
            changed = True
            plant_id, key = snooze_key.split("|")
            if (plant := self._plant(plant_id)) and (
                current := active.get((plant_id, key))
            ):
                if self._enabled(plant):
                    self._phone_deliver(plant, key, current)

        repeat = float(self.phone.get("critical_repeat_hours") or 0)
        if repeat > 0 and self.phone.get("critical") == MODE_IMMEDIATE:
            for (plant_id, key), severity in active.items():
                if (
                    severity != SEVERITY_CRITICAL
                    or f"{plant_id}|{key}" in self.data["snooze"]
                ):
                    continue
                plant = self._plant(plant_id)
                if plant is None or not self._enabled(plant):
                    continue
                if PROBLEM_TOPIC.get(key) not in self.phone["topics"]:
                    continue
                for device_id, service in services.items():
                    slot = f"{plant_id}|{key}|phone|{device_id}"
                    last = dt_util.parse_datetime(self.data["sent"].get(slot) or "")
                    if last is not None and now - last >= timedelta(hours=repeat):
                        self._send_phone(service, plant, key, severity)
                        self.data["sent"][slot] = now.isoformat()
                        changed = True
        if changed:
            self.hub.async_schedule_save()

    # ---------------------------------------------------------------- actions
    async def _async_on_action(self, event: Event) -> None:
        parts = str(event.data.get("action", "")).split("|")
        if len(parts) < 4 or parts[0] != ACTION_PREFIX:
            return
        plant = self._plant(parts[2])
        if plant is None:
            return
        if parts[1] == "DONE" and parts[3] in (TASK_WATER, TASK_FERTILIZE):
            await plant.async_mark_done(parts[3], source="phone")
            if parts[3] == TASK_WATER:
                self._ask_feedback(plant, event.data.get("device_id"))
        elif parts[1] == "FEEDBACK" and parts[3] in FEEDBACK_ANSWERS:
            await plant.async_feedback(parts[3])
            self.async_clear_feedback(plant)
        elif parts[1] == "SNOOZE" and len(parts) == 5:
            until = dt_util.utcnow() + timedelta(hours=float(parts[4]))
            self.data["snooze"][f"{plant.id}|{parts[3]}"] = until.isoformat()
            self.hub.async_schedule_save()

    # --------------------------------------------------------------- learning
    def _feedback_tag(self, plant: PlantRuntime) -> str:
        return f"{DOMAIN}_{plant.id}_feedback"

    def _ask_feedback(self, plant: PlantRuntime, device_id: str | None = None) -> None:
        """After 'Watered' on the phone: how was the soil? (undo via tap)."""
        if not plant.learning_collects:
            return
        msg = messages(self._lang)
        data: dict[str, Any] = {
            "tag": self._feedback_tag(plant),
            "group": DOMAIN,
            "channel": "Plant Butler",
            "actions": [
                {
                    "action": f"{ACTION_PREFIX}|FEEDBACK|{plant.id}|{answer}",
                    "title": msg[f"btn_{answer}"],
                }
                for answer in FEEDBACK_ANSWERS
            ],
        }
        undo = er.async_get(self.hass).async_get_entity_id(
            "button", DOMAIN, f"{plant.id}_undo_watering"
        )
        if undo:
            data["clickAction"] = f"entityId:{undo}"
        services = self._phone_services()
        targets = [s for d, s in services.items() if device_id in (None, d)] or list(
            services.values()
        )
        for service in targets:
            self._call_notify(
                service,
                {
                    "title": plant.name,
                    "message": msg["feedback_question"],
                    "data": data,
                },
            )

    @callback
    def async_clear_feedback(self, plant: PlantRuntime) -> None:
        """Remove an open feedback question from the phones."""
        for service in self._phone_services().values():
            self._call_notify(
                service,
                {
                    "message": "clear_notification",
                    "data": {"tag": self._feedback_tag(plant)},
                },
            )

    @callback
    def async_learning_info(
        self, plant: PlantRuntime, old_days: int, new_days: int
    ) -> None:
        """Tell the user that the watering rhythm changed."""
        msg = messages(self._lang)
        now = dt_util.utcnow()
        for device_id, service in self._phone_services().items():
            if self._phone_blocked(device_id, SEVERITY_INFO, now):
                continue
            self._call_notify(
                service,
                {
                    "title": plant.name,
                    "message": msg["learning_info"].format(new=new_days, old=old_days),
                    "data": {
                        "tag": f"{DOMAIN}_{plant.id}_learning",
                        "group": DOMAIN,
                        "channel": "Plant Butler",
                    },
                },
            )
