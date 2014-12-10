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
from ironic.drivers import base
from ironic.openstack.common import log as logging

import helper

LOG = logging.getLogger(__name__)

VENDOR_PASSTHRU_METHODS = [
    'launch_kvm', 'get_location',
    'get_inventory', 'get_faults',
    'get_temperature_stats',
    'get_power_stats', 'get_firmware_version'
    ]

DRIVER_VENDOR_PASSTHRU_METHODS = ['enroll_nodes']


class VendorPassthru(base.VendorInterface):
    """Cisco vendor-specific methods."""

    def get_properties(self):
        return helper.COMMON_PROPERTIES

    def validate(self, task, **kwargs):
        method = kwargs['method']
        if method in VENDOR_PASSTHRU_METHODS:
            return True
        else:
            raise exception.InvalidParameterValue(_(
                "Unsupported method (%s) passed to Cisco driver.")
                % method)

    def vendor_passthru(self, task, **kwargs):
        """Dispatch vendor specific method calls."""
        method = kwargs['method']
        if method in VENDOR_PASSTHRU_METHODS:
            return getattr(self, "_" + method)(task, **kwargs)

    def driver_vendor_passthru(self, context, method, **kwargs):
        """pxe_ucsm driver level vedor_passthru."""

        if method in DRIVER_VENDOR_PASSTHRU_METHODS:
            return getattr(self, "_" + method)(context, **kwargs)

    def _get_location(self, task, **kwargs):
        """Retrieve the server id."""
        ucs_helper = helper.CiscoIronicDriverHelper()
        location = None
        try:
            ucs_helper.connect_ucsm(task)
            location = ucs_helper.get_location(task)
        except Exception as ex:
            LOG.error("Cisco driver: failed to get node location")
            raise exception.IronicException("Failed to get ManagedObject (%s)"
                      % (ex))
        finally:
            ucs_helper.logout()
            del ucs_helper
        LOG.error(location)
        return location

    def _get_inventory(self, task, **kwargs):
        """Gets inventory of the server."""
        ucs_helper = helper.CiscoIronicDriverHelper()
        inventory = None

        try:
            inventory = ucs_helper.get_inventory(task)
        except Exception as ex:
            raise exception.IronicException("Cisco driver:"
                "Failed to get node inventory (%s), msg (%s)"
                % (task.node.uuid, ex))
        finally:
            ucs_helper.logout()
            del ucs_helper
        LOG.error(inventory)
        return inventory

    def _get_faults(self, task, **kwargs):
        """Gets faults of the server.
        """
        ucs_helper = helper.CiscoIronicDriverHelper()
        faults = {}
        try:
            faults = ucs_helper.get_faults(task)
        except Exception as ex:
            LOG.error("Cisco driver: Failed to get temperature stats for node"
                "(%s)" % (task.node.uuid))
            raise exception.IronicException("Cisco driver:"
                "failed to get temperature stats for node (%s), msg:(%s)"
                % (task.node.uuid, ex))
        finally:
            ucs_helper.logout()
            del ucs_helper
        LOG.error(faults)
        return faults

    def _get_temperature_stats(self, task, **kwargs):
        """Gets temperature stats of the server.
        """
        ucs_helper = helper.CiscoIronicDriverHelper()
        temperature_stats = {}
        try:
            temperature_stats = ucs_helper.get_temperature_stats(task)
        except Exception as ex:
            LOG.error("Cisco driver: Failed to get temperature stats for node"
                "(%s)" % (task.node.uuid))
            raise exception.IronicException("Cisco driver:"
                "failed to get temperature stats for node (%s), msg:(%s)"
                % (task.node.uuid, ex))
        finally:
            ucs_helper.logout()
            del ucs_helper

        LOG.error(temperature_stats)
        return temperature_stats

    def _get_power_stats(self, task, **kwargs):
        """Gets power stats of given server."""

        ucs_helper = helper.CiscoIronicDriverHelper()
        power_stats = {}
        try:
            power_stats = ucs_helper.get_power_stats(task)
        except Exception as ex:
            LOG.error("Cisco driver: Failed to get power stats for node"
                "(%s)" % (task.node.uuid))
            raise exception.IronicException("Cisco driver:"
                "failed to get power stats for node (%s), msg:(%s)"
                % (task.node.uuid, ex))
        finally:
            ucs_helper.logout()
            del ucs_helper

        LOG.error(power_stats)
        return power_stats

    def _get_firmware_version(self, task, **kwargs):
        """This method gets the firmware version information."""

        ucs_helper = helper.CiscoIronicDriverHelper()
        firmware_version = None
        try:
            firmware_version = ucs_helper.get_firmware_version(task)
        except Exception:
            LOG.error("Cisco driver: Failed to get firmware version for node"
                "(%s)" % (task.node.uuid))
            raise exception.IronicException("Cisco driver:"
                "failed to get firmware version for node (%s)"
                % (task.node.uuid))
        finally:
            ucs_helper.logout()
            del ucs_helper

        LOG.error(firmware_version)
        return firmware_version

    def _enroll_nodes(self, context, **kwargs):
        """This method enrolls the nodes into ironic DB."""

        LOG.debug(_("UCS driver vendor_passthru enroll nodes"))
        ucs_node = {
            'hostname': kwargs.get('hostname'),
            'username': kwargs.get('username'),
            'password': kwargs.get('password'),
            'qualifier': kwargs.get('qualifier')
            }

        if not ucs_node['hostname']:
            raise exception.InvalidParameterValue(_(
                "Cisco driver_vendor_passthru enroll_nodes requires "
                "hostname be set"))

        if not ucs_node['username'] or not ucs_node['password']:
            raise exception.InvalidParameterValue(_(
                "Cisco driver requires both username and password be set"))

        ucs_helper = helper.CiscoIronicDriverHelper(
                         ucs_node['hostname'],
                         ucs_node['username'],
                         ucs_node['password']
                         )

        try:
            success, handle = helper.generate_ucsm_handle(ucs_node['hostname'],
                    ucs_node['username'], ucs_node['password'], ucs_helper)

            if success:
                ucs_helper.enroll_nodes()
                LOG.error("ucs_helper.handles + %s" % ucs_helper.handles)
            else:
                LOG.error("Authentication failed")
        except exception.IronicException:
            raise exception.IronicException("Cisco client: Failed to get UCS"
                      " Handle")
        finally:
            ucs_helper.logout()
            del ucs_helper
