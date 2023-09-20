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
        PronoteDelaysSensor(coordinator),

        PronoteGenericSensor(coordinator, 'ical_url', 'timetable_ical_url'),

        PronoteMenusSensor(coordinator),
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


class PronoteGenericSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator, coordinator_key: str, name: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._coordinator_key = coordinator_key
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_{self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data[self._coordinator_key] is None:
            return 'unavailable'
        return self.coordinator.data[self._coordinator_key]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'updated_at': datetime.now()
        }


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
        'teacher_name': lesson_data.teacher_name,
        'teacher_names': lesson_data.teacher_names,
        'classrooms': lesson_data.classrooms,
        'outing': lesson_data.outing,
        'memo': lesson_data.memo,
        'group_name': lesson_data.group_name,
        'group_names': lesson_data.group_names,
        'exempted': lesson_data.exempted,
        'virtual_classrooms': lesson_data.virtual_classrooms,
        'num': lesson_data.num,
        'detention': lesson_data.detention,
        'test': lesson_data.test,
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
                'id': grade.id,
                'date': grade.date,
                'subject': grade.subject.name,
                'comment': grade.comment,
                'grade': grade.grade,
                'out_of': float(re.sub(',', '.', grade.out_of)),
                'default_out_of': float(re.sub(',', '.', grade.default_out_of)),
                'grade_out_of': grade.grade + '/' + grade.out_of,
                'coefficient': float(re.sub(',', '.', grade.coefficient)),
                'class_average': float(re.sub(',', '.', grade.average)),
                'max': float(re.sub(',', '.', grade.max)),
                'min': float(re.sub(',', '.', grade.min)),
                'is_bonus': grade.is_bonus,
                'is_optionnal': grade.is_optionnal,
                'is_out_of_20': grade.is_out_of_20,
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
        todo_counter = 0
        for homework in self.coordinator.data[f"homework{self._suffix}"]:
            attributes.append({
                'index': self.coordinator.data[f"homework{self._suffix}"].index(homework),
                'date': homework.date,
                'subject': homework.subject.name,
                'short_description': (homework.description)[0:HOMEWORK_DESC_MAX_LENGTH],
                'description': (homework.description),
                'done': homework.done,
            })
            if homework.done is False:
                todo_counter += 1

        return {
            'updated_at': datetime.now(),
            'homework': attributes,
            'todo_counter': todo_counter
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
        
class PronoteDelaysSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_delays"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.coordinator.data['delays'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        for delay in self.coordinator.data['delays']:
            attributes.append({
                'id': delay.id,
                'date': delay.date,
                'minutes': delay.minutes,
                'justified': delay.justified,
                'justification': delay.justification,
                'reasons': str(delay.reasons)[2:-2],
            })

        return {
            'updated_at': datetime.now(),
            'delays': attributes
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


def format_food_list(food_list):
    formatted_food_list = []
    if food_list is None:
        return formatted_food_list

    for food in food_list:
        formatted_food_labels = []
        for label in food.labels:
            formatted_food_labels.append({
                'id': label.id,
                'name': label.name,
                'color': label.color,
            })
        formatted_food_list.append({
            'id': food.id,
            'name': food.name,
            'labels': formatted_food_labels,
        })

    return formatted_food_list


class PronoteMenusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_menus"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data['menus'] is None:
            return 'unavailable'
        return len(self.coordinator.data['menus'])

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if not self.coordinator.data['menus'] is None:
            for menu in self.coordinator.data['menus']:
                attributes.append({
                    'id': menu.id,
                    'name': menu.name,
                    'date': menu.date.strftime("%Y-%m-%d"),
                    'is_lunch': menu.is_lunch,
                    'is_dinner': menu.is_dinner,
                    'first_meal': format_food_list(menu.first_meal),
                    'main_meal': format_food_list(menu.main_meal),
                    'side_meal': format_food_list(menu.side_meal),
                    'other_meal': format_food_list(menu.other_meal),
                    'cheese': format_food_list(menu.cheese),
                    'dessert': format_food_list(menu.dessert),
                })
        return {
            'updated_at': datetime.now(),
            'menus': attributes
        }
