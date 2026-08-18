"""Constants for the Pronote integration."""

from homeassistant.const import Platform

DOMAIN = "pronote"
EVENT_TYPE = "pronote_event"

LESSON_MAX_DAYS = 15
LESSON_NEXT_DAY_SEARCH_LIMIT = 30
HOMEWORK_MAX_DAYS = 15

GRADES_TO_DISPLAY = 11
EVALUATIONS_TO_DISPLAY = 15

INFO_SURVEY_LIMIT_MAX_DAYS = 7

HOMEWORK_DESC_MAX_LENGTH = 125

# Discussions. Two things need bounding here: loading the messages of a
# discussion costs one HTTP request per discussion on every refresh, and the
# messages end up in the entity attributes, which Home Assistant refuses to
# record past 16 KiB. Discussions accumulate over a school year, so the number
# exposed is capped as well (the state still counts them all).
DISCUSSIONS_TO_LOAD = 10
DISCUSSIONS_TO_DISPLAY = 10
DISCUSSION_MESSAGES_TO_DISPLAY = 3
DISCUSSION_CONTENT_MAX_LENGTH = 200

# default values for options
DEFAULT_REFRESH_INTERVAL = 15
DEFAULT_ALARM_OFFSET = 60
DEFAULT_LUNCH_BREAK_TIME = "13:00"

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]
