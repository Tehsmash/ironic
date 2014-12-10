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

from oslo.config import cfg

from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.db import api as db_api
from ironic.openstack.common import importutils
from ironic.openstack.common import log as logging
from ironic.openstack.common import loopingcall

ucssdk = importutils.try_import('UcsSdk')

opts = [
    cfg.IntOpt('max_retry',
               default=10,
               help='No of retries'),
    cfg.IntOpt('action_timeout',
               default=5,
               help='Seconds to wait for power action to be completed'),
    cfg.IntOpt('dump_xml',
               default=True,
               help='Dump xml query response and responses')
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='cisco',
                         title='Options for the cisco power driver')
CONF.register_group(opt_group)
CONF.register_opts(opts, opt_group)

LOG = logging.getLogger(__name__)


def get_processor_units(handle, compute_unit):
    """Gets the processor inventory of the passed computenode
    :param handle: Active UCS Manager handle
    :param compute_node: Compute node MO object
    :returns: Compute node adaptor inventory
    :raises: UcsException if driver failes to get inventory.
    """

    in_filter = ucssdk.FilterFilter()
    wcard_filter = ucssdk.WcardFilter()
    wcard_filter.Class = "processorUnit"
    wcard_filter.Property = "dn"
    wcard_filter.Value = "%s/" % compute_unit.Dn
    in_filter.AddChild(wcard_filter)
    units = {}

    try:
        processor_units = handle.ConfigResolveClass(
                              ucssdk.ProcessorUnit.ClassId(),
                              in_filter,
                              inHierarchical=ucssdk.YesOrNo.FALSE,
                              #dumpXml=CONF.cisco.dump_xml
                              dumpXml=ucssdk.YesOrNo.TRUE
                              )

        if processor_units.errorCode == 0:
            for p_unit in processor_units.OutConfigs.GetChild():
                unit = {}
                unit['arch'] = p_unit.getattr(ucssdk.ProcessorUnit.ARCH)
                unit['cores'] = p_unit.getattr(ucssdk.ProcessorUnit.CORES)
                unit['coresEnabled'] = p_unit.getattr(
                                           ucssdk.ProcessorUnit.CORES_ENABLED)
                unit['model'] = p_unit.getattr(ucssdk.ProcessorUnit.MODEL)
                unit['socketDesignation'] = p_unit.getattr(
                    ucssdk.ProcessorUnit.SOCKET_DESIGNATION)
                unit['speed'] = p_unit.getattr(ucssdk.ProcessorUnit.SPEED)
                unit['stepping'] = p_unit.getattr(
                    ucssdk.ProcessorUnit.STEPPING)
                unit['threads'] = p_unit.getattr(ucssdk.ProcessorUnit.THREADS)
                unit['vendor'] = p_unit.getattr(ucssdk.ProcessorUnit.VENDOR)
                units['AdaptorUnit-%s' % (p_unit.getattr(ucssdk.ProcessorUnit.ID))] = \
                    unit
    except Exception as ex:
        raise exception.IronicException("Cisco Driver: %s" % ex)
    return units


def get_memory_inventory(handle, compute_blade):
    """Gets the memory inventory of the passed computenode
    :param handle: Active UCS Manager handle
    :param compute_node: Compute node MO object
    :returns: Compute node adaptor inventory
    :raises: UcsException if driver failes to get inventory.
    """
    in_filter = ucssdk.FilterFilter()
    wcard_filter = ucssdk.WcardFilter()
    wcard_filter.Class = "memoryArray"
    wcard_filter.Property = "dn"
    wcard_filter.Value = "%s/" % compute_blade.Dn
    in_filter.AddChild(wcard_filter)
    mem_arrays = {}

    try:
        arrays = handle.ConfigResolveClass(
                            ucssdk.MemoryArray.ClassId(),
                            in_filter,
                            inHierarchical=ucssdk.YesOrNo.FALSE,
                            dumpXml=ucssdk.YesOrNo.TRUE
                            )

        if (arrays.errorCode == 0):
            for array in arrays.OutConfigs.GetChild():
                unit = {}
                unit['cpuId'] = array.getattr(ucssdk.MemoryArray.CPU_ID)
                unit['currCapacity'] = \
                    array.getattr(ucssdk.MemoryArray.CURR_CAPACITY)
                unit['maxCapacity'] = \
                    array.getattr(ucssdk.MemoryArray.MAX_CAPACITY)
                unit['populated'] = array.getattr(ucssdk.MemoryArray.POPULATED)
                mem_arrays['MemoryArray-%s' % (array.getattr(ucssdk.MemoryArray.ID))] = \
                    unit
    except ucssdk.UcsException as ex:
        raise exception.IronicException("Cisco Driver: %s" % ex)
    return mem_arrays


def get_storage_inventory(handle, compute_blade):
    """Gets the storage inventory of the passed computenode
    :param handle: Active UCS Manager handle
    :param compute_node: Compute node MO object
    :returns: Compute node adaptor inventory
    :raises: UcsException if driver failes to get inventory.
    """

    in_filter = ucssdk.FilterFilter()
    wcard_filter = ucssdk.WcardFilter()
    wcard_filter.Class = "storageLocalDisk"
    wcard_filter.Property = "dn"
    wcard_filter.Value = "%s/" % compute_blade.Dn
    in_filter.AddChild(wcard_filter)

    disks = {}
    try:
        local_disks = handle.ConfigResolveClass(
                                  ucssdk.StorageLocalDisk.ClassId(),
                                  in_filter,
                                  inHierarchical=ucssdk.YesOrNo.FALSE,
                                  dumpXml=ucssdk.YesOrNo.TRUE)
                                  #dumpXml=CONF.cisco.dump_xml)
        if (local_disks.errorCode == 0):
            for l_disk in local_disks.OutConfigs.GetChild():
                disk = {}
                disk['blockSize'] = \
                    l_disk.getattr(ucssdk.StorageLocalDisk.BLOCK_SIZE)
                disk['connectionProtocol'] = \
                    l_disk.getattr(ucssdk.StorageLocalDisk.CONNECTION_PROTOCOL)
                disk['model'] = l_disk.getattr(ucssdk.StorageLocalDisk.MODEL)
                disk['numberOfBlocks'] = \
                    l_disk.getattr(ucssdk.StorageLocalDisk.NUMBER_OF_BLOCKS)
                disk['presence'] = \
                    l_disk.getattr(ucssdk.StorageLocalDisk.PRESENCE)
                disk['serial'] = l_disk.getattr(ucssdk.StorageLocalDisk.SERIAL)
                disk['size'] = l_disk.getattr(ucssdk.StorageLocalDisk.SIZE)
                disk['vendor'] = l_disk.getattr(ucssdk.StorageLocalDisk.VENDOR)
                disks['StorageLocalDisk-%s' %
                    (l_disk.getattr(ucssdk.StorageLocalDisk.ID))] = disk
    except ucssdk.UcsException as ex:
        raise exception.IronicException("Cisco Driver: (%s)" % ex)
    return disks


def get_adaptor_inventory(handle, compute_node):
    """Gets the adaptor inventory of the passed computenode

    :param handle: Active UCS Manager handle
    :param compute_node: Compute node MO object
    :returns: Compute node adaptor inventory
    :raises: UcsException if driver failes to get inventory.
    """
    in_filter = ucssdk.FilterFilter()
    wcard_filter = ucssdk.WcardFilter()
    wcard_filter.Class = "adaptorUnit"
    wcard_filter.Property = "dn"
    wcard_filter.Value = "%s/" % compute_node.Dn
    in_filter.AddChild(wcard_filter)

    units = {}
    try:
        adaptor_units = handle.ConfigResolveClass(
                            ucssdk.AdaptorUnit.ClassId(),
                            in_filter,
                            inHierarchical=ucssdk.YesOrNo.FALSE,
                            dumpXml=ucssdk.YesOrNo.TRUE
                            #dumpXml=CONF.cisco.dump_xml
                            )
        if (adaptor_units.errorCode == 0):
            for a_unit in adaptor_units.OutConfigs.GetChild():
                unit = {}
                unit['baseMac'] = a_unit.getattr(ucssdk.AdaptorUnit.BASE_MAC)
                unit['model'] = a_unit.getattr(ucssdk.AdaptorUnit.MODEL)
                unit['partNumber'] = \
                    a_unit.getattr(ucssdk.AdaptorUnit.PART_NUMBER)
                unit['serial'] = a_unit.getattr(ucssdk.AdaptorUnit.SERIAL)
                unit['vendor'] = a_unit.getattr(ucssdk.AdaptorUnit.VENDOR)
                units['AdaptorUnit-%s' % (a_unit.getattr(ucssdk.AdaptorUnit.ID))] = \
                    unit
    except ucssdk.UcsException as ex:
        raise exception.IronicException("Cisco Driver: (%s)" % ex)

    return units


def generate_ucsm_handle(hostname, username, password, helper):
    ucs_handle = ucssdk.UcsHandle()
    try:
        success = ucs_handle.Login(
            hostname,
            username,
            password
        )
        helper.handles[hostname] = ucs_handle
    except ucssdk.UcsException as e:
        LOG.error("Cisco client exception %(msg)s" % (e.message))
        raise exception.TemporaryFailure("Cisco client exception %(msg)s"
                  % (e.message))
    return success, ucs_handle


class CiscoIronicDriverHelper(object):
    """Cisco UCS Ironic driver helper."""

    def __init__(self, hostname=None, username=None, password=None):
        """Initialize with UCS Manager details.

        :param hostname: UCS Manager hostname or ipaddress
        :param username: Username to login to UCS Manager.
        :param password: Login user password.
        """

        self.hostname = hostname
        self.username = username
        self.password = password
        self.service_profile = None
        self.handles = {}

    def _parse_driver_info(self, task):
        """Parses and creates Cisco driver info
        :param node: An Ironic node object.
        :returns: Cisco driver info.
        :raises: InvalidParameterValue if any required parameters are missing.
        """

        info = task.node.driver_info or {}
        self.hostname = info.get('hostname')
        self.username = info.get('username')
        self.password = info.get('password')
        self.service_profile = info.get('service_profile')
        self.uuid = task.node.uuid

        if not self.hostname:
            raise exception.InvalidParameterValue(_(
                "Cisco driver requires hostname be set"))

        if not self.username or not self.password:
            raise exception.InvalidParameterValue(_(
                "Cisco driver requires both username and password be set"))

        if not self.service_profile:
            raise exception.InvalidParameterValue(_(
                "Cisco driver requires service_profile be set"))

    def connect_ucsm(self, task):
        """Creates the UcsHandle
        :param task: Ironic task,
            which contain: 'hostname', 'username', 'password' parameters
        :returns: UcsHandle with active session
        :raises: IronicException in case of failure.
        """

        self._parse_driver_info(task)

        success, handle = generate_ucsm_handle(self.hostname,
                    self.username, self.password, self)

        return handle

    def logout(self):
        """Logouts the current active session."""
        self.handles[self.hostname].Logout()

    def get_managed_object(self, managed_object, in_filter):
        """Get the specified MO from UCS Manager.

        :param managed_object: MO classid
        :in_filter: input filter value
        :returns: Managed Object
        :raises: UcsException in case of failure.
        """

        handle = self.handles[self.hostname]

        try:
            managed_object = handle.GetManagedObject(
                                 None,
                                 managed_object,
                                 inFilter=in_filter,
                                 inHierarchincal=ucssdk.YesOrNo.FALSE)
            if not managed_object:
                LOG("No Managed Objects found")
        except ucssdk.UcsException as e:
            raise exception.IronicException("Cisco client exception %(msg)" %
                      (e.message))

    def get_lsboot_def(self, ucs_handle, compute):
        """Get the boot definition.
        :param ucs_handle: Active UCS handle.
        :returns: lsbootDef Managed Object
        :raises: UcsException in case of failure
        """

        in_filter = ucssdk.FilterFilter()
        wcard_filter = ucssdk.WcardFilter()
        wcard_filter.Class = "lsbootDef"
        wcard_filter.Property = "dn"
        wcard_filter.Value = "%s/" % compute.Dn
        in_filter.AddChild(wcard_filter)
        try:
            lsboot_def = ucs_handle.ConfigResolveClass(
                             ucssdk.LsbootDef.ClassId(),
                             in_filter,
                             inHierarchical=ucssdk.YesOrNo.FALSE,
                             dumpXml=ucssdk.YesOrNo.TRUE
                             )
            return lsboot_def
        except ucssdk.UcsException as ex:
            raise exception.IronicException("Cisco driver: %s" % ex)

    def get_server_local_storage(self, compute):
        """Get the lsbootLan of specific compute node
        :param compute_blade: compute blade managed object
        :returns: total local storage associated with this server
        :raises: UcsException in case of failure
        """
        in_filter = ucssdk.FilterFilter()
        wcard_filter = ucssdk.WcardFilter()
        wcard_filter.Class = "storageLocalDisk"
        wcard_filter.Property = "dn"
        wcard_filter.Value = "%s/" % compute.getattr(ucssdk.ComputeBlade.DN)
        in_filter.AddChild(wcard_filter)
        handle = self.handles[self.hostname]
        local_gb = 0
        try:
            disks = handle.ConfigResolveClass(
                        ucssdk.StorageLocalDisk.ClassId(),
                        in_filter,
                        inHierarchical=ucssdk.YesOrNo.FALSE,
                        dumpXml=ucssdk.YesOrNo.TRUE
                        )
            if disks.errorCode == 0:
                for local_disk in disks.OutConfigs.GetChild():
                    if local_disk.getattr(ucssdk.StorageLocalDisk.SIZE) != \
                           ucssdk.StorageLocalDisk.CONST_BLOCK_SIZE_UNKNOWN:
                        local_gb += int(local_disk.getattr(
                            ucssdk.StorageLocalDisk.SIZE))
                    LOG.error('Disk:%s size:%s' %
                        (local_disk.getattr(ucssdk.StorageLocalDisk.DN),
                         local_disk.getattr(ucssdk.StorageLocalDisk.SIZE))
                         )
        except ucssdk.UcsException as ex:
            raise exception.IronicException("Cisco driver: %s" % ex)
        if local_gb != 0:
            local_gb /= 1024
        LOG.error('Total disk: %d' % local_gb)
        return local_gb

    def get_lsboot_lan(self, lsboot_def):
        """Get the lsbootLan of specific compute node
        :param lsboot_def: lsboot_def MO
        :returns: lsbootDef Managed Object
        :raises: UcsException in case of failure
        """

        in_filter = ucssdk.FilterFilter()
        wcard_filter = ucssdk.WcardFilter()
        wcard_filter.Class = "lsbootLan"
        wcard_filter.Property = "dn"
        wcard_filter.Value = "%s/" % lsboot_def.getattr(ucssdk.LsbootDef.DN)
        in_filter.AddChild(wcard_filter)
        handle = self.handles[self.hostname]
        try:
            lsboot_lan = handle.ConfigResolveClass(
                              ucssdk.LsbootLan.ClassId(),
                              in_filter,
                              inHierarchical=ucssdk.YesOrNo.TRUE,
                              #dumpXml=CONF.cisco.dump_xml
                              dumpXml=ucssdk.YesOrNo.TRUE
                              )
            if (lsboot_lan.errorCode == 0):
                return lsboot_lan.OutConfigs.GetChild()
            else:
                LOG.debug('Failed to get lsbootLan')
        except ucssdk.UcsException as ex:
            raise exception.IronicExceptoin("Cisco driver: %s" % ex)

    def get_vnic_ether(self, vnic_name, ls_server):
        """Get the boot definition.
        :param vnic_name: vNIC name of service-profile
        :param ls_server: service-profile MO
        :returns: vNIC Managed Object
        :raises: UcsException in case of failure
        """

        in_filter = ucssdk.FilterFilter()

        and_filter0 = ucssdk.AndFilter()

        wcard_filter = ucssdk.WcardFilter()
        wcard_filter.Class = ucssdk.VnicEther.ClassId()
        wcard_filter.Property = "dn"
        wcard_filter.Value = "%s/" % ls_server.Dn
        and_filter0.AddChild(wcard_filter)

        eq_filter = ucssdk.EqFilter()
        eq_filter.Class = ucssdk.VnicEther.ClassId()
        eq_filter.Property = "name"
        eq_filter.Value = vnic_name
        and_filter0.AddChild(eq_filter)

        in_filter.AddChild(and_filter0)
        handle = self.handles[self.hostname]
        try:
            vnic_ether = handle.ConfigResolveClass(
                             ucssdk.VnicEther.ClassId(),
                             in_filter,
                             inHierarchical=ucssdk.YesOrNo.TRUE,
                             dumpXml=ucssdk.YesOrNo.TRUE
                             )

            if (vnic_ether.errorCode == 0):
                return vnic_ether.OutConfigs.GetChild()
        except ucssdk.UcsException as ex:
            raise exception.IronicExceptoin("Cisco driver: %s" % ex)

    def update_ironic_db(self, mac, ls_server, compute_blade):
        """Enroll nodes into Ironic DB
        :param mac: MAC address of the node being enrolled
        :param ls_server: service-profile MO
        """

        LOG.debug("Adding new node")
        # Check if any port is already registered in Ironic.
        dbapi = db_api.get_instance()
        for address in mac:
            try:
                port = dbapi.get_port_by_address(address.lower())
                LOG.debug("Address already in use.")
                LOG.debug('Port is already in use, skip adding nodes.')
                return
            except exception.PortNotFound as ex:
                LOG.debug("Port was not found")
            LOG.debug("Adding Port:" + address.lower())

        if len(mac) == 1 and mac[0] == 'derived':
            return

        rn_array = [
            ls_server.getattr(ucssdk.LsServer.DN),
            ucssdk.ManagedObject(ucssdk.NamingId.LS_POWER).MakeRn()
            ]

        power_state = None
        try:
            power = self.handles[self.hostname].GetManagedObject(
                           None, ucssdk.LsPower.ClassId(),
                           {ucssdk.LsPower.DN:
                               ucssdk.UcsUtils.MakeDn(rn_array)},
                           inHierarchical=ucssdk.YesOrNo.FALSE,
                           dumpXml=ucssdk.YesOrNo.TRUE
                           )
            if not power:
                power_state = states.ERROR
                raise exception.IronicException("Failed to get power MO,"
                          "configure valid service-profile.")
            else:
                LOG.error("State:%s" %
                    (power[0].getattr(ucssdk.LsPower.STATE)))
                if power[0].getattr(ucssdk.LsPower.STATE) == None:
                    power_state = states.ERROR
                if power[0].getattr(ucssdk.LsPower.STATE) == \
                        ucssdk.LsPower.CONST_STATE_DOWN:
                    power_state = states.POWER_OFF
                elif power[0].getattr(ucssdk.LsPower.STATE) == \
                        ucssdk.LsPower.CONST_STATE_UP:
                    power_state = states.POWER_ON
        except ucssdk.UcsException as ex:
            LOG.error(_("Cisco client exception: %(msg)s for node %(uuid)s"),
                      {'msg': ex, 'uuid': dbapi.uuid})
            raise exception.IronicException("Cisco client exception: %s" % ex)

        # Create new ironic node
        node = {'driver': 'pxe_cisco',
                'driver_info':
                    {'service_profile': ls_server.getattr(ucssdk.LsServer.DN),
                        'hostname': self.hostname,
                        'username': self.username,
                        'password': self.password
                    },
                'power_state': power_state,
                'properties':
                    {'memory_mb': compute_blade.getattr(
                         ucssdk.ComputeBlade.TOTAL_MEMORY),
                     'cpus': compute_blade.getattr(
                         ucssdk.ComputeBlade.NUM_OF_CPUS),
                     'cpu_arch': 'x86_64',
                     'local_gb': self.get_server_local_storage(compute_blade)
                    }
               }
        db_node = dbapi.create_node(node).as_dict()

        LOG.debug("Node Instance uuid:%s, db_power_state:%s power_state:%s"
            % (db_node['uuid'], db_node['power_state'], power_state))

        # Create ports
        for address in mac:
            port = {
                'address': address.lower(),
                'node_id': db_node['id']
                }
            LOG.debug("enrolling port: %s" % address.lower())
            dbapi.create_port(port).as_dict()
            LOG.debug("after create_port")

        LOG.debug('Enrolled node')

    def get_node_info(self, lsboot_def, ls_server, compute_blade):
        """Enroll nodes into Ironic DB
        :param lsboot_def: boot definition MO of service-profile
        :param ls_server: service-profile MO
        :returns None:
        :raises : IronicException in case of failure
        """

        try:
            # lsbootDef contains only one LsbootLan Mo
            boot_lan = self.get_lsboot_lan(lsboot_def)
            mac = []
            for lsboot_lan in boot_lan:
                if ((lsboot_lan != 0)
                    and (isinstance(lsboot_lan, ucssdk.ManagedObject))
                    and (lsboot_lan.classId == "LsbootLan")):

                    for image_path in lsboot_lan.GetChild():
                        if ((image_path != 0)):
                            vnic = self.get_vnic_ether(
                                             image_path.getattr("VnicName"),
                                             ls_server
                                             )
                            if (vnic != 0):
                                LOG.debug("MAC" +
                                    vnic[0].getattr(ucssdk.VnicEther.ADDR))
                                mac.insert(int(vnic[0].getattr(
                                    ucssdk.VnicEther.OPER_ORDER)) - 1,
                                    vnic[0].getattr(
                                        ucssdk.VnicEther.ADDR)
                                    )
            if len(mac) > 0:
                LOG.debug('node has ' + str(len(mac)) + 'nics' + ' '.join(mac))
                self.update_ironic_db(mac, ls_server, compute_blade)
        except ucssdk.UcsException as ex:
            raise ucssdk.UcsException("Cisco driver: %s" % ex)

    def enroll_nodes(self):
        """Enroll nodes to ironic DB."""

        handle = self.handles[self.hostname]
        try:
            ls_servers = handle.GetManagedObject(
                             None,
                             ucssdk.LsServer.ClassId(),
                             None,
                             dumpXml=ucssdk.YesOrNo.TRUE
                             )
            for ls_server in ls_servers:
                LOG.debug('Adding/Updating server - ' +
                    ls_server.getattr(ucssdk.LsServer.DN))
                LOG.debug('In addUcsServer')
                if 'blade' in ls_server.getattr(ucssdk.LsServer.PN_DN):
                    in_filter = ucssdk.FilterFilter()
                    eq_filter = ucssdk.EqFilter()
                    eq_filter.Class = "computeBlade"
                    eq_filter.Property = "assignedToDn"
                    eq_filter.Value = ls_server.getattr(ucssdk.LsServer.DN)
                    in_filter.AddChild(eq_filter)
                    compute_blades = handle.ConfigResolveClass(
                                         ucssdk.ComputeBlade.ClassId(),
                                         in_filter,
                                         inHierarchical=ucssdk.YesOrNo.FALSE,
                                         dumpXml=ucssdk.YesOrNo.TRUE
                                         )
                    if (compute_blades.errorCode == 0):
                        # for each computeBladeMo, get the lsbootDef Info.
                        for blade in compute_blades.OutConfigs.GetChild():
                            lsboot_def = self.get_lsboot_def(handle, blade)
                            for boot_def in lsboot_def.OutConfigs.GetChild():
                                # only one LsbootDef will be present,
                                # break once got that info.
                                self.get_node_info(boot_def, ls_server, blade)
                elif 'rack' in ls_server.getattr(ucssdk.LsServer.PN_DN):
                    in_filter = ucssdk.FilterFilter()
                    eq_filter = ucssdk.EqFilter()
                    eq_filter.Class = "computeRackUnit"
                    eq_filter.Property = "assignedToDn"
                    eq_filter.Value = ls_server.getattr(ucssdk.LsServer.DN)
                    in_filter.AddChild(eq_filter)
                    compute_rus = handle.ConfigResolveClass(
                                         ucssdk.ComputeRackUnit.ClassId(),
                                         in_filter,
                                         inHierarchical=ucssdk.YesOrNo.FALSE,
                                         dumpXml=ucssdk.YesOrNo.TRUE
                                         )
                    if (compute_rus.errorCode == 0):
                        # for each computeRackUnitMo, get the lsbootDef Info.
                        for r_unit in compute_rus.OutConfigs.GetChild():
                            lsboot_def = self.get_lsboot_def(handle, r_unit)
                            for boot_def in lsboot_def.OutConfigs.GetChild():
                                # only one LsbootDef will be present,
                                # break once got that info.
                                self.get_node_info(boot_def, ls_server, r_unit)
        except ucssdk.UcsException as ex:
            raise exception.IronicException("Cisco driver: %s" % ex)

    def _get_power_state(self, task):
        """Get current power state of this node

        :param node: Ironic node one of :class:`ironic.db.models.Node`
        :raises: InvalidParameterValue if required Ucs parameters are missing
        :raises: ServiceUnavailable on an error from Ucs.
        :returns: Power state of the given node
        """
        handle = self.handles[self.hostname]
        rn_array = [
            self.service_profile,
            ucssdk.ManagedObject(ucssdk.NamingId.LS_POWER).MakeRn()
            ]
        power_status = states.ERROR
        try:
            ls_power = handle.GetManagedObject(
                           None, ucssdk.LsPower.ClassId(),
                           {ucssdk.LsPower.DN:
                               ucssdk.UcsUtils.MakeDn(rn_array)},
                           inHierarchical=ucssdk.YesOrNo.FALSE,
                           dumpXml=ucssdk.YesOrNo.TRUE
                           #dumpXml=CONF.cisco.dump_xml
                           )
            if not ls_power:
                power_status = states.ERROR
                raise exception.IronicException("Failed to get power MO, "
                          "configure valid service-profile.")
            else:
                if ls_power[0].getattr(ucssdk.LsPower.STATE) == None:
                    power_status = states.ERROR
                if ls_power[0].getattr(ucssdk.LsPower.STATE) == \
                   ucssdk.LsPower.CONST_STATE_DOWN:
                    power_status = states.POWER_OFF
                elif ls_power[0].getattr(ucssdk.LsPower.STATE) == \
                    ucssdk.LsPower.CONST_STATE_UP:
                    power_status = states.POWER_ON

            return power_status
        except ucssdk.UcsException as ex:
            LOG.error(_("Cisco client exception: %(msg)s for node %(uuid)s"),
                      {'msg': ex, 'uuid': task.node.uuid})
            raise exception.IronicException("Cisco client exception: %s" % ex)

    def _set_power_state(self, task, desired_state):
        """Set power state of this node

        :param node: Ironic node one of :class:`ironic.db.models.Node`
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        :raises: ServiceUnavailable on an error from UcsHandle Client.
        :returns: Power state of the given node
        """

        handle = self.handles[self.hostname]
        rn_array = [
            self.service_profile,
            ucssdk.ManagedObject(ucssdk.NamingId.LS_POWER).MakeRn()
            ]
        power_status = states.ERROR
        try:
            ls_power = handle.GetManagedObject(
                           None,
                           ucssdk.LsPower.ClassId(),
                           {ucssdk.LsPower.DN:
                               ucssdk.UcsUtils.MakeDn(rn_array)},
                           inHierarchical=ucssdk.YesOrNo.FALSE,
                           dumpXml=ucssdk.YesOrNo.TRUE
                           #dumpXml=CONF.cisco.dump_xml
                           )
            if not ls_power:
                power_status = states.ERROR
                raise exception.IronicException("Failed to get power MO,"
                          " configure valid service-profile.")
            else:
                ls_power_set = handle.SetManagedObject(
                                   ls_power,
                                   ucssdk.LsPower.ClassId(),
                                   {ucssdk.LsPower.STATE: desired_state},
                                   dumpXml=ucssdk.YesOrNo.TRUE
                                   #dumpXml=CONF.cisco.dump_xml
                                   )
                if ls_power_set:
                    # There will be one one instance of ucssdk.LsPower
                    for power in ls_power_set:
                        power_status = power.getattr(ucssdk.LsPower.STATE)

            return power_status
        except Exception as ex:
            LOG.error(_("Cisco client exception: %(msg)s for node %(uuid)s"),
                      {'msg': ex, 'uuid': task.node.uuid})
            self.logout()
            raise exception.IronicException("%s" % ex)

    def set_power_status(self, task, desired_state):
        """Set power state of this node

        :param node: Ironic node one of :class:`ironic.db.models.Node`
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        :raises: ServiceUnavailable on an error from UcsHandle Client.
        :returns: Power state of the given node
        """
        try:
            power_status = self._get_power_state(task)
            if power_status is not desired_state:
                if desired_state == states.POWER_OFF:
                    pdesired_state = ucssdk.LsPower.CONST_STATE_DOWN
                elif desired_state == states.POWER_ON:
                    pdesired_state = ucssdk.LsPower.CONST_STATE_UP
                elif desired_state == states.REBOOT:
                    pdesired_state = \
                        ucssdk.LsPower.CONST_STATE_HARD_RESET_IMMEDIATE
                power_status = self._set_power_state(task, pdesired_state)
            updated_status = states.ERROR
            if power_status == ucssdk.LsPower.CONST_STATE_UP:
                updated_status = states.POWER_ON
            elif power_status == ucssdk.LsPower.CONST_STATE_DOWN:
                updated_status = states.POWER_OFF
            return updated_status

        except exception.IronicException as ex:
            LOG.error(_("Cisco client exception %(msg)s for node %(uuid)s"),
                      {'msg': ex, 'uuid': task.node.uuid})
            self.logout()
            raise exception.IronicException("%s" % ex)

    def _reboot(self, task, timeout=None):
        """Reboot this node
        :param node: Ironic node one of :class:`ironic.db.models.Node`
        :param timeout: Time in seconds to wait till reboot is compelete
        :raises: InvalidParameterValue if required seamicro parameters are
            missing.
        :returns: Power state of the given node
        """
        if timeout is None:
            timeout = CONF.cisco.action_timeout
        state = [None]
        retries = 0

        def _wait_for_reboot(state, retries):
            """Called at an interval.

            Until the node is rebooted successfully.
            """

            state[0] = self._get_power_state(task)
            if state[0] == states.POWER_ON:
                LOG.error("In _reboot %d %s" % (retries, state[0]))
                raise loopingcall.LoopingCallDone()

            if retries > CONF.cisco.max_retry:
                state[0] = states.ERROR
                LOG.error("In _reboot %d %s" % (retries, state[0]))
                raise loopingcall.LoopingCallDone()

            retries += 1
            #state = self._set_power_state(task, ucssdk.LsPower.CONST_STATE_UP)

        timer = loopingcall.FixedIntervalLoopingCall(_wait_for_reboot,
                                                     state, retries)
        p_state = self._get_power_state(task)
        LOG.error("p_state:%s" % (p_state))
        if p_state == states.POWER_OFF:
            self._set_power_state(task, ucssdk.LsPower.CONST_STATE_UP)
        else:
            self._set_power_state(task,
                ucssdk.LsPower.CONST_STATE_HARD_RESET_IMMEDIATE)
        timer.start(interval=timeout).wait()
        LOG.error("state: %s" % state[0])
        return state[0]

    def get_faults(self, task):

        handle = self.connect_ucsm(task)
        params = {'server': self.service_profile, 'faults': {}}

        # Need to get the server dn first.
        ls_server = handle.GetManagedObject(
                         None,
                         ucssdk.LsServer.ClassId(),
                         {ucssdk.LsServer.DN: self.service_profile},
                         #dumpXml=CONF.cisco.dump_xml
                         dumpXml=ucssdk.YesOrNo.TRUE
                         )
        # There will be only one service-profile matches the given DN.
        if ls_server and len(ls_server) == 1:
            # create wcard filter.
            in_filter = ucssdk.FilterFilter()
            wcard_filter = ucssdk.WcardFilter()
            wcard_filter.Class = ucssdk.FaultInst.ClassId()
            wcard_filter.Property = "dn"
            wcard_filter.Value = ls_server[0].getattr(ucssdk.LsServer.PN_DN)
            in_filter.AddChild(wcard_filter)

            fault_insts = handle.ConfigResolveClass(
                          ucssdk.FaultInst.ClassId(),
                          in_filter,
                          dumpXml=ucssdk.YesOrNo.TRUE
                          )
            if fault_insts:
                for fault_inst in fault_insts.OutConfigs.GetChild():
                    fault_details = {
                        ucssdk.FaultInst.CHANGE_SET:
                            fault_inst.getattr(ucssdk.FaultInst.CHANGE_SET),
                        ucssdk.FaultInst.DESCR:
                            fault_inst.getattr(ucssdk.FaultInst.DESCR),
                        ucssdk.FaultInst.LAST_TRANSITION:
                            fault_inst.getattr(
                                ucssdk.FaultInst.LAST_TRANSITION),
                        ucssdk.FaultInst.RN:
                            fault_inst.getattr(ucssdk.FaultInst.RN),
                        ucssdk.FaultInst.TYPE:
                            fault_inst.getattr(ucssdk.FaultInst.TYPE),
                        ucssdk.FaultInst.SEVERITY:
                            fault_inst.getattr(ucssdk.FaultInst.SEVERITY),
                        ucssdk.FaultInst.TAGS:
                            fault_inst.getattr(ucssdk.FaultInst.TAGS),
                        ucssdk.FaultInst.CAUSE:
                            fault_inst.getattr(ucssdk.FaultInst.CAUSE),
                        ucssdk.FaultInst.STATUS:
                            fault_inst.getattr(ucssdk.FaultInst.STATUS),
                        ucssdk.FaultInst.CREATED:
                            fault_inst.getattr(ucssdk.FaultInst.CREATED),
                        ucssdk.FaultInst.ACK:
                            fault_inst.getattr(ucssdk.FaultInst.ACK),
                        ucssdk.FaultInst.RULE:
                            fault_inst.getattr(ucssdk.FaultInst.RULE),
                        ucssdk.FaultInst.ORIG_SEVERITY:
                            fault_inst.getattr(ucssdk.FaultInst.ORIG_SEVERITY),
                        ucssdk.FaultInst.PREV_SEVERITY:
                            fault_inst.getattr(ucssdk.FaultInst.PREV_SEVERITY),
                        ucssdk.FaultInst.CODE:
                            fault_inst.getattr(ucssdk.FaultInst.CODE),
                        ucssdk.FaultInst.HIGHEST_SEVERITY:
                            fault_inst.getattr(
                                ucssdk.FaultInst.HIGHEST_SEVERITY),
                        ucssdk.FaultInst.ID:
                            fault_inst.getattr(ucssdk.FaultInst.ID),
                        ucssdk.FaultInst.OCCUR:
                            fault_inst.getattr(ucssdk.FaultInst.OCCUR)
                        }
                    params['faults'][fault_inst.getattr(ucssdk.FaultInst.DN)] = \
                        fault_details
        return params

    def get_temperature_stats(self, task):

        handle = self.connect_ucsm(task)
        params = {'server': self.service_profile}

        server = handle.GetManagedObject(
                         None,
                         ucssdk.LsServer.ClassId(),
                         {ucssdk.LsServer.DN: self.service_profile},
                         inHierarchical=ucssdk.YesOrNo.FALSE,
                         dumpXml=ucssdk.YesOrNo.TRUE
                         )
        # There will be only one service-profile matches the given DN.
        if server and len(server) == 1:
            if 'blade' in server[0].getattr(ucssdk.LsServer.PN_DN):
                #make ComputeMbTempStats Mo dn.
                dn = server[0].getattr(
                    ucssdk.LsServer.PN_DN) + '/board/temp-stats'
                compStats = ucssdk.ComputeMbTempStats
                mb_temp_stats = handle.GetManagedObject(
                                None,
                                compStats.ClassId(),
                                {compStats.DN: dn},
                                inHierarchical=ucssdk.YesOrNo.FALSE,
                                dumpXml=ucssdk.YesOrNo.TRUE
                                )
                if mb_temp_stats and len(mb_temp_stats) == 1:
                    mts = mb_temp_stats[0]
                    temp_stats = {
                        compStats.DN:
                            mts.getattr(compStats.DN),
                        compStats.FM_TEMP_SEN_IO:
                            mts.getattr(compStats.FM_TEMP_SEN_IO),
                        compStats.FM_TEMP_SEN_IO_AVG:
                            mts.getattr(compStats.FM_TEMP_SEN_IO_AVG),
                        compStats.FM_TEMP_SEN_IO_MAX:
                            mts.getattr(compStats.FM_TEMP_SEN_IO_MAX),
                        compStats.FM_TEMP_SEN_IO_MIN:
                            mts.getattr(compStats.FM_TEMP_SEN_IO_MIN),
                        compStats.FM_TEMP_SEN_REAR:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR),
                        compStats.FM_TEMP_SEN_REAR_AVG:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_AVG),
                        compStats.FM_TEMP_SEN_REAR_L:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_L),
                        compStats.FM_TEMP_SEN_REAR_LAVG:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_LAVG),
                        compStats.FM_TEMP_SEN_REAR_LMAX:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_LMAX),
                        compStats.FM_TEMP_SEN_REAR_LMIN:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_LMIN),
                        compStats.FM_TEMP_SEN_REAR_MAX:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_MAX),
                        compStats.FM_TEMP_SEN_REAR_MIN:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_MIN),
                        compStats.FM_TEMP_SEN_REAR_R:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_R),
                        compStats.FM_TEMP_SEN_REAR_RAVG:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_RAVG),
                        compStats.FM_TEMP_SEN_REAR_RMAX:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_RMAX),
                        compStats.FM_TEMP_SEN_REAR_RMIN:
                            mts.getattr(compStats.FM_TEMP_SEN_REAR_RMIN),
                        compStats.SUSPECT:
                            mts.getattr(compStats.SUSPECT),
                        compStats.THRESHOLDED:
                            mts.getattr(compStats.THRESHOLDED),
                        compStats.TIME_COLLECTED:
                            mts.getattr(compStats.TIME_COLLECTED)
                        }
                    params['temp_stats'] = temp_stats
            elif 'rack' in server[0].getattr(ucssdk.LsServer.PN_DN):
                dn = server[0].getattr(
                    ucssdk.LsServer.PN_DN) + '/board/temp-stats'
                crmts = ucssdk.ComputeRackUnitMbTempStats
                mb_temp_stats = handle.GetManagedObject(
                                    None,
                                    crmts.ClassId(),
                                    {crmts.DN: dn},
                                    inHierarchical=ucssdk.YesOrNo.FALSE,
                                    dumpXml=ucssdk.YesOrNo.TRUE
                                    )
                if mb_temp_stats and len(mb_temp_stats) == 1:
                    mts = mb_temp_stats[0]
                    temp_stats = {
                         crmts.DN:
                            mts.getattr(crmts.DN),
                         crmts.AMBIENT_TEMP:
                            mts.getattr(crmts.AMBIENT_TEMP),
                         crmts.AMBIENT_TEMP_AVG:
                             mts.getattr(crmts.AMBIENT_TEMP_AVG),
                         crmts.AMBIENT_TEMP_MAX:
                             mts.getattr(crmts.AMBIENT_TEMP_MAX),
                         crmts.AMBIENT_TEMP_MIN:
                             mts.getattr(crmts.AMBIENT_TEMP_MIN),
                         crmts.FRONT_TEMP:
                             mts.getattr(crmts.FRONT_TEMP),
                         crmts.FRONT_TEMP_AVG:
                             mts.getattr(crmts.FRONT_TEMP_AVG),
                         crmts.FRONT_TEMP_MAX:
                             mts.getattr(crmts.FRONT_TEMP_MAX),
                         crmts.FRONT_TEMP_MIN:
                             mts.getattr(crmts.FRONT_TEMP_MIN),
                         crmts.INTERVALS:
                             mts.getattr(crmts.INTERVALS),
                         crmts.IOH1_TEMP:
                             mts.getattr(crmts.IOH1_TEMP),
                         crmts.IOH1_TEMP_AVG:
                             mts.getattr(crmts.IOH1_TEMP_AVG),
                         crmts.IOH1_TEMP_MAX:
                             mts.getattr(crmts.IOH1_TEMP_MAX),
                         crmts.IOH1_TEMP_MIN:
                             mts.getattr(crmts.IOH1_TEMP_MIN),
                         crmts.IOH2_TEMP:
                             mts.getattr(crmts.IOH2_TEMP),
                         crmts.IOH2_TEMP_AVG:
                             mts.getattr(crmts.IOH2_TEMP_AVG),
                         crmts.IOH2_TEMP_MAX:
                             mts.getattr(crmts.IOH2_TEMP_MAX),
                         crmts.IOH2_TEMP_MIN:
                             mts.getattr(crmts.IOH2_TEMP_MIN),
                         crmts.REAR_TEMP:
                             mts.getattr(crmts.REAR_TEMP),
                         crmts.REAR_TEMP_AVG:
                             mts.getattr(crmts.REAR_TEMP_AVG),
                         crmts.REAR_TEMP_MAX:
                             mts.getattr(crmts.REAR_TEMP_MAX),
                         crmts.REAR_TEMP_MIN:
                             mts.getattr(crmts.REAR_TEMP_MIN),
                         crmts.SUSPECT:
                             mts.getattr(crmts.SUSPECT),
                         crmts.THRESHOLDED:
                             mts.getattr(crmts.THRESHOLDED),
                         crmts.TIME_COLLECTED:
                             mts.getattr(crmts.TIME_COLLECTED)
                        }
                    params['temperature_stats'] = temp_stats
        return params

    def get_power_stats(self, task):

        LOG.debug("In _get_power_stats")
        handle = self.connect_ucsm(task)
        #params = {'server': self.service_profile}

        ls_server = handle.GetManagedObject(
                         None,
                         ucssdk.LsServer.ClassId(),
                         {ucssdk.LsServer.DN: self.service_profile},
                         dumpXml=ucssdk.YesOrNo.TRUE
                         )
        # There will be only one service-profile matches the given DN.
        if ls_server and len(ls_server) == 1:
            dn = ls_server[0].getattr(
                    ucssdk.LsServer.PN_DN) + '/board/power-stats'
            compStats = ucssdk.ComputeMbPowerStats
            mb_power_stats = handle.GetManagedObject(
                                 None,
                                 compStats.ClassId(),
                                 {compStats.DN: dn},
                                 dumpXml=ucssdk.YesOrNo.TRUE
                                 )
            if mb_power_stats and len(mb_power_stats) == 1:
                mps = mb_power_stats[0]
                power_stats = {
                    str(compStats.DN):
                        mps.getattr(compStats.DN),
                    str(compStats.CONSUMED_POWER):
                        mps.getattr(compStats.CONSUMED_POWER),
                    str(compStats.CONSUMED_POWER_AVG):
                        mps.getattr(compStats.CONSUMED_POWER_AVG),
                    str(compStats.CONSUMED_POWER_MAX):
                        mps.getattr(compStats.CONSUMED_POWER_MAX),
                    str(compStats.CONSUMED_POWER_MIN):
                        mps.getattr(compStats.CONSUMED_POWER_MIN),
                    str(compStats.INPUT_CURRENT):
                        mps.getattr(compStats.INPUT_CURRENT),
                    str(compStats.INPUT_CURRENT_AVG):
                        mps.getattr(compStats.INPUT_CURRENT_AVG),
                    str(compStats.INPUT_CURRENT_MAX):
                        mps.getattr(compStats.INPUT_CURRENT_MAX),
                    str(compStats.INPUT_CURRENT_MIN):
                        mps.getattr(compStats.INPUT_CURRENT_MIN),
                    str(compStats.INPUT_VOLTAGE):
                        mps.getattr(compStats.INPUT_VOLTAGE),
                    str(compStats.INPUT_VOLTAGE_AVG):
                        mps.getattr(compStats.INPUT_VOLTAGE_AVG),
                    str(compStats.INPUT_VOLTAGE_MAX):
                        mps.getattr(compStats.INPUT_VOLTAGE_MAX),
                    str(compStats.INPUT_VOLTAGE_MIN):
                        mps.getattr(compStats.INPUT_VOLTAGE_MIN),
                    str(compStats.SUSPECT):
                        mps.getattr(compStats.SUSPECT),
                    str(compStats.THRESHOLDED):
                        mps.getattr(compStats.THRESHOLDED),
                    str(compStats.TIME_COLLECTED):
                        mps.getattr(compStats.TIME_COLLECTED)
                    }
                return power_stats
        return None

    def get_location(self, task):
        """Retrieve the server id."""

        handle = self.connect_ucsm(task)
        params = {'server': self.service_profile, 'Location': {}}
        # Need to get the server dn first.
        ls_server = handle.GetManagedObject(
                         None,
                         ucssdk.LsServer.ClassId(),
                         {ucssdk.LsServer.DN: self.service_profile},
                         dumpXml=ucssdk.YesOrNo.TRUE
                         #dumpXml=CONF.cisco.dump_xml
                         )
        # There will be only one service-profile matches the given DN.
        if ls_server and len(ls_server) == 1:
            location = {
                'Ucs': self.hostname,
                'server-id': ls_server[0].getattr(ucssdk.LsServer.PN_DN)
                }
            params['Location'] = location
        return params

    def get_firmware_version(self, task):
        handle = self.connect_ucsm(task)
        ls_server = handle.GetManagedObject(
                        None, None,
                        {ucssdk.LsServer.DN: self.service_profile}
                        )

        params = {"server": ""}

        if ls_server:
            for server in ls_server:
                #get firmware status
                rn_array = [
                    server.getattr(ucssdk.LsServer.PN_DN),
                    ucssdk.ManagedObject(
                        ucssdk.FirmwareStatus.ClassId()).MakeRn()
                    ]
                firmware_ver = handle.GetManagedObject(
                                  None,
                                  ucssdk.FirmwareStatus.ClassId(),
                                  {ucssdk.FirmwareStatus.DN:
                                      ucssdk.UcsUtils.MakeDn(rn_array)}
                                  )
                if firmware_ver:
                    for ver in firmware_ver:
                       params = {
                           ucssdk.FirmwareStatus.DN:
                               ver.getattr(ucssdk.FirmwareStatus.DN),
                           ucssdk.FirmwareStatus.OPER_STATE:
                               ver.getattr(ucssdk.FirmwareStatus.OPER_STATE),
                           ucssdk.FirmwareStatus.PACKAGE_VERSION:
                               ver.getattr(
                                   ucssdk.FirmwareStatus.PACKAGE_VERSION)
                           }
                       LOG.debug(_("UCS server firmware version: %s") % params)
        return params

    def get_inventory(self, task):
        handle = self.connect_ucsm(task)
        ls_server = handle.GetManagedObject(
                        None, None,
                        {ucssdk.LsServer.DN: self.service_profile},
                         dumpXml=ucssdk.YesOrNo.TRUE
                        )

        params = {"server": ""}

        if ls_server:
            for server in ls_server:
                if 'blade' in server.getattr(ucssdk.LsServer.PN_DN):
                    mo_id = ucssdk.ComputeBlade.ClassId()
                else:
                    mo_id = ucssdk.ComputeRackUnit.ClassId()

                compute_unit = handle.GetManagedObject(
                             None,
                             mo_id,
                             {ucssdk.ComputeBlade.DN:
                                 server.getattr(ucssdk.LsServer.PN_DN)},
                             dumpXml=ucssdk.YesOrNo.TRUE
                             )
                if compute_unit:
                    if mo_id is ucssdk.ComputeBlade.ClassId():
                        for unit in compute_unit:
                            blade = ucssdk.ComputeBlade
                            params = {
                                blade.DN:
                                    unit.getattr(blade.DN),
                                blade.CHASSIS_ID:
                                    unit.getattr(blade.CHASSIS_ID),
                                blade.AVAILABLE_MEMORY:
                                   unit.getattr(blade.AVAILABLE_MEMORY),
                                blade.NUM_OF_ADAPTORS:
                                    unit.getattr(blade.NUM_OF_ADAPTORS),
                                blade.NUM_OF_CORES:
                                    unit.getattr(blade.NUM_OF_CORES),
                                blade.NUM_OF_CORES_ENABLED:
                                    unit.getattr(blade.NUM_OF_CORES_ENABLED),
                                blade.NUM_OF_CPUS:
                                    unit.getattr(blade.NUM_OF_CPUS),
                                blade.NUM_OF_ETH_HOST_IFS:
                                    unit.getattr(blade.NUM_OF_ETH_HOST_IFS),
                                blade.NUM_OF_FC_HOST_IFS:
                                    unit.getattr(blade.NUM_OF_FC_HOST_IFS),
                                blade.NUM_OF_THREADS:
                                    unit.getattr(blade.NUM_OF_THREADS),
                                'ProcessorUnits':
                                    get_processor_units(handle, unit),
                                'MemoryArrays':
                                    get_memory_inventory(handle, unit),
                                'StorageUnits':
                                    get_storage_inventory(handle, unit),
                                'AdaptorUnits':
                                    get_adaptor_inventory(handle, unit)
                                }
                    elif mo_id is ucssdk.ComputeRackUnit.ClassId():
                        for unit in compute_unit:
                            unit = ucssdk.ComputeRackUnit
                            params = {
                                unit.DN:
                                    unit.getattr(unit.DN),
                                unit.AVAILABLE_MEMORY:
                                    unit.getattr(unit.AVAILABLE_MEMORY),
                                unit.NUM_OF_ADAPTORS:
                                    unit.getattr(unit.NUM_OF_ADAPTORS),
                                unit.NUM_OF_CORES:
                                    unit.getattr(unit.NUM_OF_CORES),
                                unit.NUM_OF_CORES_ENABLED:
                                    unit.getattr(unit.NUM_OF_CORES_ENABLED),
                                unit.NUM_OF_CPUS:
                                    unit.getattr(unit.NUM_OF_CPUS),
                                unit.NUM_OF_ETH_HOST_IFS:
                                    unit.getattr(unit.NUM_OF_ETH_HOST_IFS),
                                unit.NUM_OF_FC_HOST_IFS:
                                    unit.getattr(unit.NUM_OF_FC_HOST_IFS),
                                unit.NUM_OF_THREADS:
                                    unit.getattr(unit.NUM_OF_THREADS),
                                'ProcessorUnits':
                                    get_processor_units(handle, unit),
                                'MemoryArrays':
                                    get_memory_inventory(handle, unit),
                                'StorageUnits':
                                    get_storage_inventory(handle, unit),
                                'AdaptorUnits':
                                    get_adaptor_inventory(handle, unit)
                                }
        return params
