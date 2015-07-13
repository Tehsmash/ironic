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

from oslo_utils import importutils

from ironic.common import exception
from ironic.conductor import task_manager
from ironic.drivers.modules.cimc import common as cimc_common
from ironic.tests.db import base as db_base
from ironic.tests.db import utils as db_utils
from ironic.tests.objects import utils as obj_utils

imcsdk = importutils.try_import('ImcSdk')


class CIMCBaseTestCase(db_base.DbTestCase):

    def setUp(self):
        super(CIMCBaseTestCase, self).setUp()
        self.node = obj_utils.create_test_node(
            self.context, driver='fake_cimc',
            driver_info=db_utils.get_test_cimc_info())


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


class CIMCHandleTestCase(CIMCBaseTestCase):

    def setUp(self):
        super(CIMCHandleTestCase, self).setUp()
        cimc_common.CIMC_HANDLES = {}

    @mock.patch.object(imcsdk, 'ImcHandle', autospec=True)
    def test_cimc_handle(self, mock_handle):
        with task_manager.acquire(self.context, self.node.uuid,
                                  shared=False) as task:
            with cimc_common.cimc_handle(task) as handle:
                handle1 = handle

            self.assertEqual(handle1, cimc_common.CIMC_HANDLES[
                self.node.driver_info('cimc_address')])

            with cimc_common.cimc_handle(task) as handle:
                handle2 = handle

        mock_handle.login.assert_called_once_with(
            self.node.driver_info('cimc_address'),
            self.node.driver_info('cimc_username'),
            self.node.driver_info('cimc_password'),
            imcsdk.YesOrNo.TRUE)

        self.assertEqual(handle1, handle2)
