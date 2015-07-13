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

import mock

from oslo_config import cfg
from oslo_utils import importutils

from ironic.common import exception
from ironic.conductor import task_manager
from ironic.drivers.modules.cimc import common as cimc_common
from ironic.tests.conductor import utils as mgr_utils
from ironic.tests.db import base as db_base
from ironic.tests.db import utils as db_utils
from ironic.tests.objects import utils as obj_utils

imcsdk = importutils.try_import('ImcSdk')

CONF = cfg.CONF


class CIMCBaseTestCase(db_base.DbTestCase):

    def setUp(self):
        super(CIMCBaseTestCase, self).setUp()
        mgr_utils.mock_the_extension_manager(driver="fake_cimc")
        self.node = obj_utils.create_test_node(
            self.context,
            driver='fake_cimc',
            driver_info=db_utils.get_test_cimc_info(),
            instance_uuid="fake_uuid")
        CONF.set_override('max_retry', 2, 'cimc')
        CONF.set_override('action_interval', 0, 'cimc')


class ParseDriverInfoTestCase(CIMCBaseTestCase):

    def test_parse_driver_info(self):
        info = cimc_common.parse_driver_info(self.node)

        self.assertIsNotNone(info.get('cimc_address'))
        self.assertIsNotNone(info.get('cimc_username'))
        self.assertIsNotNone(info.get('cimc_password'))

    def test_parse_driver_info_missing_address(self):
        del self.node.driver_info['cimc_address']
        self.assertRaises(exception.MissingParameterValue,
                          cimc_common.parse_driver_info, self.node)

    def test_parse_driver_info_missing_username(self):
        del self.node.driver_info['cimc_username']
        self.assertRaises(exception.MissingParameterValue,
                          cimc_common.parse_driver_info, self.node)

    def test_parse_driver_info_missing_password(self):
        del self.node.driver_info['cimc_password']
        self.assertRaises(exception.MissingParameterValue,
                          cimc_common.parse_driver_info, self.node)


@mock.patch.object(cimc_common, 'cimc_handle', autospec=True)
class CIMCHandleLogin(CIMCBaseTestCase):

    def test_cimc_handle_login(self, mock_handle):
        info = cimc_common.parse_driver_info(self.node)

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                cimc_common.handle_login(task, handle, info)

                handle.login.assert_called_once_with(
                    self.node.driver_info['cimc_address'],
                    self.node.driver_info['cimc_username'],
                    self.node.driver_info['cimc_password'])

    def test_cimc_handle_login_exception(self, mock_handle):
        info = cimc_common.parse_driver_info(self.node)

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                handle.login.side_effect = imcsdk.ImcException('Boom')

                self.assertRaises(exception.CIMCException,
                                  cimc_common.handle_login,
                                  task, handle, info)

                handle.login.assert_called_once_with(
                    self.node.driver_info['cimc_address'],
                    self.node.driver_info['cimc_username'],
                    self.node.driver_info['cimc_password'])


class CIMCHandleTestCase(CIMCBaseTestCase):

    @mock.patch.object(imcsdk, 'ImcHandle', autospec=True)
    @mock.patch.object(cimc_common, 'handle_login', autospec=True)
    def test_cimc_handle(self, mock_login, mock_handle):
        mo_hand = mock.MagicMock()
        mo_hand.username = self.node.driver_info.get('cimc_username')
        mo_hand.password = self.node.driver_info.get('cimc_password')
        mo_hand.name = self.node.driver_info.get('cimc_address')
        mock_handle.return_value = mo_hand
        info = cimc_common.parse_driver_info(self.node)

        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with cimc_common.cimc_handle(task) as handle:
                self.assertEqual(handle, mock_handle.return_value)

        mock_login.assert_called_once_with(task, mock_handle.return_value,
                                           info)
        mock_handle.return_value.logout.assert_called_once_with()


@mock.patch.object(cimc_common, 'cimc_handle', autospec=True)
class AddVnicTestCase(CIMCBaseTestCase):

    def _test_add_vnic(self, mock_mo, mock_handle, pxe=False):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                first_mock = mock.MagicMock()
                second_mock = mock.MagicMock()
                mock_mo.side_effect = [first_mock, second_mock]

                mo = handle.get_imc_managedobject.return_value
                mo.__getitem__.return_value.Dn = "DN"
                handle.xml_query.return_value.error_code = None

                dn = "DN/host-eth-name"

                cimc_common.add_vnic(task, "name", "mac_address", 600, pxe)

                mock_mo.assert_any_call("adaptorEthGenProfile")
                mock_mo.assert_any_call("adaptorHostEthIf")

                first_mock.set_attr.assert_any_call("name", "name")
                first_mock.set_attr.assert_any_call("mtu", "1500")
                first_mock.set_attr.assert_any_call(
                    "pxeBoot", "enabled" if pxe else "disabled")
                first_mock.set_attr.assert_any_call("Dn", dn)
                first_mock.set_attr.assert_any_call("mac", "mac_address")
                first_mock.set_attr.assert_any_call("uplinkPort", "1")

                second_mock.set_attr.assert_any_call("vlanMode", "ACCESS")
                second_mock.set_attr.assert_any_call("vlan", "600")
                second_mock.set_attr.assert_any_call("Dn", dn)

                handle.xml_query.assert_called_once_with(
                    imcsdk.ImcCore.ExternalMethod.return_value,
                    imcsdk.WriteXmlOption.DIRTY)

    @mock.patch.object(imcsdk.ImcCore, 'ManagedObject', autospec=True)
    def test_add_vnic(self, mock_mo, mock_handle):
        self._test_add_vnic(mock_mo, mock_handle)

    @mock.patch.object(imcsdk.ImcCore, 'ManagedObject', autospec=True)
    def test_add_vnic_pxe(self, mock_mo, mock_handle):
        self._test_add_vnic(mock_mo, mock_handle, pxe=True)

    @mock.patch.object(imcsdk.ImcCore, 'ManagedObject', autospec=True)
    def test_add_vnic_long_name(self, mock_mo, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                mo = handle.get_imc_managedobject.return_value
                mo.__getitem__.return_value.Dn = "DN"
                handle.xml_query.return_value.error_code = None
                dn = "DN/host-eth-namenamenamenamenamenamenamenam"
                cimc_common.add_vnic(
                    task, "namenamenamenamenamenamenamenamename",
                    "mac_address", 600)
                mock_mo.return_value.set_attr.assert_any_call("Dn", dn)

    def test_add_vnic_fail(self, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                handle.xml_query.return_value.error_code = "123456"
                self.assertRaises(imcsdk.ImcException, cimc_common.add_vnic,
                                  task, "name", "mac_address", 600)


@mock.patch.object(cimc_common, 'cimc_handle', autospec=True)
class DeleteVnicTestCase(CIMCBaseTestCase):

    def test_delete_vnic(self, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                mo = handle.get_imc_managedobject.return_value
                mo.__getitem__.return_value.Dn = "DN"

                cimc_common.delete_vnic(task, "name")

                expected_params = {"Dn": "DN/host-eth-name"}
                handle.remove_imc_managedobject.assert_called_once_with(
                    None, class_id="adaptorHostEthIf", params=expected_params)

    def test_delete_vnic_fail(self, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                mo = handle.get_imc_managedobject.return_value
                mo.__getitem__.return_value.Dn = "DN"
                handle.remove_imc_managedobject.side_effect = (
                    imcsdk.ImcException("Boom"))

                self.assertRaises(imcsdk.ImcException,
                                  cimc_common.delete_vnic, task, "name")

                expected_params = {"Dn": "DN/host-eth-name"}
                handle.remove_imc_managedobject.assert_called_once_with(
                    None, class_id="adaptorHostEthIf", params=expected_params)

    def test_delete_vnic_long_name(self, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with mock_handle(task) as handle:
                mo = handle.get_imc_managedobject.return_value
                mo.__getitem__.return_value.Dn = "DN"

                cimc_common.delete_vnic(
                    task, "namenamenamenamenamenamenamenamename")

                expected_params = {
                    "Dn": "DN/host-eth-namenamenamenamenamenamenamenam"}
                handle.remove_imc_managedobject.assert_called_once_with(
                    None, class_id="adaptorHostEthIf", params=expected_params)
