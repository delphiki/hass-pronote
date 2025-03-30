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

You can choose between two options when adding a config entry.  

### Option 1: using username and password

Use your Pronote URL with username, password and ENT (optional):  
![Pronote config flow](doc/config_flow_username_password.png)

### Option 2: using the QR Code

Install the following Chrome Extension: [QR Code Reader](https://chrome.google.com/webstore/detail/qr-code-reader/likadllkkidlligfcdhfnnbkjigdkmci) (only needed for setup).  

Create the QR Code from your Pronote account:  
![image](doc/generate_qr_code.png)

Use the extension to scan the QR Code:  
![image](doc/scan_qr_code.png)

And copy the JSON ouput that looks like:
```json
{"jeton":"XXXXXXXXXXX[...]XXXXXXXXXXXXXX","login":"YYYYYYYYYYYYYY","url":"https://[id of your school].index-education.net/pronote/..."}
```

Paste it, and enter the PIN code used for the generation:  
![image](doc/config_flow_qr_code.png)

### Parent account

If using a Parent account, you'll have to select the child you want to add:  
![image](doc/config_flow_parent.png)

## Usage

This integration provides several sensors, always prefixed with `pronote_LASTNAME_FIRSTNAME` (where `LASTNAME` and `FIRSTNAME` are replaced), for example `sensor.pronote_LASTNAME_FIRSTNAME_today_s_timetable`.


| Sensor                                    | Description                                 |
|-------------------------------------------|---------------------------------------------|
| `sensor.pronote_LASTNAME_FIRSTNAME_class` | basic informations about your child's class |
| `[...]_today_s_timetable`                 | today's timetable                           |
| `[...]_tomorrow_s_timetable`              | tomorrow's timetable                        |
| `[...]_next_day_s_timetable`              | next school day timetable                   |
| `[...]_period_s_timetable`                | timetable for next 15 days                  |
| `[...]_timetable_ical_url`                | iCal URL for the timetable (if available)   |
| `[...]_grades`                            | latest grades                               |
| `[...]_homework`                          | homework                                    |
| `[...]_period_s_homework`                 | homework for max 15 days                    |
| `[...]_absences`                          | absences                                    |
| `[...]_evaluations`                       | evaluations                                 |
| `[...]_averages`                          | averages                                    |
| `[...]_punishments`                       | punishments                                 |
| `[...]_delays`                            | delays                                      |
| `[...]_information_and_surveys`           | information_and_surveys                     |
| `[...]_menus`                             | menus (if available)                        |
| `[...]_overall_average`                   | overall average                             |

The sensors are updated every 15 minutes.

## Cards

Cards are available here: https://github.com/delphiki/lovelace-pronote
