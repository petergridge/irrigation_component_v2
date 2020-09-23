import logging

from .const import (
    DOMAIN,
    CONST_SWITCH,
    SWITCH_ID_FORMAT,
    )


from homeassistant.const import (
    CONF_SWITCHES,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
    )

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):

    platforms = config.get(CONST_SWITCH)

    for x in platforms:
        if x.get('platform') == DOMAIN:
            switches = x.get('switches')
            break

    async def async_stop_zones(call):

        for x in switches:
            if x == call.data.get('ignore',''):
                continue

            device = SWITCH_ID_FORMAT.format(x)
            DATA = {ATTR_ENTITY_ID: device}
            await hass.services.async_call(CONST_SWITCH,
                                     SERVICE_TURN_OFF,
                                     DATA)
    """ END async_stop_zones """

    """ register services """
    hass.services.async_register(DOMAIN,
                                 'stop_zones',
                                 async_stop_zones)

    return True

