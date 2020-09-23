# irrigation_component_v2
Home assistant custom component based on template switches optimised to use inputs from lovelace to configure

The driver for this project is to provide an easy to configure user interface for a non technical user. the goal is that once the inital configuration is done all the features can be modified through lovelace cards without needing to touch any yaml.

While this leads to a small reduction in flexibility from the initial project the usability and clean interface attempt to mirror a standard irrigation controller.

# Irrigation
![Irrigation|690x469,50%](irrigation.PNG)
The irrigation component provides the capability to control your irrigation solenoids.

When starting up or powering down the defined switches are turned off to help prevent a solenoid being left on accidentally as a result of your home assistant server having a power outage.

Water can occur in an Eco mode where a water/wait/repeat cycle is run to minimise run off by letting water soak as a result of several short watering cycles.

Only one program can run at a time to prevent multiple solenoids being activated. If programs overlap the running program will be stopped.

Templates are used to monitor conditions to initiate watering. For programs this can be used to run on specific days or every 3 days or to prevent watering based on a sensor state. For zones this can be used so rules can be applied to individual zones allowing watering to occur in a covered area, or not occur if it is very windy the options are endless.

All the inputs of the new platforms are home assistant entities so the start time is provided via a input_date_time entity.

All the information provided is used to define a template internally that triggers the irrigate action according to the inputs provided.

The component creates two switch platform types
* irrigationprogram - to represent a program
  - The irrigation entity stores the last run day.
  - The list of zones to run in this program.
  - binary sensor definition for a rain sensor
* irrigationzone - to represent zones
  - The irrigation_zone provides the link to a switch entity to control a solenoid.
  - The length of time to water.
  - Has attribute defining remaining run time.

## INSTALLATION
### To create a working sample
* Copy the following program and zone folders to the ‘config/custom components/’ directory 
* Copy the 'irrigation.yaml' file to the packages directory or configuration.yaml
* Copy the 'dummyzones.yaml' file to the packages directory of configuration yaml. This will provide dummy implementation of switches to represent solenoids.
* In Lovelace create a 'manual' card and copy the contents of the 'lovelace.yaml' file

## CONFIGURATION
An irrigation section must be present in the configuration.yaml file that specifies the irrigation programs, zones and the switches attached:
### Example configuration.yaml entry
```yaml
switch:
  - platform: irrigationzone
    switches:
      pot_plants:
        friendly_name: Pot Plants
        water: input_number.irrigation_pot_plants_run
        wait: input_number.irrigation_pot_plants_wait
        repeat: input_number.irrigation_pot_plants_repeat
        switch_entity: switch.irrigation_solenoid_01
        icon_off: 'mdi:flower'

  - platform: irrigationprogram
    switches: 
      morning:
        friendly_name: Morning
        irrigation_on: input_boolean.irrigation_on
        start_time: input_datetime.irrigation_morning_start_time
        run_freq: input_select.irrigation_freq
    #    run_days: input_select.irrigation_run_days
        rain_sensor: binary_sensor.irrigation_rain_sensor
        ignore_rain_sensor: input_boolean.irrigation_ignore_rain_sensor
        icon: mdi:fountain
        zones:
          - zone: switch.pot_plants
          - zone: switch.front_lawn
```
## CONFIGURATION VARIABLES

## program
*(string)(Required)* the switch entity.
#### friendly_name
*(string)(Required)* This is the name given to the irrigation entity.
#### start_time
*(template)(Required)* Allows a value template to define when watering occurs on the program. Watering will occur when the template evaluates to True.
#### run_freq or run_days
*(input_select)(Optional)* This will set how often the irrigation will run.
##### run_freq
*(input_select)* A numeric value that represent the frequency to water, 1 is daily
##### run_days
*(input_select)* The selected option should provide a list days to run, 'Sun','Thu' will run on Sunday and Thursday
#### irrigation_on
*(input_boolean)(Optional)* Attribute to temproarily disable the watering schedule
#### Zones 
*(list)(Required)* the list of zones to water.
#### zone
*(entity)(Required)* This is the name given to the irrigation_zone entity.



## zones
*(list)(Required)* a list of zone to operate.
#### name
*(string)(Required)* This is the name given to the irrigation_zone entity.
#### water
*(int)(Required)* This it the period that the zone will turn the switch_entity on for. Range 1 to 30 minutes.
#### wait
*(int)(Optional)* This provides for an Eco capability implementing a cycle of water/wait/repeat to allow water to soak into the soil. Range 1 to 30 minutes.
#### repeat
*(int)(Optional)* This is the number of cycles to run water/wait. Range 1 to 30.
#### template
*(template)(Optional)* Allows a value_template to defer watering on a zone. If defined watering will occur when the template evaluates to True.
#### switch_entity
*(entity)(Required)* The switch to operate when the zone is triggered.
#### icon_on
*(icon)(Optional)* This will replace the default icon mdi:water.
#### icon_off
*(icon)(Optional)* This will replace the default icon mdi:water-off.
#### icon_wait
*(icon)(Optional)* This will replace the default icon mdi:timer-sand.

## SERVICES
```yaml
run_program:
    description: Run a defined irrigation program.
    fields:
        entity_id:
            description: The program to manually run, template evaluation is ignored.
            example: 'irrigation.morning'

irrigationprog.stop_programs:
    description: Stop any running programs or stations.
```

## TEMPLATE EXAMPLES
Both of these templates provide the same result for watering on defined days.
```yaml
"{{ now().weekday() in [0,2,4,6] }}"
"{{ now().strftime('%a') in ['Mon','Wed','Fri','Sun'] }}"
```
Water every three days at 7:30am.
```yaml
"{{ states('sensor.time') == '07:30' and state_attr('irrigation.morning', 'days_since') > 2 }}"
```

Check sensor values.
```yaml
{{ states('sensor.time') == '07:30' and now().weekday() in [0,1,2,3,4,5,6] and states('binary_sensor.is_wet') == 'off' }}
{{ states('sensor.time') == '07:30' and is_state('binary_sensor.is_wet','off') }}
{{ states('sensor.time') == '07:30' and states('binary_sensor.is_wet') == 'off' }}
```
## ESPHOME
An example ESPHOME configuration file is included in the repository this example utilises:
* ESP8266 
* PCF8575 - I2C IO expander for up to 16 solenoids
* BME280 - temperature, pressure and humidity sensor
* Moisture Sensor - analogue/digital moisture sensor

## REVISION HISTORY
0.1
•	Initial release
0.2
•	template based
•	time remaining countdown


