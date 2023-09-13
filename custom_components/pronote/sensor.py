from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.sensor import SensorEntity

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

import re

from datetime import datetime

from .coordinator import PronoteDataUpdateCoordinator

from .const import (
    DOMAIN,
    GRADES_TO_DISPLAY,
    HOMEWORK_DESC_MAX_LENGTH,
    EVALUATIONS_TO_DISPLAY
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PronoteDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]

    await coordinator.async_config_entry_first_refresh()

    sensors = [
        PronoteChildSensor(coordinator),

        PronoteTimetableSensor(coordinator, 'today'),
        PronoteTimetableSensor(coordinator, 'tomorrow'),
        PronoteTimetableSensor(coordinator, 'next_day'),
        PronoteTimetableSensor(coordinator, 'period'),

        PronoteGradesSensor(coordinator),

        PronoteHomeworkSensor(coordinator, ''),
        PronoteHomeworkSensor(coordinator, '_period'),

        PronoteAbsensesSensor(coordinator),
        PronoteEvaluationsSensor(coordinator),
        PronoteAveragesSensor(coordinator),
        PronotePunishmentsSensor(coordinator),
    ]

    async_add_entities(sensors, False)


class PronoteBaseSensor(
    CoordinatorEntity[PronoteDataUpdateCoordinator], SensorEntity
):
    """Representation of an Pronote sensor."""

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)


class PronoteChildSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._child_info = coordinator.data['child_info']
        self._account_type = coordinator.data['account_type']

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}"

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
        'start_at': lesson_data.start,
        'end_at': lesson_data.end,
        'start_time': lesson_data.start.strftime("%H:%M"),
        'end_time': lesson_data.end.strftime("%H:%M"),
        'lesson': cours_affiche_from_lesson(lesson_data),
        'classroom': lesson_data.classroom,
        'canceled': lesson_data.canceled,
        'status': lesson_data.status,
        'background_color': lesson_data.background_color,
    }


class PronoteTimetableSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._suffix = suffix
        self._start_at = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_timetable_{self._suffix}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['lessons_'+self._suffix])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self._lessons = self.coordinator.data['lessons_'+self._suffix]
        attributes = []
        canceled_counter = 0
        for lesson in self._lessons:
            index = self._lessons.index(lesson)
            if not (lesson.start == self._lessons[index - 1].start and lesson.canceled is True):
                attributes.append(build_cours_data(lesson))
            if lesson.canceled is False and self._start_at is None:
                self._start_at = lesson.start
            if lesson.canceled is True:
                canceled_counter += 1
        return {
            'updated_at': datetime.now(),
            'lessons': attributes,
            'day_start_at': self._start_at,
            'canceled_lessons_counter': canceled_counter
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["lessons_" + self._suffix]


class PronoteGradesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_grades"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['grades'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        for grade in self.coordinator.data['grades']:
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


class PronoteHomeworkSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._suffix = suffix

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_homework{self._suffix}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data[f"homework{self._suffix}"])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for homework in self.coordinator.data[f"homework{self._suffix}"]:
            attributes.append({
                'index': self.coordinator.data[f"homework{self._suffix}"].index(homework),
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


class PronoteAbsensesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_absences"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['absences'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for absence in self.coordinator.data['absences']:
            attributes.append({
                'id': absence.id,
                'from': absence.from_date,
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


class PronoteEvaluationsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_evaluations"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['evaluations'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        for evaluation in self.coordinator.data['evaluations']:
            index_note += 1
            if index_note == EVALUATIONS_TO_DISPLAY:
                break
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


class PronoteAveragesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_averages"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['averages'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for average in self.coordinator.data['averages']:
            attributes.append({
                'average': average.student,
                'class': average.class_average,
                'max': average.max,
                'min': average.min,
                'out_of': average.out_of,
                'subject': average.subject.name,
            })
        return {
            'updated_at': datetime.now(),
            'averages': attributes
        }


class PronotePunishmentsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_punishments"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['punishments'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for punishment in self.coordinator.data['punishments']:
            attributes.append({
                'id': punishment.id,
                'date': punishment.given.strftime("%Y-%m-%d"),
                'subject': punishment.during_lesson,
                'reasons': punishment.reasons,
                'circumstances': punishment.circumstances,
                'nature': punishment.nature,
                'duration': str(punishment.duration),
                'homework': punishment.homework,
                'exclusion': punishment.exclusion,
            })
        return {
            'updated_at': datetime.now(),
            'punishments': attributes
        }
