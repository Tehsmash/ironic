#    Copyright 2014, Cisco Systems.

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Ironic Cisco UCSM interfaces.
Provides basic power control of servers managed by Cisco UCSM using PyUcs Sdk.
Provides vendor passthru methods for Cisco UCSM specific functionality.
"""

from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.openstack.common import log as logging

import helper

LOG = logging.getLogger(__name__)


class Power(base.PowerInterface):
    """Cisco Power Interface.

    This PowerInterface class provides a mechanism for controlling the power
    state of servers managed by Cisco UCSM.
    """

    def get_properties(self):
        return helper.COMMON_PROPERTIES

    def validate(self, task):
        """Check that node 'driver_info' is valid.

        Check that node 'driver_info' contains the required fields.

        :param node: Single node object.
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        """
        ucs_helper = helper.CiscoIronicDriverHelper()
        ucs_helper._parse_driver_info(task)
        del ucs_helper

    def get_power_state(self, task):
        """Get the current power state.
        Poll the host for the current power state of the node.
        :param task: A instance of `ironic.manager.task_manager.TaskManager`.
        :param node: A single node.
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        :raises: ServiceUnavailable on an error from SeaMicro Client.
        :returns: power state. One of :class:`ironic.common.states`.
        """
        ucs_helper = helper.CiscoIronicDriverHelper()
        ucs_helper.connect_ucsm(task)
        power_state = ucs_helper._get_power_state(task)
        ucs_helper.logout()
        del ucs_helper
        return power_state

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, pstate):
        """Turn the power on or off.
        Set the power state of a node.
        :param task: A instance of `ironic.manager.task_manager.TaskManager`.
        :param node: A single node.
        :param pstate: Either POWER_ON or POWER_OFF from :class:
            `ironic.common.states`.
        :raises: InvalidParameterValue if an invalid power state was specified.
        :raises: PowerStateFailure if the desired power state couldn't be set.
        """

        if pstate in [states.POWER_ON, states.POWER_OFF]:
            ucs_helper = helper.CiscoIronicDriverHelper()
            ucs_helper.connect_ucsm(task)
            state = ucs_helper.set_power_status(task, pstate)
            ucs_helper.logout()
        else:
            raise exception.InvalidParameterValue(_(
                "set_power_state called with invalid power state."))

        if state != pstate:
            raise exception.PowerStateFailure(pstate=pstate)

    @task_manager.require_exclusive_lock
    def reboot(self, task):
        """Cycles the power to a node.

        :param task: a TaskManager instance.
        :param node: An Ironic node object.
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        :raises: PowerStateFailure if the final state of the node is not
            POWER_ON.
        """
        ucs_helper = helper.CiscoIronicDriverHelper()
        ucs_helper.connect_ucsm(task)
        state = ucs_helper._reboot(task)
        LOG.error("in reboot : %s" % state)
        ucs_helper.logout()

        if state != states.POWER_ON:
            raise exception.PowerStateFailure(pstate=states.POWER_ON)
