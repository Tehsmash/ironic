#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import socket

from oslo_config import cfg

from ironic.common import neutron
from ironic.common import utils
from ironic.drivers import base
from ironic.drivers.modules.network import common


CONF = cfg.CONF


def _device_exists(device):
    """Check if ethernet device exists."""
    return os.path.exists('/sys/class/net/%s' % device)


def _delete_net_dev(dev):
    if _device_exists(dev):
        utils.execute('ip', 'link', 'delete', dev, run_as_root=True,
                      check_exit_code=[0, 2, 254])


def _create_ovs_vif(bridge, dev, iface_id, mac,
                    interface_type=None):
    cmd = ['ovs-vsctl', '--', '--if-exists', 'del-port', dev, '--',
           'add-port', bridge, dev,
           '--', 'set', 'Interface', dev,
           'external-ids:iface-id=%s' % iface_id,
           'external-ids:iface-status=active',
           'external-ids:attached-mac=%s' % mac]
    if interface_type:
        cmd += ['type=%s' % interface_type]
    utils.execute(*cmd, run_as_root=True)


def _remove_ovs_vif(bridge, dev):
    utils.execute('ovs-vsctl', '--if-exists', 'del-port', dev,
                  run_as_root=True)


def _get_bridge_name(iface_id):
    name = iface_id.split('-')[0]
    return "irbr-%s" % name


def _delete_linux_bridge(iface_id):
    name = _get_bridge_name(iface_id)
    if not _device_exists(name):
        return
    utils.execute('ip', 'link', 'set', name, 'down', run_as_root=True)
    utils.execute('brctl', 'delbr', name, run_as_root=True)


def _create_linux_bridge(iface_id):
    name = _get_bridge_name(iface_id)
    if _device_exists(name):
        return

    utils.execute('brctl', 'addbr', name, run_as_root=True)
    utils.execute('ip', 'link', 'set', name, 'up', run_as_root=True)


def _veth_names(iface_id):
    name = iface_id.split('-')[0]
    return "irp1-%s" % name, "irp2-%s" % name


def _create_veth_pair(iface_id):
    dev1_name, dev2_name = _veth_names(iface_id)

    for dev in [dev1_name, dev2_name]:
        _delete_net_dev(dev)

    utils.execute('ip', 'link', 'add', dev1_name, 'type', 'veth', 'peer',
                  'name', dev2_name, run_as_root=True)
    for dev in [dev1_name, dev2_name]:
        utils.execute('ip', 'link', 'set', dev, 'up', run_as_root=True)
        utils.execute('ip', 'link', 'set', dev, 'promisc', 'on',
                      run_as_root=True)


def _create_vlan_subinterface(dev, vlan):
    name = '%s.%s' % (dev, vlan)
    utils.execute('ip', 'link', 'add', 'link', dev, 'name',
                  name, 'type', 'vlan', 'id', vlan,
                  run_as_root=True)
    utils.execute('ip', 'link', 'set', name, 'up', run_as_root=True)


def _add_iface_to_bridge(bridge, iface):
    utils.execute('brctl', 'addif', bridge, iface, run_as_root=True)


class OVSNetwork(base.NetworkInterface, neutron.NeutronNetworkInterfaceMixin):
    """OVS network interface."""

    def __init__(self):
        super(OVSNetwork, self).__init__()
        self.host_name = socket.gethostname()

    def validate(self, task):
        """Validates the network interface.

        :param task: a TaskManager instance.
        :raises: InvalidParameterValue, if the network interface configuration
            is invalid.
        :raises: MissingParameterValue, if some parameters are missing.
        """
        self.get_cleaning_network_uuid()
        self.get_provisioning_network_uuid()

    def port_changed(self, task, port_obj):
        """Handle any actions required when a port changes

        :param task: a TaskManager instance.
        :param port_obj: a changed Port object.
        :raises: Conflict, FailedToUpdateDHCPOptOnPort
        """
        pass

    def portgroup_changed(self, task, portgroup_obj):
        """Handle any actions required when a portgroup changes

        :param task: a TaskManager instance.
        :param portgroup_obj: a changed Portgroup object.
        :raises: Conflict, FailedToUpdateDHCPOptOnPort
        """
        pass

    def vif_attach(self, task, vif_info):
        """Attach a virtual network interface to a node

        :param task: A TaskManager instance.
        :param vif_info: a dictionary of information about a VIF.
            It must have an 'id' key, whose value is a unique
            identifier for that VIF.
        :raises: NetworkError, VifAlreadyAttached, NoFreePhysicalPorts
        """
        vif_id = vif_info['id']
        physnets = set()
        port_like_obj = (
            common.get_free_port_like_object(task, vif_id, physnets))

        neutron.update_port_address(vif_id, port_like_obj.address)

        int_info = port_like_obj.internal_info
        int_info[common.TENANT_VIF_KEY] = vif_id
        port_like_obj.internal_info = int_info
        port_like_obj.save()

    def vif_detach(self, task, vif_id):
        """Detach a virtual network interface from a node

        :param task: A TaskManager instance.
        :param vif_id: A VIF ID to detach
        :raises: NetworkError, VifNotAttached
        """
        for port_like_obj in task.ports:
            int_info = port_like_obj.internal_info
            if int_info[common.TENANT_VIF_KEY] == vif_id:
                del int_info[common.TENANT_VIF_KEY]
            port_like_obj.internal_info = int_info
            port_like_obj.save()

    def vif_list(self, task):
        """List attached VIF IDs for a node.

        :param task: A TaskManager instance.
        :returns: List of VIF dictionaries, each dictionary will have an 'id'
            entry with the ID of the VIF.
        """
        vifs = []
        for port_like_obj in task.ports:
            vif = port_like_obj.internal_info.get(common.TENANT_VIF_KEY)
            if vif:
                vifs.append({'id': vif})
        return vifs

    def get_current_vif(self, task, p_obj):
        """Returns the currently used VIF associated with port or portgroup

        We are booting the node only in one network at a time, and presence of
        cleaning_vif_port_id means we're doing cleaning, of
        provisioning_vif_port_id - provisioning.
        Otherwise it's a tenant network

        :param task: A TaskManager instance.
        :param p_obj: Ironic port or portgroup object.
        :returns: VIF ID associated with p_obj or None.
        """
        return (p_obj.internal_info.get('cleaning_vif_port_id') or
                p_obj.internal_info.get('provisioning_vif_port_id') or
                p_obj.internal_info.get(common.TENANT_VIF_KEY) or
                p_obj.extra.get('vif_port_id') or None)

    def _plumb_vif_for_port(self, vif, port):
        _create_linux_bridge(vif)
        _create_veth_pair(vif)
        _create_vlan_subinterface(port.extra['interface'],
                                  port.extra['private_vlan'])
        _add_iface_to_bridge(_get_bridge_name(vif),
                             "%s.%s" % (port.extra['interface'],
                                        port.extra['private_vlan']))
        _add_iface_to_bridge(_get_bridge_name(vif), _veth_names(vif)[0])
        _create_ovs_vif("br-int", _veth_names(vif)[1], vif, port.address)

    def _unplumb_vif_for_port(self, vif, port):
        _delete_linux_bridge(vif)
        _delete_net_dev(_veth_names(vif)[0])
        _delete_net_dev("%s.%s" % (port.extra['interface'],
                                   port.extra['private_vlan']))
        _remove_ovs_vif('br-int', _veth_names(vif)[1])

    def add_provisioning_network(self, task):
        """Add the provisioning network to a node.

        :param task: A TaskManager instance.
        """
        client = neutron.get_client()

        for port in task.ports:
            if not port.pxe_enabled:
                continue
            body = {
                'port': {
                    'network_id': self.get_provisioning_network_uuid(),
                    'admin_state_up': True,
                    'device_owner': 'baremetal:none',
                    'mac_address': port.address
                }
            }
            neutron_port = client.create_port(body)
            vif = neutron_port['port']['id']

            self._plumb_vif_for_port(vif, port)

            body = {
                'port': {
                    'binding:host_id': self.host_name,
                }
            }
            client.update_port(neutron_port['port']['id'], body)
            internal_info = port.internal_info
            internal_info['provisioning_vif_port_id'] = (
                neutron_port['port']['id'])
            port.internal_info = internal_info
            port.save()

    def remove_provisioning_network(self, task):
        """Remove the provisioning network from a node.

        :param task: A TaskManager instance.
        """
        client = neutron.get_client()
        for port in task.ports:
            vif = port.internal_info.get('provisioning_vif_port_id')
            if not vif:
                continue
            client.delete_port(vif)

            self._unplumb_vif_for_port(vif, port)

            internal_info = port.internal_info
            del internal_info['provisioning_vif_port_id']
            port.internal_info = internal_info
            port.save()

    def configure_tenant_networks(self, task):
        """Configure tenant networks for a node.

        :param task: A TaskManager instance.
        """
        client = neutron.get_client()

        for port in task.ports:
            vif = port.internal_info.get(common.TENANT_VIF_KEY)
            if not vif:
                continue
            self._plumb_vif_for_port(vif, port)
            body = {
                'port': {
                    'binding:host_id': self.host_name,
                }
            }
            client.update_port(vif, body)

    def unconfigure_tenant_networks(self, task):
        """Unconfigure tenant networks for a node.

        :param task: A TaskManager instance.
        """
        for port in task.ports:
            vif = port.internal_info.get(common.TENANT_VIF_KEY)
            if not vif:
                continue
            neutron.unbind_neutron_port(vif)
            self._unplumb_vif_for_port(vif, port)

    def add_cleaning_network(self, task):
        """Add the cleaning network to a node.

        :param task: A TaskManager instance.
        """
        client = neutron.get_client()

        self.remove_provisioning_network(task)

        for port in task.ports:
            if not port.pxe_enabled:
                continue
            body = {
                'port': {
                    'network_id': self.get_cleaning_network_uuid(),
                    'admin_state_up': True,
                    'device_owner': 'baremetal:none',
                    'mac_address': port.address
                }
            }
            neutron_port = client.create_port(body)
            vif = neutron_port['port']['id']

            self._plumb_vif_for_port(vif, port)

            body = {
                'port': {
                    'binding:host_id': self.host_name,
                }
            }
            client.update_port(neutron_port['port']['id'], body)
            internal_info = port.internal_info
            internal_info['cleaning_vif_port_id'] = neutron_port['port']['id']
            port.internal_info = internal_info
            port.save()

    def remove_cleaning_network(self, task):
        """Remove the cleaning network from a node.

        :param task: A TaskManager instance.
        """
        client = neutron.get_client()
        for port in task.ports:
            vif = port.internal_info.get('cleaning_vif_port_id')
            if not vif:
                continue
            client.delete_port(vif)

            self._unplumb_vif_for_port(vif, port)

            internal_info = port.internal_info
            del internal_info['cleaning_vif_port_id']
            port.internal_info = internal_info
            port.save()
