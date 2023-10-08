"""Data update coordinator for the Pronote integration."""
from __future__ import annotations

from datetime import date, datetime, timedelta
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
   
    _LOGGER.debug(f"Coordinator uses connection: {data['connection_type']}")
    
    if data['connection_type'] == 'qrcode':  
        qr_code_url=data['qr_code_url']
        qr_code_username=data['qr_code_username']
        qr_code_uuid=data['qr_code_uuid']
        qr_code_password = open(f"/config/custom_components/pronote/qrcredentials_{qr_code_username}.txt", "r").read()

        _LOGGER.debug(f"Coordinator uses qr_code_username: {qr_code_username}")
        _LOGGER.debug(f"Coordinator uses qr_code_pwd: {qr_code_password}")
        try:
            qr_code_internal_password
        except:
            _LOGGER.info(f"Coordinator qr_code_internal_pwd not defined (yet)")
        else:
            _LOGGER.debug(f"Coordinator uses qr_code_internal_pwd: {qr_code_internal_password}")
        client = pronotepy.Client.token_login(qr_code_url,qr_code_username,qr_code_password,qr_code_uuid)
        qr_code_internal_password = client.password      
        qrcredentials = open(f"/config/custom_components/pronote/qrcredentials_{qr_code_username}.txt", "w+")
        qrcredentials.writelines([client.password])
        qrcredentials.close()         

    else:
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
    grades = client.current_period.grades
    return sorted(grades, key=lambda grade: grade.date, reverse=True)


def get_absences(client):
    absences = client.current_period.absences
    return sorted(absences, key=lambda absence: absence.from_date, reverse=True)


def get_delays(client):
    delays = client.current_period.delays
    return sorted(delays, key=lambda delay: delay.date, reverse=True)


def get_averages(client):
    averages = client.current_period.averages
    return averages


def get_punishments(client):
    punishments = client.current_period.punishments
    return sorted(punishments, key=lambda punishment: punishment.given.strftime("%Y-%m-%d"), reverse=True)


def get_evaluations(client):
    evaluations = client.current_period.evaluations
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
    async def _async_update_data(self) -> dict[Platform, dict[str, Any]]:
        """Get the latest data from Pronote and updates the state."""
        data = self.config_entry.data
        self.data = {
            "account_type": data['account_type'],
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
            "delays": None,
            "evaluations": None,
            "punishments": None,
            "menus": None,
            "information_and_surveys": None,
        }

        client = await self.hass.async_add_executor_job(get_pronote_client, data)

        if client is None:
            _LOGGER.error('Unable to init pronote client')
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

        self.data['child_info'] = child_info
        self.data['sensor_prefix'] = re.sub(
            "[^A-Za-z]", "_", child_info.name.lower())

        try:
            lessons_today = await self.hass.async_add_executor_job(client.lessons, date.today())
            self.data['lessons_today'] = sorted(
                lessons_today, key=lambda lesson: lesson.start)
        except Exception as ex:
            _LOGGER.info(
                "Error getting lessons_today from pronote: %s", ex)

        try:
            lessons_tomorrow = await self.hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=1))
            self.data['lessons_tomorrow'] = sorted(
                lessons_tomorrow, key=lambda lesson: lesson.start)
        except Exception as ex:
            _LOGGER.info(
                "Error getting lessons_tomorrow from pronote: %s", ex)

        delta = LESSON_MAX_DAYS
        while True:
            try:
                lessons_period = await self.hass.async_add_executor_job(client.lessons, date.today(), date.today() + timedelta(days=delta))
            except Exception as ex:
                _LOGGER.debug(
                    f"No lessons at: {delta} from today, searching best earlier alternative ({ex})")
                lessons_period = []
            if lessons_period:
                break
            delta = delta - 1
        _LOGGER.debug(
            f"Lessons found at: {delta} days, for a maximum of {LESSON_MAX_DAYS} from today")
        self.data['lessons_period'] = sorted(
            lessons_period, key=lambda lesson: lesson.start)

        try:
            delta = 1
            while True:
                lessons_nextday = await self.hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=delta))
                if lessons_nextday:
                    break
                delta = delta + 1
            self.data['lessons_next_day'] = sorted(
                lessons_nextday, key=lambda lesson: lesson.start)
        except Exception as ex:
            _LOGGER.info(
                "Error getting lessons_next_day from pronote: %s", ex)

        try:
            self.data['grades'] = await self.hass.async_add_executor_job(get_grades, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting grades from pronote: %s", ex)

        try:
            self.data['averages'] = await self.hass.async_add_executor_job(get_averages, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting averages from pronote: %s", ex)

        try:
            homeworks = await self.hass.async_add_executor_job(client.homework, date.today())
            self.data['homework'] = sorted(
                homeworks, key=lambda lesson: lesson.date)
        except Exception as ex:
            _LOGGER.info(
                "Error getting homework from pronote: %s", ex)

        try:
            homework_period = await self.hass.async_add_executor_job(client.homework, date.today(), date.today() + timedelta(days=HOMEWORK_MAX_DAYS))
            self.data['homework_period'] = sorted(
                homework_period, key=lambda homework: homework.date)
        except Exception as ex:
            _LOGGER.info(
                "Error getting homework_period from pronote: %s", ex)

        try:
            information_and_surveys = await self.hass.async_add_executor_job(client.information_and_surveys)
            self.data['information_and_surveys'] = sorted(
                information_and_surveys, key=lambda information_and_survey: information_and_survey.creation_date, reverse=True)
        except Exception as ex:
            _LOGGER.info(
                "Error getting information_and_surveys from pronote: %s", ex)

        try:
            self.data['absences'] = await self.hass.async_add_executor_job(get_absences, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting absences from pronote: %s", ex)

        try:
            self.data['delays'] = await self.hass.async_add_executor_job(get_delays, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting delays from pronote: %s", ex)

        try:
            self.data['evaluations'] = await self.hass.async_add_executor_job(get_evaluations, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting evaluations from pronote: %s", ex)

        try:
            self.data['punishments'] = await self.hass.async_add_executor_job(get_punishments, client)
        except Exception as ex:
            _LOGGER.info(
                "Error getting punishments from pronote: %s", ex)

        try:
            self.data['ical_url'] = await self.hass.async_add_executor_job(client.export_ical)
        except Exception as ex:
            _LOGGER.info("Error getting ical_url from pronote: %s", ex)

        try:
            self.data['menus'] = await self.hass.async_add_executor_job(client.menus, date.today(), date.today() + timedelta(days=7))
        except Exception as ex:
            _LOGGER.info("Error getting menus from pronote: %s", ex)

        return self.data
