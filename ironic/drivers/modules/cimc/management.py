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

"""
Ironic Cisco UCSM interfaces.
Provides Management interface operations of servers managed by Cisco UCSM using
PyUcs Sdk.
"""

from oslo_log import log as logging
from oslo_utils import importutils

from ironic.common import boot_devices
from ironic.drivers import base
from ironic.drivers.modules.cimc import common

imcsdk = importutils.try_import('ImcSdk')

LOG = logging.getLogger(__name__)

CIMC_TO_IRONIC_BOOT_DEVICE = {
    'storage-read-write': boot_devices.DISK,
    'lan-read-only': boot_devices.PXE,
    'vm-read-only': boot_devices.CDROM
}

IRONIC_TO_CIMC_BOOT_DEVICE = {
    boot_devices.DISK: ('lsbootStorage', 'storage-read-write',
                        'storage', 'read-write'),
    boot_devices.PXE: ('lsbootLan', 'lan-read-only',
                       'lan', 'read-only'),
    boot_devices.CDROM: ('lsbootVirtualMedia', 'vm-read-only',
                         'virtual-media', 'read-only')
}


class UcsManagement(base.ManagementInterface):

    def get_properties(self):
        return common.COMMON_PROPERTIES

    def validate(self, task):
        common.parse_driver_info(task.node)

    def get_supported_boot_devices(self):
        return list(CIMC_TO_IRONIC_BOOT_DEVICE.values())

    def get_boot_device(self, task):
        with common.cimc_handle(task) as handle:
            method = imcsdk.ImcCore.ExternalMethod("ConfigResolveClass")
            method.Cookie = handle.cookie
            method.InDn = "sys/rack-unit-1"
            method.InHierarchical = "true"
            method.ClassId = "lsbootDef"

            resp = handle.xml_query(method, imcsdk.WriteXmlOption.DIRTY)
            bootDevs = resp.OutConfigs.child[0].child

            ordered = {}
            for dev in bootDevs:
                try:
                    ordered[int(dev.Order)] = dev
                except (ValueError, AttributeError):
                    pass
            first_device = ordered.get(1)

            boot_device = None
            if first_device:
                boot_device = CIMC_TO_IRONIC_BOOT_DEVICE.get(first_device.Rn)

            persistent = True
            if boot_device is None:
                persistent = None
            return {'boot_device': boot_device, 'persistent': persistent}

    def set_boot_device(self, task, device, persistent=False):
        with common.cimc_handle(task) as handle:
            dev = IRONIC_TO_CIMC_BOOT_DEVICE[device]

            method = imcsdk.ImcCore.ExternalMethod("ConfigConfMo")
            method.Cookie = handle.cookie
            method.Dn = "sys/rack-unit-1/boot-policy"
            method.InHierarchical = "true"

            config = imcsdk.Imc.ConfigConfig()

            bootMode = imcsdk.ImcCore.ManagedObject(dev[0])
            bootMode.set_attr("access", dev[3])
            bootMode.set_attr("type", dev[2])
            bootMode.set_attr("Rn", dev[1])
            bootMode.set_attr("order", "1")

            config.add_child(bootMode)
            method.InConfig = config

            handle.xml_query(method, imcsdk.WriteXmlOption.DIRTY)

    def get_sensors_data(self, task):
        raise NotImplementedError()
