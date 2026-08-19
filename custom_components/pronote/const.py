"""Constants for the Pronote integration."""

from homeassistant.const import Platform

DOMAIN = "pronote"
EVENT_TYPE = "pronote_event"

SERVICE_MARK_DISCUSSIONS = "mark_discussions_as_read"

LESSON_MAX_DAYS = 15
LESSON_NEXT_DAY_SEARCH_LIMIT = 30
HOMEWORK_MAX_DAYS = 15

GRADES_TO_DISPLAY = 11
EVALUATIONS_TO_DISPLAY = 15

INFO_SURVEY_LIMIT_MAX_DAYS = 7

HOMEWORK_DESC_MAX_LENGTH = 125

# Discussions. Loading the messages of a discussion costs one HTTP request per
# discussion on every refresh, hence DISCUSSIONS_TO_LOAD.
#
# The messages then end up in the entity attributes, which Home Assistant stops
# recording past 16 KiB. Rather than capping the number of discussions shown,
# the most recent ones are kept until DISCUSSIONS_ATTRIBUTE_MAX_BYTES is
# reached: a few discussions keep their full content, many degrade gracefully.
# The state and unread_count always cover them all.
DISCUSSIONS_TO_LOAD = 10
DISCUSSION_MESSAGES_TO_DISPLAY = 3
DISCUSSION_CONTENT_MAX_LENGTH = 1000
DISCUSSIONS_ATTRIBUTE_MAX_BYTES = 12000

# default values for options
DEFAULT_REFRESH_INTERVAL = 15
DEFAULT_ALARM_OFFSET = 60
DEFAULT_LUNCH_BREAK_TIME = "13:00"
# The messaging tab belongs to the account, not to a child: with several
# children, every entry would otherwise expose the same discussions.
DEFAULT_DISCUSSIONS_ENABLED = True

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR, Platform.SWITCH]
