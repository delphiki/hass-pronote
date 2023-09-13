# Pronote integration for Home Assistant

## Installation

### Using HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=delphiki&repository=hass-pronote&category=integration)

OR

If you can't find the integration, add this repository to HACS, then:  
HACS > Integrations > **Pronote**

### Manual install

Copy the `pronote` folder from latest release to the `custom_components` folder in your `config` folder.

## Configuration

Click on the following button:  
[![Open your Home Assistant instance and start setting up a new integration of a specific brand.](https://my.home-assistant.io/badges/brand.svg)](https://my.home-assistant.io/redirect/brand/?brand=pronote)  

Or go to :  
Settings > Devices & Sevices > Integrations > Add Integration, and search for "Pronote"

Then follow the step of the config flow:  
![Pronote config flow](doc/config_flow.png)

Note: if you're using a Parent account, you'll be prompt to select a child:  
![Pronote config flow](doc/config_flow_parent.png)

## Usage

This integration provides several sensors (where `LASTNAME` and `FIRSTNAME` are replaced):
* `sensor.pronote_LASTNAME_FIRSTNAME`: basic informations about your child
* `sensor.pronote_LASTNAME_FIRSTNAME_timetable_today`: today's timetable
* `sensor.pronote_LASTNAME_FIRSTNAME_timetable_tomorrow`: tomorrow's timetable
* `sensor.pronote_LASTNAME_FIRSTNAME_timetable_next_day`: next school day timetable
* `sensor.pronote_LASTNAME_FIRSTNAME_timetable_period`: next school day timetable for next 15 days
* `sensor.pronote_LASTNAME_FIRSTNAME_timetable_ical_url`: iCal URL for the timetable
* `sensor.pronote_LASTNAME_FIRSTNAME_grades`: a list of the latest grades
* `sensor.pronote_LASTNAME_FIRSTNAME_homework`: a list of your child's homework
* `sensor.pronote_LASTNAME_FIRSTNAME_homework_period`: a list of your child's homework for max 15 days
* `sensor.pronote_LASTNAME_FIRSTNAME_absences`: a list of your child's absences
* `sensor.pronote_LASTNAME_FIRSTNAME_evaluations` a list of your child's evaluations
* `sensor.pronote_LASTNAME_FIRSTNAME_averages` a list of your child's averages
* `sensor.pronote_LASTNAME_FIRSTNAME_punishments` a list of your child's punishments
* `sensor.pronote_LASTNAME_FIRSTNAME_menus` a list of your child's menus

The sensors above are updated every 15 minutes.
