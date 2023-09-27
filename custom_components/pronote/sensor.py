from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

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
        PronoteOverall_averageSensor(coordinator),
        PronoteClass_overall_averageSensor(coordinator),
        PronotePunishmentsSensor(coordinator),
        PronoteDelaysSensor(coordinator),

        PronoteGenericSensor(coordinator, 'ical_url', 'timetable_ical_url'),

        PronoteMenusSensor(coordinator),
    ]

    async_add_entities(sensors, False)


class PronoteGenericSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator, coordinator_key: str, name: str, state: str = None) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._coordinator_key = coordinator_key
        self._name = name
        self._state = state
        self._attr_unique_id = f"pronote-{self.coordinator.data['sensor_prefix']}-{self._name}"
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {self.coordinator.data['child_info'].name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"Pronote - {self.coordinator.data['child_info'].name}")
            },
            manufacturer="Pronote",
            model=self.coordinator.data['child_info'].name,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_{self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data[self._coordinator_key] is None:
            return 'unavailable'
        elif self._state == 'len':
            return len(self.coordinator.data[self._coordinator_key])
        else:
            return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'updated_at': datetime.now()
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data[self._coordinator_key]


class PronoteChildSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._child_info = coordinator.data['child_info']
        self._account_type = coordinator.data['account_type']
        self._attr_unique_id = f"pronote-{self.coordinator.data['sensor_prefix']}-identity"
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {self.coordinator.data['child_info'].name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"Pronote - {self.coordinator.data['child_info'].name}")
            },
            manufacturer="Pronote",
            model=self.coordinator.data['child_info'].name,
        )

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


class PronoteTimetableSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'lessons_'+suffix, 'timetable_'+suffix, 'len')
        self._suffix = suffix
        self._start_at = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self._lessons = self.coordinator.data['lessons_'+self._suffix]
        attributes = []
        canceled_counter = None
        if self._lessons is not None:
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


def check_attr(value, output):
    if value is not None:
        return output
    return None

class PronoteGradesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'grades', 'grades', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        if self.coordinator.data['grades'] is not None:
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
                    'out_of': check_attr(grade.out_of, float(re.sub(',', '.', grade.out_of))),
                    'default_out_of': check_attr(grade.default_out_of, float(re.sub(',', '.', grade.default_out_of))),
                    'grade_out_of': check_attr(grade.out_of, grade.grade + '/' + grade.out_of),
                    'coefficient': check_attr(grade.coefficient, float(re.sub(',', '.', grade.coefficient))),
                    'class_average': check_attr(grade.average, float(re.sub(',', '.', grade.average))),
                    'max': check_attr(grade.max, float(re.sub(',', '.', grade.max))),
                    'min': check_attr(grade.min, float(re.sub(',', '.', grade.min))),
                    'is_bonus': grade.is_bonus,
                    'is_optionnal': grade.is_optionnal,
                    'is_out_of_20': grade.is_out_of_20,
                })

        return {
            'updated_at': datetime.now(),
            'grades': attributes
        }


class PronoteHomeworkSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'homework'+suffix, 'homework'+suffix, 'len')
        self._suffix = suffix

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        todo_counter = None
        if self.coordinator.data[f"homework{self._suffix}"] is not None:
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


class PronoteAbsensesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'absences', 'absences', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data['absences'] is not None:
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


class PronoteDelaysSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'delays', 'delays', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data['delays'] is not None:
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


class PronoteEvaluationsSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'evaluations', 'evaluations', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        if self.coordinator.data['evaluations'] is not None:
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


class PronoteAveragesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'averages', 'averages', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data['averages'] is not None:
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

class PronoteOverall_averageSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'overall_average', 'overall_average', 'len')

    @property
    def native_value(self):
        """Return the state of the sensor."""
        attributes = []
        if self.coordinator.data['overall_average'] is not None:
            for overall_average in self.coordinator.data['overall_average']:
                attributes.append({
                    (f"{overall_average.replace(',', '.')}"), 
                })
        return (''.join(''.join(a) for a in attributes))
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        return {'updated_at': datetime.now().strftime('%d-%m-%Y %H:%M')}
        
class PronoteClass_overall_averageSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'class_overall_average', 'class_overall_average', 'len')

    @property
    def native_value(self):
        """Return the state of the sensor."""
        attributes = []
        if self.coordinator.data['class_overall_average'] is not None:
            for class_overall_average in self.coordinator.data['class_overall_average']:
                attributes.append({
                    (f"{class_overall_average.replace(',', '.')}"), 
                })
        return (''.join(''.join(a) for a in attributes))
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        return {'updated_at': datetime.now().strftime('%d-%m-%Y %H:%M')}

class PronotePunishmentsSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'punishments', 'punishments', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data['punishments'] is not None:
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


class PronoteMenusSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, 'menus', 'menus', 'len')

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data['menus'] is not None:
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
