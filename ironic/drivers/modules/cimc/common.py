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

from contextlib import contextmanager
from oslo_log import log as logging
from oslo_utils import importutils

from ironic.drivers.modules import deploy_utils

REQUIRED_PROPERTIES = {
    'cimc_address': _('IP or Hostname of the CIMC. Required.'),
    'cimc_username': _('CIMC Manager admin username. Required.'),
    'cimc_password': _('CIMC Manager password. Required.'),
}

COMMON_PROPERTIES = REQUIRED_PROPERTIES

imcsdk = importutils.try_import('ImcSdk')

LOG = logging.getLogger(__name__)

CIMC_HANDLES = {}


def parse_driver_info(node):
    """Parses and creates Cisco driver info

    :param node: An Ironic node object.
    :returns: dictonary that contains node.driver_info parameter/values.
    :raises: MissingParameterValue if any required parameters are missing.
    """

    info = {}
    for param in REQUIRED_PROPERTIES:
        info[param] = node.driver_info.get(param)
    error_msg = (_("%s driver requires these parameters to be set in the "
                   "node's driver_info.") %
                 node.driver)
    deploy_utils.check_for_missing_params(info, error_msg)
    return info


@contextmanager
def cimc_handle(task):
    info = parse_driver_info(task.node)

    handle = CIMC_HANDLES.get(info['cimc_address'])
    if handle is None:
        LOG.debug("Handle for %s doesn't exist,"
                  "creating one" % info['cimc_address'])
        handle = imcsdk.ImcHandle()

        handle.login(info['cimc_address'],
                     info['cimc_username'],
                     info['cimc_password'],
                     auto_refresh=imcsdk.YesOrNo.TRUE)

        CIMC_HANDLES[info['cimc_address']] = handle
    yield handle


def add_vnic(task, name, mac, vlan, pxe=False):
    name = name[0:31]
    with cimc_handle(task) as handle:
        rackunit = handle.get_imc_managedobject(
            None, imcsdk.ComputeRackUnit.class_id())
        adaptorunits = handle.get_imc_managedobject(
            in_mo=rackunit, class_id=imcsdk.AdaptorUnit.class_id())

        dn = "%s/host-eth-%s" % (adaptorunits[0].Dn, name)

        method = imcsdk.ImcCore.ExternalMethod("ConfigConfMo")
        method.Cookie = handle.cookie
        method.Dn = dn

        config = imcsdk.Imc.ConfigConfig()

        newVic = imcsdk.ImcCore.ManagedObject("adaptorHostEthIf")
        newVic.set_attr("name", name)
        newVic.set_attr("mtu", "1500")
        newVic.set_attr("pxeBoot", "enabled" if pxe else "disabled")
        newVic.set_attr("Dn", dn)
        newVic.set_attr("mac", mac)
        newVic.set_attr("uplinkPort", "1")

        vlanProfile = imcsdk.ImcCore.ManagedObject("adaptorEthGenProfile")
        vlanProfile.set_attr("vlanMode", "ACCESS")
        vlanProfile.set_attr("vlan", str(vlan))
        vlanProfile.set_attr("Dn", dn)

        newVic.add_child(vlanProfile)
        config.add_child(newVic)
        method.InConfig = config

        handle.xml_query(
            method, imcsdk.WriteXmlOption.DIRTY, dump_xml=True)


def delete_vnic(task, name):
    name = name[0:31]
    with cimc_handle(task) as handle:
        rackunit = handle.get_imc_managedobject(
            None, imcsdk.ComputeRackUnit.class_id())
        adaptorunits = handle.get_imc_managedobject(
            in_mo=rackunit, class_id=imcsdk.AdaptorUnit.class_id())
        vic = {
            "Dn": "%s/host-eth-%s" % (adaptorunits[0].Dn, name),
        }
        handle.remove_imc_managedobject(
            None, class_id="adaptorHostEthIf", params=vic, dump_xml=True)
