"""Switch platform for the Pronote integration.

One switch per discussion and per information, whose state is whether it has
been read, and which marks it read or unread in PRONOTE when toggled.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as ha_slugify

from .const import DEFAULT_DISCUSSIONS_ENABLED, DOMAIN
from .coordinator import PronoteDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DISCUSSION_MARKER = "_discussion_"
INFORMATION_MARKER = "_information_"


def discussion_key(discussion) -> str:
    """Stable key for a discussion. PRONOTE exposes no id, so the subject it is."""
    return ha_slugify(discussion["subject"] or "sans objet")


def discussion_unique_id(coordinator, discussion) -> str:
    return (
        f"{DOMAIN}_{coordinator.data['sensor_prefix']}"
        f"{DISCUSSION_MARKER}{discussion_key(discussion)}"
    )


def information_unique_id(coordinator, information) -> str:
    return (
        f"{DOMAIN}_{coordinator.data['sensor_prefix']}"
        f"{INFORMATION_MARKER}{ha_slugify(information['id'])}"
    )


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PronoteDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]

    if coordinator.data is None:
        return

    registry = er.async_get(hass)

    # Unique ids of the entities this setup has created. It starts out empty on
    # every start: registry entries are not live entities, they only carry the
    # entity id and settings of entities the platform is expected to create
    # again. Seeding this from the registry would leave them unprovided.
    added_ids: set[str] = set()

    @callback
    def sync_switches() -> None:
        """Add switches for new items, remove those that are gone.

        Discussions and informations come and go over a school year: without the
        removal pass, the entity registry would slowly fill up with switches
        pointing at threads and news that no longer exist.
        """
        discussions_enabled = config_entry.options.get(
            "discussions", DEFAULT_DISCUSSIONS_ENABLED
        )
        discussions = coordinator.data.get("discussions")
        informations = coordinator.data.get("information_and_surveys")

        current: dict[str, tuple[str, dict]] = {}
        if discussions_enabled:
            for discussion in discussions or []:
                current[discussion_unique_id(coordinator, discussion)] = (
                    "discussion",
                    discussion,
                )
        for information in informations or []:
            current[information_unique_id(coordinator, information)] = (
                "information",
                information,
            )

        added = [
            PronoteDiscussionSwitch(coordinator, item, unique_id)
            if kind == "discussion"
            else PronoteInformationSwitch(coordinator, item, unique_id)
            for unique_id, (kind, item) in current.items()
            if unique_id not in added_ids
        ]
        if added:
            added_ids.update(entity.unique_id for entity in added)
            async_add_entities(added)

        # A failed refresh leaves the data at None, which must not be read as
        # "everything is gone", or a transient error would delete entities.
        # Disabling discussions, on the other hand, is meant to remove them.
        removable = []
        if not discussions_enabled or discussions is not None:
            removable.append(DISCUSSION_MARKER)
        if informations is not None:
            removable.append(INFORMATION_MARKER)

        for entry in er.async_entries_for_config_entry(
                registry, config_entry.entry_id
        ):
            if entry.domain != "switch" or entry.unique_id in current:
                continue
            if not any(marker in entry.unique_id for marker in removable):
                continue
            _LOGGER.debug("Removing switch of gone item: %s", entry.entity_id)
            registry.async_remove(entry.entity_id)
            added_ids.discard(entry.unique_id)

    sync_switches()
    config_entry.async_on_unload(coordinator.async_add_listener(sync_switches))


class PronoteReadSwitch(CoordinatorEntity, SwitchEntity):
    """Read state of a single item.

    On means read, which is also how it is toggled: turning the switch on marks
    the item as read in PRONOTE, turning it off marks it unread.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, unique_id: str, name: str) -> None:
        """Initialize the Pronote switch."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {coordinator.data['child_info'].name}",
            identifiers={(DOMAIN, coordinator.data["child_info"].name)},
            manufacturer="Pronote",
            model=coordinator.data["child_info"].name,
        )

    @property
    def _item(self):
        """The item this switch stands for, or None once it is gone."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._item is not None


class PronoteDiscussionSwitch(PronoteReadSwitch):
    """Read/unread state of a single discussion."""

    def __init__(self, coordinator, discussion, unique_id: str) -> None:
        super().__init__(
            coordinator, unique_id, discussion["subject"] or "(sans objet)"
        )
        self._key = discussion_key(discussion)
        self._subject = discussion["subject"]

    @property
    def _item(self):
        for discussion in self.coordinator.data.get("discussions") or []:
            if discussion_key(discussion) == self._key:
                return discussion
        return None

    @property
    def is_on(self) -> bool | None:
        discussion = self._item
        return None if discussion is None else discussion["unread"] == 0

    @property
    def icon(self) -> str:
        return "mdi:email-open-outline" if self.is_on else "mdi:email-alert"

    @property
    def extra_state_attributes(self):
        discussion = self._item or {}
        return {
            "kind": "discussion",
            "subject": discussion.get("subject"),
            "creator": discussion.get("creator"),
            "unread": discussion.get("unread"),
            "last_message_date": discussion.get("last_message_date"),
            "last_message_author": discussion.get("last_message_author"),
            "last_message": discussion.get("last_message"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Mark the discussion as read in PRONOTE."""
        await self.coordinator.async_mark_discussions(subject=self._subject, read=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Mark the discussion as unread in PRONOTE."""
        await self.coordinator.async_mark_discussions(subject=self._subject, read=False)


class PronoteInformationSwitch(PronoteReadSwitch):
    """Read/unread state of a single information or survey."""

    def __init__(self, coordinator, information, unique_id: str) -> None:
        super().__init__(
            coordinator, unique_id, information["title"] or "(sans titre)"
        )
        self._id = information["id"]

    @property
    def _item(self):
        for information in self.coordinator.data.get("information_and_surveys") or []:
            if information["id"] == self._id:
                return information
        return None

    @property
    def is_on(self) -> bool | None:
        information = self._item
        return None if information is None else information["read"]

    @property
    def icon(self) -> str:
        information = self._item
        if information is not None and information.get("survey"):
            return "mdi:poll" if self.is_on else "mdi:comment-question-outline"
        return "mdi:newspaper-variant-outline" if self.is_on else "mdi:newspaper-variant"

    @property
    def extra_state_attributes(self):
        information = self._item or {}
        return {
            "kind": "information",
            "title": information.get("title"),
            "author": information.get("author"),
            "category": information.get("category"),
            "survey": information.get("survey"),
            "creation_date": information.get("creation_date"),
            "start_date": information.get("start_date"),
            "end_date": information.get("end_date"),
            "attachments": information.get("attachments"),
            "content": information.get("content"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Mark the information as read in PRONOTE."""
        await self.coordinator.async_mark_information(self._id, read=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Mark the information as unread in PRONOTE."""
        await self.coordinator.async_mark_information(self._id, read=False)
