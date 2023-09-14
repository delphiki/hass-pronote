"""Data update coordinator for the Pronote integration."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import logging
import pronotepy
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


from .const import (
    LESSON_MAX_DAYS,
    HOMEWORK_MAX_DAYS,
)

_LOGGER = logging.getLogger(__name__)


def get_pronote_client(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    url = data['url'] + ('parent' if data['account_type'] ==
                         'parent' else 'eleve') + '.html'

    ent = None
    if 'ent' in data:
        ent = getattr(pronotepy.ent, data['ent'])

    if not ent:
        url += '?login=true'

    try:
        client = (pronotepy.ParentClient if data['account_type'] ==
                  'parent' else pronotepy.Client)(url, data['username'], data['password'], ent)
        _LOGGER.info(f"Client name: {client.info.name}")
    except Exception as err:
        _LOGGER.debug(err)
        return None

    return client


def get_grades(client):
    try:
        grades = client.current_period.grades
    except Exception as err:
        _LOGGER.debug(err)
        grades = []
    return sorted(grades, key=lambda grade: grade.date, reverse=True)


def get_absences(client):
    try:
        absences = client.current_period.absences
    except Exception as err:
        _LOGGER.debug(err)
        absences = []
    return sorted(absences, key=lambda absence: absence.from_date, reverse=True)


def get_averages(client):
    try:
        averages = client.current_period.averages
    except Exception as err:
        _LOGGER.debug(err)
        averages = []
    return averages


def get_punishments(client):
    try:
        punishments = client.current_period.punishments
    except Exception as err:
        _LOGGER.debug(err)
        punishments = []
    return sorted(punishments, key=lambda punishment: punishment.given.strftime("%Y-%m-%d"), reverse=True)


def get_evaluations(client):
    try:
        evaluations = client.current_period.evaluations
    except Exception as err:
        _LOGGER.debug(err)
        evaluations = []
    evaluations = sorted(evaluations, key=lambda evaluation: (evaluation.name))
    return sorted(evaluations, key=lambda evaluation: (evaluation.date), reverse=True)


class PronoteDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Pronote integration."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.title,
            update_interval=timedelta(minutes=15),
        )
        self.config_entry = entry
        self.data = {
            "account_type": entry.data['account_type'],
            "sensor_prefix": None,
            "child_info": None,
            "lessons_today": None,
            "lessons_tomorrow": None,
            "lessons_next_day": None,
            "lessons_period": None,
            "ical_url": None,
            "grades": None,
            "averages": None,
            "homework": None,
            "homework_period": None,
            "absences": None,
            "evaluations": None,
            "punishments": None,
            "menus": None,
        }

    async def _async_update_data(self) -> dict[Platform, dict[str, Any]]:
        """Get the latest data from Pronote and updates the state."""
        try:
            data = self.config_entry.data

            client = await self.hass.async_add_executor_job(get_pronote_client, data)

            if client is None:
                _LOGGER.info('NO CLIENT FOR PRONOTE')
                return None

            child_info = client.info

            if (data['account_type'] == 'parent'):
                client.set_child(data['child'])
                candidates = pronotepy.dataClasses.Util.get(
                    client.children,
                    name=data['child']
                )
                child_info = candidates[0] if candidates else None

            if child_info is None:
                return None

            self.data['account_type'] = data['account_type']
            self.data['child_info'] = child_info

            self.data['sensor_prefix'] = re.sub(
                "[^A-Za-z]", "_", child_info.name.lower())

            lessons_today = await self.hass.async_add_executor_job(client.lessons, date.today())
            self.data['lessons_today'] = sorted(
                lessons_today, key=lambda lesson: lesson.start)

            lessons_tomorrow = await self.hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=1))
            self.data['lessons_tomorrow'] = sorted(
                lessons_tomorrow, key=lambda lesson: lesson.start)

            delta = LESSON_MAX_DAYS
            while True:
                try:
                    lessons_period = await self.hass.async_add_executor_job(client.lessons, date.today(), date.today() + timedelta(days=delta))
                except:
                    _LOGGER.debug(
                        f"No lessons at: {delta} from today, searching best earlier alternative")
                    lessons_period = []
                if lessons_period:
                    break
                delta = delta - 1
            _LOGGER.debug(
                f"Lessons found at: {delta} days, for a maximum of {LESSON_MAX_DAYS} from today")
            self.data['lessons_period'] = sorted(
                lessons_period, key=lambda lesson: lesson.start)

            delta = 1
            while True:
                lessons_nextday = await self.hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=delta))
                if lessons_nextday:
                    break
                delta = delta + 1
            self.data['lessons_next_day'] = sorted(
                lessons_nextday, key=lambda lesson: lesson.start)

            self.data['grades'] = await self.hass.async_add_executor_job(get_grades, client)
            self.data['averages'] = await self.hass.async_add_executor_job(get_averages, client)

            homeworks = await self.hass.async_add_executor_job(client.homework, date.today())
            self.data['homework'] = sorted(
                homeworks, key=lambda lesson: lesson.date)

            homework_period = await self.hass.async_add_executor_job(client.homework, date.today(), date.today() + timedelta(days=HOMEWORK_MAX_DAYS))
            self.data['homework_period'] = sorted(
                homework_period, key=lambda homework: homework.date)

            self.data['absences'] = await self.hass.async_add_executor_job(get_absences, client)

            self.data['evaluations'] = await self.hass.async_add_executor_job(get_evaluations, client)

            self.data['punishments'] = await self.hass.async_add_executor_job(get_punishments, client)

        except Exception as ex:
            _LOGGER.error("Error getting data from pronote: %s", ex)
            raise ex

        try:
            self.data['ical_url'] = await self.hass.async_add_executor_job(client.export_ical)
        except Exception as ex:
            _LOGGER.error("Error getting ical_url from pronote: %s", ex)

        try:
            self.data['menus'] = await self.hass.async_add_executor_job(client.menus, date.today(), date.today() + timedelta(days=7))
        except Exception as ex:
            _LOGGER.error("Error getting menus from pronote: %s", ex)

        return self.data
