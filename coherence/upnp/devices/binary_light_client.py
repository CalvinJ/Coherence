# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from .basics import BasicClient
from ..services.clients.switch_power_client import SwitchPowerClient

class BinaryLightClient(BasicClient):
    logCategory = 'binarylight_client'

    _service_definition = (
        ('switch_power', SwitchPowerClient, True,
         ["urn:schemas-upnp-org:service:SwitchPower:1"]),
        )
