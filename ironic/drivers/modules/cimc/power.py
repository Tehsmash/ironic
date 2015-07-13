# Copyright 2015, Cisco Systems.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall
from oslo_utils import importutils

from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.drivers.modules.cimc import common

imcsdk = importutils.try_import('ImcSdk')

opts = [
    cfg.IntOpt('max_retry',
               default=6,
               help=_('Number of times a power operation needs to be '
                      'retried')),
    cfg.IntOpt('action_interval',
               default=10,
               help=_('Amount of time in seconds to wait in between power '
                      'operations')),
]

CONF = cfg.CONF
CONF.register_opts(opts, group='cimc')

LOG = logging.getLogger(__name__)

CIMC_TO_IRONIC_POWER_STATE = {
    imcsdk.ComputeRackUnit.CONST_OPER_POWER_ON: states.POWER_ON,
    imcsdk.ComputeRackUnit.CONST_OPER_POWER_OFF: states.POWER_OFF,
}

IRONIC_TO_CIMC_POWER_STATE = {
    states.POWER_ON: imcsdk.ComputeRackUnit.CONST_ADMIN_POWER_UP,
    states.POWER_OFF: imcsdk.ComputeRackUnit.CONST_ADMIN_POWER_DOWN,
    states.REBOOT: 'hard-reset-immediate'  # 'cycle-immediate'
}


def _wait_for_state_change(target_state, task):
    """Wait and check for the power state change."""
    store = {'state': None, 'retries': CONF.cimc.max_retry}

    def _wait(store):

        current_power_state = None
        with common.cimc_handle(task) as handle:
            rack_unit = handle.get_imc_managedobject(
                None, None, params={"Dn": "sys/rack-unit-1"}
            )
            current_power_state = rack_unit[0].get_attr("OperPower")

        store['state'] = CIMC_TO_IRONIC_POWER_STATE.get(current_power_state)

        if store['state'] == target_state:
            raise loopingcall.LoopingCallDone()

        store['retries'] -= 1
        if store['retries'] <= 0:
            store['state'] = states.ERROR
            raise loopingcall.LoopingCallDone()

    timer = loopingcall.FixedIntervalLoopingCall(_wait, store)
    timer.start(interval=CONF.cimc.action_interval).wait()
    return store['state']


class Power(base.PowerInterface):

    def get_properties(self):
        return common.COMMON_PROPERTIES

    def validate(self, task):
        common.parse_driver_info(task.node)

    def get_power_state(self, task):
        current_power_state = None
        with common.cimc_handle(task) as handle:
            rack_unit = handle.get_imc_managedobject(
                None, None, params={"Dn": "sys/rack-unit-1"}
            )
            current_power_state = rack_unit[0].get_attr("OperPower")
        return CIMC_TO_IRONIC_POWER_STATE.get(current_power_state,
                                              states.ERROR)

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, pstate):
        with common.cimc_handle(task) as handle:
            handle.set_imc_managedobject(
                None, class_id="ComputeRackUnit",
                params={
                    imcsdk.ComputeRackUnit.ADMIN_POWER:
                        IRONIC_TO_CIMC_POWER_STATE.get(pstate),
                    imcsdk.ComputeRackUnit.DN: "sys/rack-unit-1"
                })

    @task_manager.require_exclusive_lock
    def reboot(self, task):
        current_power_state = self.get_power_state(task)

        if current_power_state == states.POWER_ON:
            self.set_power_state(task, states.REBOOT)
        elif current_power_state == states.POWER_OFF:
            self.set_power_state(task, states.POWER_ON)

        state = _wait_for_state_change(states.POWER_ON, task)

        if state != states.POWER_ON:
            raise exception.PowerStateFailure(pstate=states.POWER_ON)
