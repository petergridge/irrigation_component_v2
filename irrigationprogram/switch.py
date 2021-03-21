
import logging
import asyncio
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)

from .const import (
    DOMAIN,
    ATTR_ICON_WATER,
    ATTR_ICON_WAIT,
    ATTR_ICON_OFF,
    DFLT_ICON_WATER,
    DFLT_ICON_WAIT,
    DFLT_ICON_OFF,
    CONST_SWITCH,
#    ATTR_FRIENDLY_NAME,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_WATER,
    ATTR_WAIT,
    ATTR_REPEAT,
    ATTR_SWITCH,
    ATTR_REMAINING
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON
)


SWITCH_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
        vol.Required(ATTR_FRIENDLY_NAME): cv.string,
        vol.Required(ATTR_WATER): cv.entity_domain('input_number'),
        vol.Optional(ATTR_WAIT): cv.entity_domain('input_number'),
        vol.Optional(ATTR_REPEAT): cv.entity_domain('input_number'),
        vol.Required(ATTR_SWITCH): cv.entity_domain('switch'),
        vol.Optional(ATTR_ICON_WATER,default=DFLT_ICON_WATER): cv.icon,
        vol.Optional(ATTR_ICON_WAIT,default=DFLT_ICON_WAIT): cv.icon,
        vol.Optional(ATTR_ICON_OFF,default=DFLT_ICON_OFF): cv.icon,
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
        water                   = device_config.get(ATTR_WATER)
        wait                    = device_config.get(ATTR_WAIT)
        repeat                  = device_config.get(ATTR_REPEAT)
        switch                  = device_config.get(ATTR_SWITCH)
        icon_water              = device_config.get(ATTR_ICON_WATER)
        icon_wait               = device_config.get(ATTR_ICON_WAIT)
        icon_off                = device_config.get(ATTR_ICON_OFF)
        unique_id               = device_config.get(CONF_UNIQUE_ID)

        switches.append(
            IrrigationZone(
                hass,
                device,
                friendly_name,
                water,
                wait,
                repeat,
                switch,
                icon_water,
                icon_wait,
                icon_off,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the irrigation switches."""
    async_add_entities(await _async_create_entities(hass, config))


class IrrigationZone(SwitchEntity):
    """Representation of an Irrigation zone."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        water,
        wait,
        repeat,
        switch,
        icon_water,
        icon_wait,
        icon_off,
        unique_id,
    ):

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )

        """Initialize a Irrigation program."""
        self._name       = friendly_name
        self._switch     = switch
        self._water      = water
        self._wait       = wait
        self._repeat     = repeat
        self._state      = False
        self._icon_water = icon_water
        self._icon_wait  = icon_wait
        self._icon_off   = icon_off
        self._icon       = self._icon_off
        self._stop       = False
        self._runtime    = 0
        self._state_attributes = None
        self._unique_id  = unique_id
        self._device_id  = device_id

    async def async_added_to_hass(self):

        await super().async_added_to_hass()

        """ house keeping to help ensure solenoids are in a safe state """
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_turn_off())
        return True

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

        if self._icon_state == ATTR_ICON_OFF:
            icon = self._icon_off
        elif self._icon_state == ATTR_ICON_WAIT:
            icon = self._icon_wait
        else:
            icon = self._icon_water
        setattr(self, '_icon', icon)


    async def async_turn_on(self, **kwargs):

        DATA = {'ignore': self._device_id}
        await self.hass.services.async_call(DOMAIN,
                                            'stop_zones',
                                            DATA)

        step = 1
        self._stop = False

        x = '{{ states("' + self._water + '")}}'
        x = cv.template(x)
        x.hass = self.hass
        z_water = int(float(x.async_render()))

        z_wait = 0
        if self._wait is not None:
            x = '{{ states("' + self._wait + '")}}'
            x = cv.template(x)
            x.hass = self.hass
            z_wait = int(float(x.async_render()))

        z_repeat = 1
        if self._repeat is not None:
            x = '{{ states("' + self._repeat + '")}}'
            x = cv.template(x)
            x.hass = self.hass
            z_repeat = int(float(x.async_render()))
            if z_repeat == 0:
                z_repeat = 1

        self._runtime = (((z_water + z_wait) * z_repeat) - z_wait) * 60

        """ run the watering cycle, water/wait/repeat """
        DATA = {ATTR_ENTITY_ID: self._switch}
        for i in range(z_repeat, 0, -1):
            if self._stop == True:
                self._state = False
                break

            self._state = False
            self.async_schedule_update_ha_state(True)
            DATA = {ATTR_ENTITY_ID: self._switch}
            await self.hass.services.async_call(CONST_SWITCH,
                                                SERVICE_TURN_ON,
                                                DATA)

            water = z_water * 60
            for w in range(0,water, step):
                self._runtime = self._runtime - step
                ATTRS = {ATTR_REMAINING:self._runtime}
                setattr(self, '_state_attributes', ATTRS)
                self._state = True
                self.async_schedule_update_ha_state()
                self._icon_state = ATTR_ICON_WATER
                await asyncio.sleep(step)
                if self._stop == True:
                    break

            """ turn the switch entity off """
            if z_wait > 0 and i > 1:
                if self._stop == True:
                    self._state = False
                    break
                """ Eco mode is enabled """
                self.async_schedule_update_ha_state(True)
                await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_OFF,
                                                    DATA)

                wait = z_wait * 60
                for w in range(0,wait, step):
                    self._runtime = self._runtime - step
                    ATTRS = {ATTR_REMAINING:self._runtime}
                    setattr(self, '_state_attributes', ATTRS)
                    self._state = True
                    self._icon_state = ATTR_ICON_WAIT
                    self.async_schedule_update_ha_state()
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break
                self._eco = False

            if i <= 1:
                """ last/only cycle """
                self._state = False
                await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_OFF,
                                                    DATA)

        self._state = False
        self._icon_state = ATTR_ICON_OFF
        self._runtime = 0
        ATTRS = {ATTR_REMAINING:self._runtime}
        setattr(self, '_state_attributes', ATTRS)
        self.async_schedule_update_ha_state(True)


    async def async_turn_off(self, **kwargs):
        if self._state == True:
            self._stop = True
            DATA = {ATTR_ENTITY_ID: self._switch}
            await self.hass.services.async_call(CONST_SWITCH,
                                                SERVICE_TURN_OFF,
                                                DATA)
            self._state = False
            self.async_schedule_update_ha_state()
