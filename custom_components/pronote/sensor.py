from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from datetime import datetime

from .coordinator import PronoteDataUpdateCoordinator
from .pronote_formatter import *

from .const import (
    DOMAIN,
    GRADES_TO_DISPLAY,
    EVALUATIONS_TO_DISPLAY,
    DEFAULT_LUNCH_BREAK_TIME,
)
import logging
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PronoteDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]

    sensors = [
        PronoteChildSensor(coordinator),
        PronoteTimetableSensor(coordinator, "today"),
        PronoteTimetableSensor(coordinator, "tomorrow"),
        PronoteTimetableSensor(coordinator, "next_day"),
        PronoteTimetableSensor(coordinator, "period"),
        PronoteGradesSensor(coordinator),
        PronoteHomeworkSensor(coordinator, ""),
        PronoteHomeworkSensor(coordinator, "_period"),
        PronoteAbsensesSensor(coordinator),
        PronoteEvaluationsSensor(coordinator),
        PronoteAveragesSensor(coordinator),
        PronotePeriodAveragesSensor(coordinator),
        PronotePunishmentsSensor(coordinator),
        PronoteDelaysSensor(coordinator),
        PronoteInformationAndSurveysSensor(coordinator),
        PronoteGenericSensor(coordinator, "ical_url", "timetable_ical_url"),
        PronoteGenericSensor(
            coordinator, "next_alarm", "next_alarm", None, SensorDeviceClass.TIMESTAMP
        ),
        PronoteMenusSensor(coordinator),
    ]

    async_add_entities(sensors, False)


class PronoteChildSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._child_info = coordinator.data["child_info"]
        self._account_type = coordinator.data["account_type"]
        self._attr_unique_id = (
            f"pronote-{self.coordinator.data['sensor_prefix']}-identity"
        )
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {self.coordinator.data['child_info'].name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"Pronote - {self.coordinator.data['child_info'].name}")
            },
            manufacturer="Pronote",
            model=self.coordinator.data["child_info"].name,
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
            "nickname": self.coordinator.config_entry.options.get("nickname"),
            "class_name": self._child_info.class_name,
            "establishment": self._child_info.establishment,
            "via_parent_account": self._account_type == "parent",
            "updated_at": self.coordinator.last_update_success_time,
        }


class PronoteGenericSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Pronote sensor."""

    def __init__(
        self,
        coordinator,
        coordinator_key: str,
        name: str,
        state: str = None,
        device_class: str = None,
    ) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator)
        self._coordinator_key = coordinator_key
        self._name = name
        self._state = state
        self._attr_unique_id = (
            f"pronote-{self.coordinator.data['sensor_prefix']}-{self._name}"
        )
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {self.coordinator.data['child_info'].name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"Pronote - {self.coordinator.data['child_info'].name}")
            },
            manufacturer="Pronote",
            model=self.coordinator.data["child_info"].name,
        )
        if device_class is not None:
            self._attr_device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self.coordinator.data['sensor_prefix']}_{self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data[self._coordinator_key] is None:
            return "unavailable"
        elif self._state == "len":
            return len(self.coordinator.data[self._coordinator_key])
        elif self._state is not None:
            return self._state
        else:
            return self.coordinator.data[self._coordinator_key]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"updated_at": self.coordinator.last_update_success_time}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data[self._coordinator_key] is not None
        )


class PronoteTimetableSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "lessons_" + suffix, "timetable_" + suffix, "len")
        self._suffix = suffix
        self._start_at = None
        self._end_at = None
        self._lunch_break_start_at = None
        self._lunch_break_end_at = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        lessons = self.coordinator.data["lessons_" + self._suffix]
        attributes = []
        canceled_counter = None
        single_day = self._suffix in ["today", "tomorrow", "next_day"]
        lunch_break_time = datetime.strptime(
            self.coordinator.config_entry.options.get(
                "lunch_break_time", DEFAULT_LUNCH_BREAK_TIME
            ),
            "%H:%M",
        ).time()

        if lessons is not None:
            self._start_at = None
            self._end_at = None
            self._lunch_break_start_at = None
            self._lunch_break_end_at = None
            canceled_counter = 0
            for lesson in lessons:
                index = lessons.index(lesson)
                if not (
                    lesson.start == lessons[index - 1].start
                    and lesson.canceled is True
                ):
                    attributes.append(format_lesson(lesson, lunch_break_time))
                if lesson.canceled is False and self._start_at is None:
                    self._start_at = lesson.start
                if lesson.canceled is True:
                    canceled_counter += 1
                if single_day is True and lesson.canceled is False:
                    self._end_at = lesson.end
                    if lesson.end.time() < lunch_break_time:
                        self._lunch_break_start_at = lesson.end
                    if (
                        self._lunch_break_end_at is None
                        and lesson.start.time() >= lunch_break_time
                    ):
                        self._lunch_break_end_at = lesson.start

        result = {
            "updated_at": self.coordinator.last_update_success_time,
            "lessons": attributes,
            "canceled_lessons_counter": canceled_counter,
            "day_start_at": self._start_at,
            "day_end_at": self._end_at,
        }

        if single_day is True:
            result["lunch_break_start_at"] = self._lunch_break_start_at
            result["lunch_break_end_at"] = self._lunch_break_end_at

        return result


class PronoteGradesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "grades", "grades", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        if self.coordinator.data["grades"] is not None:
            for grade in self.coordinator.data["grades"]:
                index_note += 1
                if index_note == GRADES_TO_DISPLAY:
                    break
                attributes.append(format_grade(grade))

        return {
            "updated_at": self.coordinator.last_update_success_time,
            "grades": attributes,
        }


class PronoteHomeworkSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator: PronoteDataUpdateCoordinator, suffix: str) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "homework" + suffix, "homework" + suffix, "len")
        self._suffix = suffix

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        todo_counter = None
        if self.coordinator.data[f"homework{self._suffix}"] is not None:
            todo_counter = 0
            for homework in self.coordinator.data[f"homework{self._suffix}"]:
                attributes.append(format_homework(homework))
                if homework.done is False:
                    todo_counter += 1

        return {
            "updated_at": self.coordinator.last_update_success_time,
            "homework": attributes,
            "todo_counter": todo_counter,
        }


class PronoteAbsensesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "absences", "absences", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data["absences"] is not None:
            for absence in self.coordinator.data["absences"]:
                attributes.append(format_absence(absence))

        return {
            "updated_at": self.coordinator.last_update_success_time,
            "absences": attributes,
        }


class PronoteDelaysSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "delays", "delays", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data["delays"] is not None:
            for delay in self.coordinator.data["delays"]:
                attributes.append(format_delay(delay))

        return {
            "updated_at": self.coordinator.last_update_success_time,
            "delays": attributes,
        }


class PronoteEvaluationsSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "evaluations", "evaluations", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        index_note = 0
        if self.coordinator.data["evaluations"] is not None:
            for evaluation in self.coordinator.data["evaluations"]:
                index_note += 1
                if index_note == EVALUATIONS_TO_DISPLAY:
                    break
                attributes.append(format_evaluation(evaluation))

        return {
            "updated_at": self.coordinator.last_update_success_time,
            "evaluations": attributes,
        }


class PronoteAveragesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "averages", "averages", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data["averages"] is not None:
            for average in self.coordinator.data["averages"]:
                attributes.append(format_average(average))
        return {
            "updated_at": self.coordinator.last_update_success_time,
            "averages": attributes,
        }
        
class PronotePeriodAveragesSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "period_averages", "period_averages", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        _LOGGER.info("coordinator data: %s", self.coordinator.data)
        if self.coordinator.data["period_averages"] is not None:
            attributes.append(self.coordinator.data["period_averages"])
        return {
            "updated_at": self.coordinator.last_update_success_time,
            "period_averages": attributes,
        }        


class PronotePunishmentsSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "punishments", "punishments", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data["punishments"] is not None:
            for punishment in self.coordinator.data["punishments"]:
                attributes.append(format_punishment(punishment))
        return {
            "updated_at": self.coordinator.last_update_success_time,
            "punishments": attributes,
        }


class PronoteMenusSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(coordinator, "menus", "menus", "len")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        if self.coordinator.data["menus"] is not None:
            for menu in self.coordinator.data["menus"]:
                attributes.append(format_menu(menu))
        return {
            "updated_at": self.coordinator.last_update_success_time,
            "menus": attributes,
        }


class PronoteInformationAndSurveysSensor(PronoteGenericSensor):
    """Representation of a Pronote sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the Pronote sensor."""
        super().__init__(
            coordinator, "information_and_surveys", "information_and_surveys", "len"
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = []
        unread_count = None
        if not self.coordinator.data["information_and_surveys"] is None:
            unread_count = 0
            for information_and_survey in self.coordinator.data[
                "information_and_surveys"
            ]:
                attributes.append(format_information_and_survey(information_and_survey))
                if information_and_survey.read is False:
                    unread_count += 1
        return {
            "updated_at": self.coordinator.last_update_success_time,
            "unread_count": unread_count,
            "information_and_surveys": attributes,
        }
