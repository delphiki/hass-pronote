"""Switch platform for the Pronote integration: one switch per discussion."""

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


def discussion_key(discussion) -> str:
    """Stable key for a discussion. PRONOTE exposes no id, so the subject it is."""
    return ha_slugify(discussion["subject"] or "sans objet")


def discussion_unique_id(coordinator, key: str) -> str:
    return f"{DOMAIN}_{coordinator.data['sensor_prefix']}_discussion_{key}"


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PronoteDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]

    registry = er.async_get(hass)

    if not config_entry.options.get("discussions", DEFAULT_DISCUSSIONS_ENABLED):
        # This entry does not expose discussions: drop the switches a previous
        # configuration may have left behind, rather than leaving them dangling.
        for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
            if entry.domain == "switch":
                registry.async_remove(entry.entity_id)
        return

    if coordinator.data is None:
        return


    # Unique ids of the entities this setup has created. It starts out empty on
    # every start: registry entries are not live entities, they only carry the
    # entity id and settings of entities the platform is expected to create
    # again. Seeding this from the registry would leave them unprovided.
    added_ids: set[str] = set()

    @callback
    def sync_discussion_switches() -> None:
        """Add switches for new discussions, remove those that are gone.

        Discussions come and go over a school year: without the removal pass,
        the entity registry would slowly fill up with switches pointing at
        threads that no longer exist.
        """
        discussions = coordinator.data.get("discussions")
        if discussions is None:
            # Refresh failed, or the messaging tab is unavailable: keep the
            # existing switches rather than deleting them on a transient error.
            return

        current = {
            discussion_unique_id(coordinator, discussion_key(discussion)): discussion
            for discussion in discussions
        }

        added = [
            PronoteDiscussionSwitch(coordinator, discussion, unique_id)
            for unique_id, discussion in current.items()
            if unique_id not in added_ids
        ]
        if added:
            added_ids.update(entity.unique_id for entity in added)
            async_add_entities(added)

        for entry in er.async_entries_for_config_entry(
                registry, config_entry.entry_id
        ):
            if entry.domain == "switch" and entry.unique_id not in current:
                _LOGGER.debug(
                    "Removing switch of gone discussion: %s", entry.entity_id
                )
                registry.async_remove(entry.entity_id)
                added_ids.discard(entry.unique_id)

    sync_discussion_switches()
    config_entry.async_on_unload(
        coordinator.async_add_listener(sync_discussion_switches)
    )


class PronoteDiscussionSwitch(CoordinatorEntity, SwitchEntity):
    """Read/unread state of a single discussion.

    On means the discussion is read, which is also how it is toggled: turning
    the switch on marks it as read in PRONOTE, turning it off marks it unread.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, discussion, unique_id: str) -> None:
        """Initialize the Pronote discussion switch."""
        super().__init__(coordinator)
        self._key = discussion_key(discussion)
        self._subject = discussion["subject"]
        self._attr_unique_id = unique_id
        self._attr_name = discussion["subject"] or "(sans objet)"
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {coordinator.data['child_info'].name}",
            identifiers={(DOMAIN, coordinator.data["child_info"].name)},
            manufacturer="Pronote",
            model=coordinator.data["child_info"].name,
        )

    @property
    def _discussion(self):
        """The discussion this switch stands for, or None once it is gone."""
        for discussion in self.coordinator.data.get("discussions") or []:
            if discussion_key(discussion) == self._key:
                return discussion
        return None

    @property
    def is_on(self) -> bool | None:
        discussion = self._discussion
        return None if discussion is None else discussion["unread"] == 0

    @property
    def icon(self) -> str:
        return "mdi:email-open-outline" if self.is_on else "mdi:email-alert-outline"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._discussion is not None

    @property
    def extra_state_attributes(self):
        discussion = self._discussion or {}
        return {
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
