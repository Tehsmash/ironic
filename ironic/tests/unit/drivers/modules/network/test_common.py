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

import mock
from oslo_config import cfg
from oslo_utils import uuidutils

from ironic.common import exception
from ironic.common import neutron as neutron_common
from ironic.conductor import task_manager
from ironic.drivers.modules.network import common
from ironic.tests.unit.conductor import mgr_utils
from ironic.tests.unit.db import base as db_base
from ironic.tests.unit.objects import utils as obj_utils

CONF = cfg.CONF


class TestVifPortIDMixin(db_base.DbTestCase):

    def setUp(self):
        super(TestVifPortIDMixin, self).setUp()
        self.config(enabled_drivers=['fake'])
        mgr_utils.mock_the_extension_manager()
        self.interface = common.VIFPortIDMixin()
        self.node = obj_utils.create_test_node(self.context,
                                               network_interface='neutron')
        self.port = obj_utils.create_test_port(
            self.context, node_id=self.node.id,
            address='52:54:00:cf:2d:32',
            extra={'vif_port_id': uuidutils.generate_uuid(),
                   'client-id': 'fake1'})
        self.neutron_port = {'id': '132f871f-eaec-4fed-9475-0d54465e0f00',
                             'mac_address': '52:54:00:cf:2d:32'}

    def test_vif_list_extra(self):
        vif_id = uuidutils.generate_uuid()
        self.port.extra = {'vif_port_id': vif_id}
        self.port.save()
        with task_manager.acquire(self.context, self.node.id) as task:
            vifs = self.interface.vif_list(task)
            self.assertEqual(vifs, [{'id': vif_id}])

    def test_vif_list_internal(self):
        vif_id = uuidutils.generate_uuid()
        self.port.internal_info = {common.TENANT_VIF_KEY: vif_id}
        self.port.save()
        with task_manager.acquire(self.context, self.node.id) as task:
            vifs = self.interface.vif_list(task)
            self.assertEqual(vifs, [{'id': vif_id}])

    def test_vif_list_extra_and_internal_priority(self):
        vif_id = uuidutils.generate_uuid()
        vif_id2 = uuidutils.generate_uuid()
        self.port.extra = {'vif_port_id': vif_id2}
        self.port.internal_info = {common.TENANT_VIF_KEY: vif_id}
        self.port.save()
        with task_manager.acquire(self.context, self.node.id) as task:
            vifs = self.interface.vif_list(task)
            self.assertEqual(vifs, [{'id': vif_id}])

    @mock.patch.object(neutron_common, 'get_client')
    @mock.patch.object(neutron_common, 'update_port_address')
    def test_vif_attach(self, mock_upa, mock_client):
        self.port.extra = {}
        self.port.save()
        vif = {'id': "fake_vif_id"}
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.vif_attach(task, vif)
            self.port.refresh()
            self.assertEqual(self.port.internal_info.get(
                common.TENANT_VIF_KEY), "fake_vif_id")
            mock_upa.assert_called_once_with("fake_vif_id", self.port.address)

    @mock.patch.object(neutron_common, 'get_client')
    @mock.patch.object(neutron_common, 'update_port_address')
    def test_vif_attach_update_port_exception(self, mock_upa, mock_client):
        self.port.extra = {}
        self.port.save()
        vif = {'id': "fake_vif_id"}
        mock_upa.side_effect = (
            exception.FailedToUpdateMacOnPort(port_id='fake'))
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaisesRegexp(
                exception.NetworkError, "can not update Neutron port",
                self.interface.vif_attach, task, vif)

    def test_attach_port_no_ports_left_extra(self):
        vif = {'id': "fake_vif_id"}
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaisesRegexp(
                exception.NetworkError, "not enough physical ports",
                self.interface.vif_attach, task, vif)

    def test_attach_port_no_ports_left_internal_info(self):
        self.port.internal_info = {
            common.TENANT_VIF_KEY: self.port.extra['vif_port_id']}
        self.port.extra = {}
        self.port.save()
        vif = {'id': "fake_vif_id"}
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaisesRegexp(
                exception.NetworkError, "not enough physical ports",
                self.interface.vif_attach, task, vif)

    def test_attach_port_vif_already_attached_extra(self):
        vif = {'id': self.port.extra['vif_port_id']}
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaisesRegexp(
                exception.NetworkError, "already attached",
                self.interface.vif_attach, task, vif)

    def test_attach_port_vif_already_attach_internal_info(self):
        vif = {'id': self.port.extra['vif_port_id']}
        self.port.internal_info = {
            common.TENANT_VIF_KEY: self.port.extra['vif_port_id']}
        self.port.extra = {}
        self.port.save()
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaisesRegexp(
                exception.NetworkError, "already attached",
                self.interface.vif_attach, task, vif)

    def test_vif_detach_in_extra(self):
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.vif_detach(
                task, self.port.extra['vif_port_id'])
            self.port.refresh()
            self.assertFalse('vif_port_id' in self.port.extra)
            self.assertFalse(common.TENANT_VIF_KEY in self.port.internal_info)

    def test_vif_detach_in_internal_info(self):
        self.port.internal_info = {
            common.TENANT_VIF_KEY: self.port.extra['vif_port_id']}
        self.port.extra = {}
        self.port.save()
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.vif_detach(
                task, self.port.internal_info[common.TENANT_VIF_KEY])
            self.port.refresh()
            self.assertFalse('vif_port_id' in self.port.extra)
            self.assertFalse(common.TENANT_VIF_KEY in self.port.internal_info)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_address')
    def test_port_changed_address(self, mac_update_mock):
        new_address = '11:22:33:44:55:bb'
        self.port.address = new_address
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.port_changed(task, self.port)
            mac_update_mock.assert_called_once_with(
                self.port.extra['vif_port_id'],
                new_address, token=task.context.auth_token)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_address')
    def test_port_changed_address_VIF_MAC_update_fail(self, mac_update_mock):
        new_address = '11:22:33:44:55:bb'
        self.port.address = new_address
        mac_update_mock.side_effect = (
            exception.FailedToUpdateMacOnPort(port_id=self.port.uuid))
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaises(exception.FailedToUpdateMacOnPort,
                              self.interface.port_changed,
                              task, self.port)
            mac_update_mock.assert_called_once_with(
                self.port.extra['vif_port_id'],
                new_address, token=task.context.auth_token)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_address')
    def test_port_changed_address_no_vif_id(self, mac_update_mock):
        self.port.extra = {}
        self.port.save()
        self.port.address = '11:22:33:44:55:bb'
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.port_changed(task, self.port)
            self.assertFalse(mac_update_mock.called)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_dhcp_opts')
    def test_port_changed_client_id(self, dhcp_update_mock):
        expected_extra = {'vif_port_id': 'fake-id', 'client-id': 'fake2'}
        expected_dhcp_opts = [{'opt_name': 'client-id', 'opt_value': 'fake2'}]
        self.port.extra = expected_extra
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.port_changed(task, self.port)
            dhcp_update_mock.assert_called_once_with(
                'fake-id', expected_dhcp_opts, token=self.context.auth_token)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_dhcp_opts')
    def test_port_changed_vif(self, dhcp_update_mock):
        expected_extra = {'vif_port_id': 'new_ake-id', 'client-id': 'fake1'}
        self.port.extra = expected_extra
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.port_changed(task, self.port)
            self.assertFalse(dhcp_update_mock.called)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_dhcp_opts')
    def test_port_changed_client_id_fail(self, dhcp_update_mock):
        self.port.extra = {'vif_port_id': 'fake-id', 'client-id': 'fake2'}
        dhcp_update_mock.side_effect = (
            exception.FailedToUpdateDHCPOptOnPort(port_id=self.port.uuid))
        with task_manager.acquire(self.context, self.node.id) as task:
            self.assertRaises(exception.FailedToUpdateDHCPOptOnPort,
                              self.interface.port_changed,
                              task, self.port)

    @mock.patch('ironic.dhcp.neutron.NeutronDHCPApi.update_port_dhcp_opts')
    def test_port_changed_client_id_no_vif_id(self, dhcp_update_mock):
        self.port.extra = {'client-id': 'fake1'}
        self.port.save()
        self.port.extra = {'client-id': 'fake2'}
        with task_manager.acquire(self.context, self.node.id) as task:
            self.interface.port_changed(task, self.port)
            self.assertFalse(dhcp_update_mock.called)

    def _test_port_changed(self, has_vif=False, in_portgroup=False,
                           pxe_enabled=True, standalone_ports=True,
                           expect_errors=False):
        pg = obj_utils.create_test_portgroup(
            self.context, node_id=self.node.id,
            standalone_ports_supported=standalone_ports)

        extra_vif = {'vif_port_id': uuidutils.generate_uuid()}
        if has_vif:
            extra = extra_vif
            opposite_extra = {}
        else:
            extra = {}
            opposite_extra = extra_vif
        opposite_pxe_enabled = not pxe_enabled

        pg_id = None
        if in_portgroup:
            pg_id = pg.id

        ports = []

        # Update only portgroup id on existed port with different
        # combinations of pxe_enabled/vif_port_id
        p1 = obj_utils.create_test_port(self.context, node_id=self.node.id,
                                        uuid=uuidutils.generate_uuid(),
                                        address="aa:bb:cc:dd:ee:01",
                                        extra=extra,
                                        pxe_enabled=pxe_enabled)
        p1.portgroup_id = pg_id
        ports.append(p1)

        # Update portgroup_id/pxe_enabled/vif_port_id in one request
        p2 = obj_utils.create_test_port(self.context, node_id=self.node.id,
                                        uuid=uuidutils.generate_uuid(),
                                        address="aa:bb:cc:dd:ee:02",
                                        extra=opposite_extra,
                                        pxe_enabled=opposite_pxe_enabled)
        p2.extra = extra
        p2.pxe_enabled = pxe_enabled
        p2.portgroup_id = pg_id
        ports.append(p2)

        # Update portgroup_id and pxe_enabled
        p3 = obj_utils.create_test_port(self.context, node_id=self.node.id,
                                        uuid=uuidutils.generate_uuid(),
                                        address="aa:bb:cc:dd:ee:03",
                                        extra=extra,
                                        pxe_enabled=opposite_pxe_enabled)
        p3.pxe_enabled = pxe_enabled
        p3.portgroup_id = pg_id
        ports.append(p3)

        # Update portgroup_id and vif_port_id
        p4 = obj_utils.create_test_port(self.context, node_id=self.node.id,
                                        uuid=uuidutils.generate_uuid(),
                                        address="aa:bb:cc:dd:ee:04",
                                        pxe_enabled=pxe_enabled,
                                        extra=opposite_extra)
        p4.extra = extra
        p4.portgroup_id = pg_id
        ports.append(p4)

        for port in ports:
            with task_manager.acquire(self.context, self.node.id) as task:
                if not expect_errors:
                    self.interface.port_changed(task, port)
                else:
                    self.assertRaises(exception.Conflict,
                                      self.interface.port_changed,
                                      task, port)

    def test_port_changed_novif_pxe_noportgroup(self):
        self._test_port_changed(has_vif=False, in_portgroup=False,
                                pxe_enabled=True,
                                expect_errors=False)

    def test_port_changed_novif_nopxe_noportgroup(self):
        self._test_port_changed(has_vif=False, in_portgroup=False,
                                pxe_enabled=False,
                                expect_errors=False)

    def test_port_changed_vif_pxe_noportgroup(self):
        self._test_port_changed(has_vif=True, in_portgroup=False,
                                pxe_enabled=True,
                                expect_errors=False)

    def test_port_changed_vif_nopxe_noportgroup(self):
        self._test_port_changed(has_vif=True, in_portgroup=False,
                                pxe_enabled=False,
                                expect_errors=False)

    def test_port_changed_novif_pxe_portgroup_standalone_ports(self):
        self._test_port_changed(has_vif=False, in_portgroup=True,
                                pxe_enabled=True, standalone_ports=True,
                                expect_errors=False)

    def test_port_changed_novif_pxe_portgroup_nostandalone_ports(self):
        self._test_port_changed(has_vif=False, in_portgroup=True,
                                pxe_enabled=True, standalone_ports=False,
                                expect_errors=True)

    def test_port_changed_novif_nopxe_portgroup_standalone_ports(self):
        self._test_port_changed(has_vif=False, in_portgroup=True,
                                pxe_enabled=False, standalone_ports=True,
                                expect_errors=False)

    def test_port_changed_novif_nopxe_portgroup_nostandalone_ports(self):
        self._test_port_changed(has_vif=False, in_portgroup=True,
                                pxe_enabled=False, standalone_ports=False,
                                expect_errors=False)

    def test_port_changed_vif_pxe_portgroup_standalone_ports(self):
        self._test_port_changed(has_vif=True, in_portgroup=True,
                                pxe_enabled=True, standalone_ports=True,
                                expect_errors=False)

    def test_port_changed_vif_pxe_portgroup_nostandalone_ports(self):
        self._test_port_changed(has_vif=True, in_portgroup=True,
                                pxe_enabled=True, standalone_ports=False,
                                expect_errors=True)

    def test_port_changed_vif_nopxe_portgroup_standalone_ports(self):
        self._test_port_changed(has_vif=True, in_portgroup=True,
                                pxe_enabled=True, standalone_ports=True,
                                expect_errors=False)

    def test_port_changed_vif_nopxe_portgroup_nostandalone_ports(self):
        self._test_port_changed(has_vif=True, in_portgroup=True,
                                pxe_enabled=False, standalone_ports=False,
                                expect_errors=True)
