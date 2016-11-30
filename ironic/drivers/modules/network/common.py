# Copyright 2016 Cisco Systems
# All Rights Reserved
#
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

from neutronclient.common import exceptions as neutron_exceptions
from oslo_config import cfg
from oslo_log import log

from ironic.common import dhcp_factory
from ironic.common import exception
from ironic.common.i18n import _LW
from ironic.common import neutron
from ironic import objects

CONF = cfg.CONF
LOG = log.getLogger(__name__)

TENANT_VIF_KEY = 'tenant_vif_port_id'


class VIFPortIDMixin(object):

    def port_changed(self, task, port_obj):
        """Handle any actions required when a port changes

        :param task: a TaskManager instance.
        :param port: a changed Port object from the API before it is saved.
        :raises: FailedToUpdateDHCPOptOnPort, Conflict
        """
        context = task.context
        node = task.node
        port_uuid = port_obj.uuid
        portgroup_obj = None
        if port_obj.portgroup_id:
            portgroup_obj = [pg for pg in task.portgroups if
                             pg.id == port_obj.portgroup_id][0]
        vif = (port_obj.internal_info.get(TENANT_VIF_KEY) or
               port_obj.extra.get('vif_port_id'))
        if 'address' in port_obj.obj_what_changed():
            if vif:
                api = dhcp_factory.DHCPFactory()
                api.provider.update_port_address(vif, port_obj.address,
                                                 token=context.auth_token)
            # Log warning if there is no vif_port_id and an instance
            # is associated with the node.
            elif node.instance_uuid:
                LOG.warning(_LW(
                    "No VIF found for instance %(instance)s "
                    "port %(port)s when attempting to update port MAC "
                    "address."),
                    {'port': port_uuid, 'instance': node.instance_uuid})

        if 'extra' in port_obj.obj_what_changed():
            original_port = objects.Port.get_by_id(context, port_obj.id)
            updated_client_id = port_obj.extra.get('client-id')
            if (original_port.extra.get('client-id') !=
                updated_client_id):
                vif = (port_obj.internal_info.get(TENANT_VIF_KEY) or
                       port_obj.extra.get('vif_port_id'))
                # DHCP Option with opt_value=None will remove it
                # from the neutron port
                if vif:
                    api = dhcp_factory.DHCPFactory()
                    client_id_opt = {'opt_name': 'client-id',
                                     'opt_value': updated_client_id}

                    api.provider.update_port_dhcp_opts(
                        vif, [client_id_opt], token=context.auth_token)
                # Log warning if there is no vif_port_id and an instance
                # is associated with the node.
                elif node.instance_uuid:
                    LOG.warning(_LW(
                        "No VIF found for instance %(instance)s "
                        "port %(port)s when attempting to update port "
                        "client-id."),
                        {'port': port_uuid,
                         'instance': node.instance_uuid})

        if portgroup_obj and ((set(port_obj.obj_what_changed()) &
                              {'pxe_enabled', 'portgroup_id'}) or vif):
            if ((port_obj.pxe_enabled or vif) and not
                portgroup_obj.standalone_ports_supported):
                msg = (_("Port group %(portgroup)s doesn't support "
                         "standalone ports. This port %(port)s cannot be "
                         " a member of that port group because either "
                         "'extra/vif_port_id' was specified or "
                         "'pxe_enabled' was set to True.") %
                       {"portgroup": portgroup_obj.uuid,
                        "port": port_uuid})
                raise exception.Conflict(msg)

    def vif_list(self, task):
        """List attached VIF IDs for a node

        :param task: A TaskManager instance.
        """
        vifs = []
        for port in task.ports:
            vif_id = port.internal_info.get(
                TENANT_VIF_KEY, port.extra.get('vif_port_id'))
            if vif_id:
                vifs.append({'id': vif_id})
        return vifs

    def vif_attach(self, task, vif):
        """Attach a virtual network interface to a node

        :param task: A TaskManager instance.
        :param vif: A VIF object to attach
        :raises: NetworkError
        """
        vif_id = vif['id']
        # Sort ports by pxe_enabled to ensure we always bind pxe_enabled ports
        # first
        sorted_ports = sorted(task.ports, key=lambda p: p.pxe_enabled,
                              reverse=True)
        free_ports = []
        # Check all ports to ensure this VIF isn't already attached
        for port in sorted_ports:
            port_id = port.internal_info.get(TENANT_VIF_KEY,
                                             port.extra.get('vif_port_id'))
            if port_id is None:
                free_ports.append(port)
            elif port_id == vif_id:
                raise exception.NetworkError(_(
                    "Unable to attach VIF because VIF %(vif)s is already "
                    "attached to Ironic port or portgroup %(port)s") % {
                        "vif": vif_id, "port": port.uuid})

        if not free_ports:
            raise exception.NetworkError(_("Unable to attach VIF %(vif)s, not "
                                           "enough physical ports.") %
                                         {'vif': vif_id})
        # Get first free port
        port = free_ports.pop(0)

        # Check if the requested vif_id is a neutron port. If it is
        # then attempt to update the port's MAC address.
        try:
            client = neutron.get_client(task.context.auth_token)
            client.show_port(vif_id)
        except neutron_exceptions.NeutronClientException:
            # NOTE(sambetts): If a client error occurs this is because either
            # neutron doesn't exist because we're running in standalone
            # environment or we can't find a matching neutron port which means
            # a user might be requesting a non-neutron port. So skip trying to
            # update the neutron port MAC address in these cases.
            pass
        else:
            try:
                neutron.update_port_address(vif_id, port.address)
            except exception.FailedToUpdateMacOnPort:
                raise exception.NetworkError(_(
                    "Unable to attach VIF %(vif)s because Ironic can not "
                    "update Neutron port %(port)s MAC address to match "
                    "physical MAC address %(mac)s") % {
                        'vif': vif_id, 'port': vif_id, 'mac': port.address})

        int_info = port.internal_info
        int_info[TENANT_VIF_KEY] = vif_id
        port.internal_info = int_info
        port.save()

    def vif_detach(self, task, vif_id):
        """Detach a virtual network interface from a node

        :param task: A TaskManager instance.
        :param vif_id: A VIF ID to detach
        :raises: NetworkError
        """
        for port in task.ports:
            # FIXME(sambetts) Remove this when we no longer support a nova
            # driver that uses port.extra
            if (port.extra.get("vif_port_id") == vif_id or
                    port.internal_info.get(TENANT_VIF_KEY) == vif_id):
                int_info = port.internal_info
                extra = port.extra
                int_info.pop(TENANT_VIF_KEY, None)
                extra.pop('vif_port_id', None)
                port.extra = extra
                port.internal_info = int_info
                port.save()
                break
        else:
            raise exception.NetworkError(_(
                "Unable to detach VIF: VIF %(vif_id)s not attached to node "
                "%(node)s") % {'vif_id': vif_id, 'node': task.node.uuid})
