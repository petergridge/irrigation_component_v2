
import logging
import asyncio
import voluptuous as vol
from datetime import (datetime) #, timedelta
import homeassistant.util.dt as dt_util

from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change

from homeassistant.helpers.restore_state import (
    RestoreEntity,
)

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)

from .const import (
    DOMAIN,
    SWITCH_ID_FORMAT,
    ATTR_START,
    ATTR_RUN_FREQ,
    ATTR_RUN_DAYS,
    ATTR_IRRIGATION_ON,
    ATTR_RAIN_SENSOR,
    CONST_SWITCH,
    ATTR_NAME,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_ZONES,
    ATTR_ZONE,
    DFLT_ICON,
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
#    STATE_ON,
#    STATE_OFF,
    ATTR_ICON,
    MATCH_ALL,
)


SWITCH_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
        vol.Required(ATTR_FRIENDLY_NAME): cv.string,
        vol.Required(ATTR_START): cv.entity_domain('input_datetime'),
        vol.Exclusive(ATTR_RUN_FREQ,"FRQP"): cv.entity_domain('input_select'),
        vol.Exclusive(ATTR_RUN_DAYS,"FRQP"): cv.entity_domain('input_select'),
        vol.Optional(ATTR_IRRIGATION_ON): cv.entity_domain('input_boolean'),
        vol.Optional(ATTR_RAIN_SENSOR): cv.entity_domain('binary_sensor'),
        vol.Optional(ATTR_IGNORE_RAIN_SENSOR): cv.entity_domain('input_boolean'),
        vol.Optional(ATTR_ICON,default=DFLT_ICON): cv.icon,
        vol.Required(ATTR_ZONES): [{
            vol.Required(ATTR_ZONE): cv.entity_domain(CONST_SWITCH),
        }],
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

_LOGGER = logging.getLogger(__name__)


async def _async_create_entities(hass, config):
    """Create the Template switches."""
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name           = device_config.get(ATTR_FRIENDLY_NAME, device)
        start_time              = device_config.get(ATTR_START)
        run_freq                = device_config.get(ATTR_RUN_FREQ)
        run_days                = device_config.get(ATTR_RUN_DAYS)
        irrigation_on           = device_config.get(ATTR_IRRIGATION_ON)
        rain_sensor             = device_config.get(ATTR_RAIN_SENSOR)
        ignore_rain_sensor      = device_config.get(ATTR_IGNORE_RAIN_SENSOR)
        icon                    = device_config.get(ATTR_ICON)
        zones                   = device_config.get(ATTR_ZONES)
        unique_id               = device_config.get(CONF_UNIQUE_ID)

        switches.append(
            IrrigationProgram(
                hass,
                device,
                friendly_name,
                start_time,
                run_freq,
                run_days,
                irrigation_on,
                rain_sensor,
                ignore_rain_sensor,
                icon,
                zones,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the irrigation switches."""
    async_add_entities(await _async_create_entities(hass, config))


class IrrigationProgram(SwitchEntity, RestoreEntity):
    """Representation of an Irrigation program."""
    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        start_time,
        run_freq,
        run_days,
        irrigation_on,
        rain_sensor,
        ignore_rain_sensor,
        icon,
        zones,
        unique_id,
    ):

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )

        """Initialize a Irrigation program."""
        self._name               = friendly_name
        self._start_time         = start_time
        self._run_freq           = run_freq
        self._run_days           = run_days
        self._irrigation_on      = irrigation_on
        self._rain_sensor        = rain_sensor
        self._ignore_rain_sensor = ignore_rain_sensor
        self._icon               = icon
        self._zones              = zones
        self._state_attributes   = None
        self._state              = False
        self._unique_id          = unique_id
        self._stop               = False
        self._device_id          = device_id
        self._running            = False
        self._last_run           = None
        self._triggered_by_template = False

        """ Build a template from the attributes provided """
        self._template = None
        template = "states('sensor.time') + ':00' == states('" + self._start_time + "') "
        if self._irrigation_on is not None:
            template = template + " and is_state('" + self._irrigation_on + "', 'on') "
        if self._run_days is not None:
            template = template + " and now().strftime('%a') in states('" + self._run_days + "')"
        if self._run_freq is not None:
            template = template + \
                    " and states('" + run_freq + "')|int" + \
                    " == ((as_timestamp(now()) " + \
                    "- as_timestamp(states." + self.entity_id + \
                    ".attributes.last_ran) | int) /86400) | int(0) "

        template = "{{ " + template + " }}"
        template = cv.template(template)
        template.hass = hass
        self._template = template


    @callback
    def _update_state(self, result):
        super()._update_state(result)


    async def async_added_to_hass(self):

        state = await self.async_get_last_state()
        self._last_run     = state.attributes.get('last_ran')

        """ default to today for new programs """
        if self._last_run is None:
            utcnow         = dt_util.utcnow()
            time_date      = dt_util.start_of_local_day(dt_util.as_local(utcnow))
            self._last_run = dt_util.as_local(time_date).date().isoformat()

        ATTRS = {'last_ran':self._last_run}
        setattr(self, '_state_attributes', ATTRS)

        """ house keeping to help ensure solenoids are in a safe state """
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_turn_off())

        @callback
        async def template_check(entity, old_state, new_state):
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            """Update template on startup."""

            async_track_state_change(
                self.hass, 'sensor.time', template_check)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)


        await super().async_added_to_hass()


    @property
    def name(self):
        """Return the name of the variable."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this switch."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state_attributes(self):
        """Return the state attributes.
        Implemented by component base class.
        """
        return self._state_attributes

    async def async_update(self):
        """Update the state from the template."""
        if self._running == False:
            evaluated = 'False'
            evaluated = self._template.async_render()
            if evaluated == 'True':
                self._running = True
                self._triggered_by_template = True
                await self.async_turn_on()


    async def async_turn_on(self, **kwargs):

        """ stop all programs but this one """
        DATA = {'ignore': self._device_id}
        await self.hass.services.async_call(DOMAIN,
                                            'stop_programs',
                                            DATA)

        """ Initialise for stop programs service call """
        self._state = True
        self._stop  = False
        self.async_write_ha_state()

        """ Iterate through all the defined zones """
        for zone in self._zones:
            z_name     = zone.get(ATTR_NAME)
            z_ignore   = zone.get(ATTR_IGNORE_RAIN_SENSOR)
            z_zone     = zone.get(ATTR_ZONE)


            if self._triggered_by_template == True:
                """ assess the rain sensor """
                alt_template = ""
                if self._rain_sensor is not None:
                    alt_template = alt_template + "{{ ( is_state('" + self._rain_sensor + "', 'off') "
                    if  self._ignore_rain_sensor is not None:
                        alt_template = alt_template + " or is_state('" + self._ignore_rain_sensor + "', 'on') "
                    if  z_ignore is not None:
                        alt_template = alt_template + " or is_state('" + z_ignore + "', 'on') "
                    alt_template = alt_template + " ) }}"

                alt_template = cv.template(alt_template)
                alt_template.hass = self.hass
                try:
                    evaluated = alt_template.async_render()
                except:
                    _LOGGER.error('Rain Sensor template %s, invalid: %s',
                                  self._name,
                                  self._template)
                    return

                if evaluated == 'False':
                    #if called from a service-run the program
                    return

            """ evaluates to true - continue watering"""
            self._running = True

            """Update last run date attribute """
            now            = dt_util.utcnow()
            time_date      = dt_util.start_of_local_day(dt_util.as_local(now))
            self._last_run = dt_util.as_local(time_date).date().isoformat()
            ATTRS = {'last_ran':self._last_run}
            setattr(self, '_state_attributes', ATTRS)

            if self._stop == True:
                break

            DATA = {ATTR_ENTITY_ID: z_zone}
            await self.hass.services.async_call(CONST_SWITCH,
                                                SERVICE_TURN_ON,
                                                DATA)

            """ wait until the zone stops """
            step = 1
            await asyncio.sleep(step)
            switch_state = self.hass.states.get(z_zone)
            while switch_state.state == 'on':
                await asyncio.sleep(step)
                switch_state = self.hass.states.get(z_zone)
                if self._stop == True:
                    break
        """ end of for zone loop """

        """Update last run date attribute """
        now            = dt_util.utcnow()
        time_date      = dt_util.start_of_local_day(dt_util.as_local(now))
        self._last_run = dt_util.as_local(time_date).date().isoformat()
        ATTRS = {'last_ran':self._last_run}
        setattr(self, '_state_attributes', ATTRS)

        self._state       = False
        self._running     = False
        self._run_program = None
        self._stop        = False
        self._triggered_by_template = False
        
        self.async_write_ha_state()


    async def async_turn_off(self, **kwargs):

        self._stop = True
        for zone in self._zones:
            z_zone = zone.get(ATTR_ZONE)
            DATA = {ATTR_ENTITY_ID: z_zone}
            await self.hass.services.async_call(CONST_SWITCH,
                                                SERVICE_TURN_OFF,
                                                DATA)

        self._state = False
        self.async_schedule_update_ha_state()
