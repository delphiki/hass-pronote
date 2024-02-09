from datetime import datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util.dt import get_time_zone
import pytz

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import PronoteDataUpdateCoordinator
from .pronote_formatter import format_displayed_lesson

from .const import (
    DOMAIN
)

async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ReCollect Waste sensors based on a config entry."""
    coordinator: PronoteDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([PronoteCalendar(coordinator, config_entry)], False)

@callback
def async_get_calendar_event_from_lessons(lesson, timezone) -> CalendarEvent:
    """Get a HASS CalendarEvent from a Pronote Lesson."""
    tz = pytz.timezone(timezone)

    lesson_name = format_displayed_lesson(lesson)
    if lesson.canceled:
        lesson_name = f"Annulé - {lesson_name}"

    return CalendarEvent(
        summary=lesson_name,
        description=f"{lesson.teacher_name}",
        location=f"Salle {lesson.classroom}",
        start=tz.localize(lesson.start),
        end=tz.localize(lesson.end),
    )

class PronoteCalendar(CoordinatorEntity, CalendarEntity):

    def __init__(
        self,
        coordinator: PronoteDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the ReCollect Waste entity."""
        super().__init__(coordinator, entry)

        child_info = coordinator.data['child_info']
        calendar_name = child_info.name
        nickname = self.coordinator.config_entry.options.get('nickname', '')
        if nickname != '':
            calendar_name = nickname

        self._attr_translation_key = "timetable"
        self._attr_translation_placeholders = {"child": calendar_name}
        self._attr_unique_id = f"{coordinator.data['sensor_prefix']}-timetable"
        self._attr_name = f"Emploi du temps de {calendar_name}"
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {self.coordinator.data['child_info'].name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"Pronote - {self.coordinator.data['child_info'].name}")
            },
            manufacturer="Pronote",
            model=self.coordinator.data['child_info'].name,
        )
        self._event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            now = datetime.now()
            current_event = next(
                event
                for event in self.coordinator.data['lessons_period']
                if event.start >= now and now < event.end
            )
        except StopIteration:
            self._event = None
        else:
            self._event = async_get_calendar_event_from_lessons(
                current_event, self.hass.config.time_zone
            )

        super()._handle_coordinator_update()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            async_get_calendar_event_from_lessons(event, hass.config.time_zone)
            for event in filter(lambda lesson: lesson.canceled == False, self.coordinator.data['lessons_period'])
        ]