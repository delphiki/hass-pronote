"""Data update coordinator for the Pronote integration."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import logging
from .pronote_helper import *
from .pronote_formatter import *
import re
from zoneinfo import ZoneInfo
from slugify import slugify

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator


from .const import (
    LESSON_MAX_DAYS,
    LESSON_NEXT_DAY_SEARCH_LIMIT,
    HOMEWORK_MAX_DAYS,
    INFO_SURVEY_LIMIT_MAX_DAYS,
    EVENT_TYPE,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_ALARM_OFFSET,
)

_LOGGER = logging.getLogger(__name__)


def get_grades(period):
    try:
        grades = period.grades
        return sorted(grades, key=lambda grade: grade.date, reverse=True)
    except Exception as ex:
        _LOGGER.info("Error getting grades from period (%s): %s", period.name, ex)
        return None


def get_absences(period):
    try:
        absences = period.absences
        return sorted(absences, key=lambda absence: absence.from_date, reverse=True)
    except Exception as ex:
        _LOGGER.info("Error getting absences from period (%s): %s", period.name, ex)
        return None


def get_delays(period):
    try:
        delays = period.delays
        return sorted(delays, key=lambda delay: delay.date, reverse=True)
    except Exception as ex:
        _LOGGER.info("Error getting delays from period (%s): %s", period.name, ex)
        return None


def get_averages(period):
    try:
        averages = period.averages
        return averages
    except Exception as ex:
        _LOGGER.info("Error getting averages from period (%s): %s", period.name, ex)
        return None


def get_punishments(period):
    try:
        punishments = period.punishments
        return sorted(
            punishments,
            key=lambda punishment: punishment.given.strftime("%Y-%m-%d"),
            reverse=True,
        )
    except Exception as ex:
        _LOGGER.info("Error getting punishments from period (%s): %s", period.name, ex)
        return None


def get_evaluations(period):
    try:
        evaluations = period.evaluations
        evaluations = sorted(evaluations, key=lambda evaluation: (evaluation.name))
        return sorted(
            evaluations, key=lambda evaluation: (evaluation.date), reverse=True
        )
    except Exception as ex:
        _LOGGER.info("Error getting evaluations from period (%s): %s", period.name, ex)
        return None


def get_overall_average(period):
    try:
        return period.overall_average
    except Exception as ex:
        _LOGGER.info(
            "Error getting overall average from period (%s): %s", period.name, ex
        )
        return None


class PronoteDataUpdateCoordinator(TimestampDataUpdateCoordinator):
    """Data update coordinator for the Pronote integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.title,
            update_interval=timedelta(
                minutes=entry.options.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
            ),
        )
        self.config_entry = entry
        self._client = None

    async def _async_update_data(self) -> dict[Platform, dict[str, Any]]:
        """Get the latest data from Pronote and updates the state."""
        today = date.today()
        previous_data = None if self.data is None else self.data.copy()

        config_data = self.config_entry.data
        self.data = {
            "account_type": config_data["account_type"],
            "sensor_prefix": None,
            "child_info": None,
            "lessons_today": [],
            "lessons_tomorrow": [],
            "lessons_next_day": [],
            "lessons_period": [],
            "ical_url": None,
            "grades": [],
            "averages": [],
            "homework": [],
            "homework_period": [],
            "absences": [],
            "delays": [],
            "evaluations": [],
            "punishments": [],
            "menus": [],
            "information_and_surveys": [],
            "periods": [],
            "current_period": None,
            "previous_periods": [],
            "active_periods": [],
            "next_alarm": None,
            "overall_average": None,
        }

        client = await self.hass.async_add_executor_job(get_pronote_client, config_data)

        if client is None:
            _LOGGER.error("Unable to init pronote client")
            return None

        # should be moved to pronote_helper but won't work
        if config_data["connection_type"] == "qrcode":
            new_data = config_data.copy()
            new_data.update({"qr_code_password": client.password})
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

        child_info = client.info

        if config_data["account_type"] == "parent":
            client.set_child(config_data["child"])
            child_info = client._selected_child

        if child_info is None:
            return None

        self.data["child_info"] = child_info
        self.data["sensor_prefix"] = re.sub("[^A-Za-z]", "_", child_info.name.lower())

        # Lessons
        try:
            lessons_today = await self.hass.async_add_executor_job(
                client.lessons, today
            )
            self.data["lessons_today"] = sorted(
                lessons_today, key=lambda lesson: lesson.start
            )
        except Exception as ex:
            self.data["lessons_today"] = None
            _LOGGER.info("Error getting lessons_today from pronote: %s", ex)

        try:
            lessons_tomorrow = await self.hass.async_add_executor_job(
                client.lessons, today + timedelta(days=1)
            )
            self.data["lessons_tomorrow"] = sorted(
                lessons_tomorrow, key=lambda lesson: lesson.start
            )
        except Exception as ex:
            self.data["lessons_tomorrow"] = None
            _LOGGER.info("Error getting lessons_tomorrow from pronote: %s", ex)

        lessons_period = None
        delta = LESSON_MAX_DAYS
        while True and delta > 0:
            try:
                lessons_period = await self.hass.async_add_executor_job(
                    client.lessons, today, today + timedelta(days=delta)
                )
            except Exception as ex:
                _LOGGER.debug(
                    f"No lessons at: {delta} from today, searching best earlier alternative ({ex})"
                )
            if lessons_period:
                break
            delta = delta - 1
        _LOGGER.debug(
            f"Lessons found at: {delta} days, for a maximum of {LESSON_MAX_DAYS} from today"
        )
        self.data["lessons_period"] = (
            sorted(lessons_period, key=lambda lesson: lesson.start)
            if lessons_period is not None
            else None
        )

        if (
                self.data["lessons_tomorrow"] is not None
                and len(self.data["lessons_tomorrow"]) > 0
        ):
            self.data["lessons_next_day"] = self.data["lessons_tomorrow"]
        else:
            try:
                delta = 2
                while True and delta < LESSON_NEXT_DAY_SEARCH_LIMIT:
                    lessons_nextday = await self.hass.async_add_executor_job(
                        client.lessons, today + timedelta(days=delta)
                    )
                    if lessons_nextday:
                        break
                    else:
                        lessons_nextday = None
                        del lessons_nextday
                    delta = delta + 1
                self.data["lessons_next_day"] = sorted(
                    lessons_nextday, key=lambda lesson: lesson.start
                )
                lessons_nextday = None
                del lessons_nextday
            except Exception as ex:
                self.data["lessons_next_day"] = None
                _LOGGER.info("Error getting lessons_next_day from pronote: %s", ex)

        next_alarm = None
        tz = ZoneInfo(self.hass.config.time_zone)
        today_start_at = get_day_start_at(self.data["lessons_today"])
        next_day_start_at = get_day_start_at(self.data["lessons_next_day"])
        if today_start_at or next_day_start_at:
            alarm_offset = self.config_entry.options.get(
                "alarm_offset", DEFAULT_ALARM_OFFSET
            )
            if today_start_at is not None:
                todays_alarm = today_start_at - timedelta(minutes=alarm_offset)
                if datetime.now() <= todays_alarm:
                    next_alarm = todays_alarm
            if next_alarm is None and next_day_start_at is not None:
                next_alarm = next_day_start_at - timedelta(minutes=alarm_offset)
        if next_alarm is not None:
            next_alarm = next_alarm.replace(tzinfo=tz)

        self.data["next_alarm"] = next_alarm

        # Grades
        self.data["grades"] = await self.hass.async_add_executor_job(
            get_grades, client.current_period
        )
        self.compare_data(
            previous_data,
            "grades",
            ["date", "subject", "grade_out_of"],
            "new_grade",
            format_grade,
        )

        # Averages
        self.data["averages"] = await self.hass.async_add_executor_job(
            get_averages, client.current_period
        )

        # Homework
        try:
            homework = await self.hass.async_add_executor_job(client.homework, today)
            self.data["homework"] = sorted(homework, key=lambda lesson: lesson.date)
        except Exception as ex:
            self.data["homework"] = None
            _LOGGER.info("Error getting homework from pronote: %s", ex)

        try:
            homework_period = await self.hass.async_add_executor_job(
                client.homework, today, today + timedelta(days=HOMEWORK_MAX_DAYS)
            )
            self.data["homework_period"] = sorted(
                homework_period, key=lambda homework: homework.date
            )
        except Exception as ex:
            self.data["homework_period"] = None
            _LOGGER.info("Error getting homework_period from pronote: %s", ex)

        # Information and Surveys
        try:
            information_and_surveys = await self.hass.async_add_executor_job(
                client.information_and_surveys,
                today - timedelta(days=INFO_SURVEY_LIMIT_MAX_DAYS),
                )
            self.data["information_and_surveys"] = sorted(
                information_and_surveys,
                key=lambda information_and_survey: information_and_survey.creation_date,
                reverse=True,
            )
        except Exception as ex:
            self.data["information_and_surveys"] = None
            _LOGGER.info("Error getting information_and_surveys from pronote: %s", ex)

        # Absences
        self.data["absences"] = await self.hass.async_add_executor_job(
            get_absences, client.current_period
        )
        self.compare_data(
            previous_data, "absences", ["from", "to"], "new_absence", format_absence
        )

        # Delays
        self.data["delays"] = await self.hass.async_add_executor_job(
            get_delays, client.current_period
        )
        self.compare_data(
            previous_data, "delays", ["date", "minutes"], "new_delay", format_delay
        )

        # Evaluations
        self.data["evaluations"] = await self.hass.async_add_executor_job(
            get_evaluations, client.current_period
        )

        # Punishments
        self.data["punishments"] = await self.hass.async_add_executor_job(
            get_punishments, client.current_period
        )

        # iCal
        try:
            self.data["ical_url"] = await self.hass.async_add_executor_job(
                client.export_ical
            )
        except Exception as ex:
            _LOGGER.info("Error getting ical_url from pronote: %s", ex)

        # Menus
        try:
            self.data["menus"] = await self.hass.async_add_executor_job(
                client.menus, today, today + timedelta(days=7)
            )
        except Exception as ex:
            self.data["menus"] = None
            _LOGGER.info("Error getting menus from pronote: %s", ex)

        # Overall average
        self.data["overall_average"] = await self.hass.async_add_executor_job(
            get_overall_average, client.current_period
        )

        # Periods
        try:
            self.data["periods"] = client.periods
        except Exception as ex:
            self.data["periods"] = None
            _LOGGER.info("Error getting periods from pronote: %s", ex)
        try:
            self.data["current_period"] = client.current_period
            self.data["current_period_key"] = client.current_period_key = slugify(
                client.current_period.name, separator="_"
            )
        except Exception as ex:
            self.data["current_period"] = None
            _LOGGER.info("Error getting current period from pronote: %s", ex)

        # determine previous periods (handle only trimestres and semestres)
        supported_period_types = ["trimestre", "semestre"]
        period_type = None
        if self.data["current_period"] is not None:
            period_type = self.data["current_period"].name.split(" ")[0].lower()

        if period_type in supported_period_types:
            for period in self.data["periods"]:
                if (
                        period.name.lower().startswith(period_type)
                        and period.start < self.data["current_period"].start
                ):
                    self.data["previous_periods"].append(period)
                    period_key = slugify(period.name, separator="_")

                    self.data[
                        f"grades_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_grades, period)
                    self.data[
                        f"averages_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_averages, period)
                    self.data[
                        f"absences_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_absences, period)
                    self.data[
                        f"delays_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_delays, period)
                    self.data[
                        f"evaluations_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_evaluations, period)
                    self.data[
                        f"punishments_{period_key}"
                    ] = await self.hass.async_add_executor_job(get_punishments, period)
                    self.data[
                        f"overall_average_{period_key}"
                    ] = await self.hass.async_add_executor_job(
                        get_overall_average, period
                    )

        self.data["active_periods"] = self.data["previous_periods"] + [
            self.data["current_period"]
        ]

        return self.data

    def compare_data(
            self, previous_data, data_key, compare_keys, event_type, format_func
    ):
        if (
                previous_data is not None
                and previous_data[data_key] is not None
                and self.data[data_key] is not None
        ):
            not_found_items = []
            for item in self.data[data_key]:
                found = False
                for previous_item in previous_data[data_key]:
                    if {
                        key: format_func(previous_item)[key] for key in compare_keys
                    } == {key: format_func(item)[key] for key in compare_keys}:
                        found = True
                        break
                if found is False:
                    not_found_items.append(item)
            for not_found_item in not_found_items:
                self.trigger_event(event_type, format_func(not_found_item))

    def trigger_event(self, event_type, event_data):
        event_data = {
            "child_name": self.data["child_info"].name,
            "child_nickname": self.config_entry.options.get("nickname"),
            "child_slug": self.data["sensor_prefix"],
            "type": event_type,
            "data": event_data,
        }
        self.hass.bus.async_fire(EVENT_TYPE, event_data)
