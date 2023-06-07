from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.sensor import SensorEntity

import logging
import pronotepy
import re
from datetime import date, timedelta, datetime

from .const import (
    DOMAIN,
    GRADES_TO_DISPLAY,
    HOMEWORK_DESC_MAX_LENGTH
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


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
        _LOGGER.info(client.info.name)
    except Exception as err:
        _LOGGER.critical(err)
        return None

    return client


def get_grades(client):
    grades = client.current_period.grades
    return sorted(grades, key=lambda grade: grade.date, reverse=True)


def get_absences(client):
    absences = client.current_period.absences
    return sorted(absences, key=lambda absence: absence.from_date, reverse=True)


def get_evaluations(client):
    try:
        evaluations = client.current_period.evaluations
    except:
        evaluations = []
    evaluations = sorted(evaluations, key=lambda evaluation: (evaluation.name))
    return sorted(evaluations, key=lambda evaluation: (evaluation.date), reverse=True)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.data

    client = await hass.async_add_executor_job(get_pronote_client, data)
    child_info = client.info

    if (data['account_type'] == 'parent'):
        client.set_child(data['child'])
        candidates = pronotepy.dataClasses.Util.get(
            client.children,
            name=data['child']
        )
        child_info = candidates[0] if candidates else None

    if child_info is None:
        return False

    sensor_prefix = re.sub("[^A-Za-z]", "_", child_info.name.lower())

    lessons_today = await hass.async_add_executor_job(client.lessons, date.today())
    lessons_today = sorted(lessons_today, key=lambda lesson: lesson.start)

    lessons_tomorrow = await hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=1))
    lessons_tomorrow = sorted(
        lessons_tomorrow, key=lambda lesson: lesson.start)

    delta = 1
    while True:
        lessons_nextday = await hass.async_add_executor_job(client.lessons, date.today() + timedelta(days=delta))
        if lessons_nextday:
            break
        delta = delta + 1
    lessons_nextday = sorted(lessons_nextday, key=lambda lesson: lesson.start)

    grades = await hass.async_add_executor_job(get_grades, client)

    homeworks = await hass.async_add_executor_job(client.homework, date.today())
    homeworks = sorted(homeworks, key=lambda lesson: lesson.date)

    absences = await hass.async_add_executor_job(get_absences, client)

    evaluations = await hass.async_add_executor_job(get_evaluations, client)

    sensors = [
        PronoteChildSensor(sensor_prefix, child_info, data['account_type']),
        PronoteTimetableSensor(sensor_prefix, 'today', lessons_today),
        PronoteTimetableSensor(sensor_prefix, 'tomorrow', lessons_tomorrow),
        PronoteTimetableSensor(sensor_prefix, 'next_day', lessons_nextday),
        PronoteGradesSensor(sensor_prefix, grades),
        PronoteHomeworksSensor(sensor_prefix, homeworks),
        PronoteAbsensesSensor(sensor_prefix, absences),
        PronoteEvaluationsSensor(sensor_prefix, evaluations),
    ]
    async_add_entities(sensors, True)


class PronoteChildSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, child_info: dict, account_type: str) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._child_info = child_info
        self._account_type = account_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._child_info.name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "full_name": self._child_info.name,
            "class_name": self._child_info.class_name,
            "establishment": self._child_info.establishment,
            "via_parent_account": self._account_type == 'parent',
            "updated_at": datetime.now()
        }


def cours_affiche_from_lesson(lesson_data):
    if lesson_data.detention is True:
        return 'RETENUE'
    if lesson_data.subject:
        return lesson_data.subject.name
    return 'autre'


def build_cours_data(lesson_data):
    return {
        'id': lesson_data.id,
        'start_at': lesson_data.start.strftime("%d/%m/%Y, %H:%M"),
        'date': lesson_data.start.strftime("%d/%m/%Y"),
        'time': lesson_data.start.strftime("%H:%M"),
        'end_at': lesson_data.end.strftime("%H:%M"),
        'lesson': cours_affiche_from_lesson(lesson_data),
        'classroom': lesson_data.classroom,
        'canceled': lesson_data.canceled,
        'status': lesson_data.status,
        'background_color': lesson_data.background_color,
    }


class PronoteTimetableSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, suffix: str, lessons) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._suffix = suffix
        self._lessons = lessons
        self._start_at = None
        _LOGGER.info('PronoteTimetableSensor')
        _LOGGER.info(lessons)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}_timetable_{self._suffix}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._start_at

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for lesson in self._lessons:
            index = self._lessons.index(lesson)
            if not (lesson.start == self._lessons[index - 1].start and lesson.canceled is True):
                attributes.append(build_cours_data(lesson))
            if lesson.canceled is False and self._start_at is None:
                self.state = lesson.start

        return {
            'updated_at': datetime.now(),
            'lessons': attributes
        }


class PronoteGradesSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, grades) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._grades = grades

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}_grades"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self._grades)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        for grade in self._grades:
            index_note += 1
            if index_note == GRADES_TO_DISPLAY:
                break
            attributes.append({
                'date': grade.date,
                'subject': grade.subject.name,
                'grade': grade.grade,
                'out_of': float(re.sub(',', '.', grade.out_of)),
                'grade_out_of': grade.grade + '/' + grade.out_of,
                'coefficient': float(re.sub(',', '.', grade.coefficient)),
                'class_average': float(re.sub(',', '.', grade.average)),
                'max': float(re.sub(',', '.', grade.max)),
                'min': float(re.sub(',', '.', grade.min)),
            })

        return {
            'updated_at': datetime.now(),
            'grades': attributes
        }


class PronoteHomeworksSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, homeworks) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._homeworks = homeworks

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}_homeworks"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self._homeworks)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for homework in self._homeworks:
            attributes.append({
                'index': self._homeworks.index(homework),
                'date': homework.date,
                'subject': homework.subject.name,
                'short_description': (homework.description)[0:HOMEWORK_DESC_MAX_LENGTH],
                'description': (homework.description),
                'done': homework.done,
            })

        return {
            'updated_at': datetime.now(),
            'homeworks': attributes
        }


class PronoteAbsensesSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, absences) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._absences = absences

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}_absences"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self._absences)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for absence in self._absences:
            attributes.append({
                'id': absence.id,
                'from': absence.from_date,
                'formatted_from': absence.from_date.strftime("Le %d %b à %H:%M"),
                'to': absence.to_date,
                'justified': absence.justified,
                'hours': absence.hours,
                'days': absence.days,
                'reason': str(absence.reasons)[2:-2],
            })

        return {
            'updated_at': datetime.now(),
            'absences': attributes
        }


class PronoteEvaluationsSensor(SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, prefix: str, evaluations) -> None:
        """Initialize the Pronote sensor."""
        self._prefix = prefix
        self._evaluations = evaluations

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._prefix}_evaluations"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self._evaluations)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for evaluation in self._evaluations:
            attributes.append({
                'date': evaluation.date,
                'subject': evaluation.subject.name,
                'description': evaluation.description,
                'coefficient': evaluation.coefficient,
                'paliers': evaluation.paliers,
                'teacher': evaluation.teacher,
                'acquisitions': [
                    {
                        'order': acquisition.order,
                        'name': acquisition.name,
                        'abbreviation': acquisition.abbreviation,
                        'level': acquisition.level,
                        'domain': acquisition.domain,
                    }
                    for acquisition in evaluation.acquisitions
                ]
            })

        return {
            'updated_at': datetime.now(),
            'evaluations': attributes
        }
