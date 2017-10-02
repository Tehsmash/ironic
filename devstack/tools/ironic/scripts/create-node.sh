#!/usr/bin/env bash

# **create-nodes**

# Creates baremetal poseur nodes for ironic testing purposes

set -ex

# Make tracing more educational
export PS4='+ ${BASH_SOURCE:-}:${FUNCNAME[0]:-}:L${LINENO:-}:   '

# Keep track of the DevStack directory
TOP_DIR=$(cd $(dirname "$0")/.. && pwd)

while getopts "n:c:i:m:M:d:a:b:e:E:p:o:f:l:L:N:O:" arg; do
    case $arg in
        n) NAME=$OPTARG;;
        c) CPU=$OPTARG;;
        i) INTERFACE_COUNT=$OPTARG;;
        M) INTERFACE_MTU=$OPTARG;;
        m) MEM=$(( 1024 * OPTARG ));;
        # Extra G to allow fuzz for partition table : flavor size and registered
        # size need to be different to actual size.
        d) DISK=$(( OPTARG + 1 ));;
        a) ARCH=$OPTARG;;
        b) BRIDGE=$OPTARG;;
        e) EMULATOR=$OPTARG;;
        E) ENGINE=$OPTARG;;
        p) VBMC_PORT=$OPTARG;;
        o) PDU_OUTLET=$OPTARG;;
        f) DISK_FORMAT=$OPTARG;;
        l) LOGDIR=$OPTARG;;
        L) UEFI_LOADER=$OPTARG;;
        N) UEFI_NVRAM=$OPTARG;;
        O) OOB_MANAGEMENT=$OPTARG;;
    esac
done

shift $(( $OPTIND - 1 ))

if [ -z "$UEFI_LOADER" ] && [ ! -z "$UEFI_NVRAM" ]; then
    echo "Parameter -N (UEFI NVRAM) cannot be used without -L (UEFI Loader)"
    exit 1
fi

LIBVIRT_NIC_DRIVER=${LIBVIRT_NIC_DRIVER:-"virtio"}
LIBVIRT_STORAGE_POOL=${LIBVIRT_STORAGE_POOL:-"default"}
LIBVIRT_CONNECT_URI=${LIBVIRT_CONNECT_URI:-"qemu:///system"}

export VIRSH_DEFAULT_CONNECT_URI=$LIBVIRT_CONNECT_URI

if ! virsh pool-list --all | grep -q $LIBVIRT_STORAGE_POOL; then
    virsh pool-define-as --name $LIBVIRT_STORAGE_POOL dir --target /var/lib/libvirt/images >&2
    virsh pool-autostart $LIBVIRT_STORAGE_POOL >&2
    virsh pool-start $LIBVIRT_STORAGE_POOL >&2
fi

pool_state=$(virsh pool-info $LIBVIRT_STORAGE_POOL | grep State | awk '{ print $2 }')
if [ "$pool_state" != "running" ] ; then
    [ ! -d /var/lib/libvirt/images ] && sudo mkdir /var/lib/libvirt/images
    virsh pool-start $LIBVIRT_STORAGE_POOL >&2
fi

if [ -n "$LOGDIR" ] ; then
    mkdir -p "$LOGDIR"
fi

PREALLOC=
if [ -f /etc/debian_version -a "$DISK_FORMAT" == "qcow2" ]; then
    PREALLOC="--prealloc-metadata"
fi

if [ -n "$LOGDIR" ] ; then
    VM_LOGGING="--console-log $LOGDIR/${NAME}_console.log"
else
    VM_LOGGING=""
fi
VOL_NAME="${NAME}.${DISK_FORMAT}"

UEFI_OPTS=""
if [ ! -z "$UEFI_LOADER" ]; then
    UEFI_OPTS="--uefi-loader $UEFI_LOADER"

    if [ ! -z "$UEFI_NVRAM" ]; then
        UEFI_OPTS+=" --uefi-nvram $UEFI_NVRAM"
    fi
fi

# Create bridge and add VM interface to it.
# Additional interface will be added to this bridge and
# it will be plugged to OVS.
# This is needed in order to have interface in OVS even
# when VM is in shutdown state
INTERFACE_COUNT=${INTERFACE_COUNT:-1}
ADDRESSES=""

for int in $(seq 1 $INTERFACE_COUNT); do
    tapif=tap-${NAME}i${int}
    sudo ip tuntap add dev $tapif mode tap
    sudo ip link set $tapif mtu $INTERFACE_MTU
    sudo ip link set $tapif up
    sudo ovs-vsctl add-port $BRIDGE $tapif
    address=$(ip l sh $tapif | awk '/link\/ether/ { print $2 }')
    ADDRESSES="${ADDRESSES} ${tapif},${address}"
done

if ! virsh list --all | grep -q $NAME; then
    virsh vol-list --pool $LIBVIRT_STORAGE_POOL | grep -q $VOL_NAME &&
        virsh vol-delete $VOL_NAME --pool $LIBVIRT_STORAGE_POOL >&2
    virsh vol-create-as $LIBVIRT_STORAGE_POOL ${VOL_NAME} ${DISK}G --format $DISK_FORMAT $PREALLOC >&2
    volume_path=$(virsh vol-path --pool $LIBVIRT_STORAGE_POOL $VOL_NAME)
    # Pre-touch the VM to set +C, as it can only be set on empty files.
    sudo touch "$volume_path"
    sudo chattr +C "$volume_path" || true
    vm_opts=""
    if [[ -n "$EMULATOR" ]]; then
        vm_opts+="--emulator $EMULATOR "
    fi
    $PYTHON $TOP_DIR/scripts/configure-vm.py \
        --bootdev network --name $NAME --image "$volume_path" \
        --arch $ARCH --cpus $CPU --memory $MEM --libvirt-nic-driver $LIBVIRT_NIC_DRIVER \
        --disk-format $DISK_FORMAT $VM_LOGGING --engine $ENGINE $UEFI_OPTS $vm_opts \
        --interface-count $INTERFACE_COUNT >&2

    # Createa Virtual BMC for the node if IPMI is used
    if [[ $(type -P vbmc) != "" ]]; then
        vbmc add $NAME --port $VBMC_PORT
        vbmc start $NAME
    fi
fi

cat << EOF
 -
  name: ${NAME}
  driver: pxe_ipmitool
  driver_info:
    deploy_kernel:
    deploy_ramdisk:
EOF

if [[ "$OOB_MANAGEMENT" == "vbmc" ]]; then
  vbmc_ip=127.0.0.1
  cat << EOF
    ipmi_address: ${vbmc_ip}
    ipmi_username: admin
    ipmi_password: password
    ipmi_port: ${VBMC_PORT}
EOF
fi

if [[ "$OOB_MANAGEMENT" == "vpdu" ]]; then
  vpdu_ip=127.0.0.1
  cat << EOF
    snmp_address: ${vpdu_ip}
    snmp_driver: apc_rackpdu
    snmp_port: 1161
    snmp_protocol: 2c
    snmp_community: private
    snmp_outlet: ${PDU_OUTLET}
EOF
fi

if [[ "$OOB_MANAGEMENT" == "redfish" ]]; then
  red_ip=127.0.0.1
  cat << EOF
    redfish_address: ${red_ip}
    redfish_username: admin
    redfish_password: password
    redfish_system_id: /redfish/v1/Systems/${NAME}
EOF
fi

cat << EOF
  properties:
    capabilities: 'boot_option:local'
    cpus: ${CPU}
    local_gb: ${DISK}
    memory_mb: ${MEM}
    cpu_arch: x86_64
  ports:
EOF

switch_mac=$(ip l sh $BRIDGE | awk '/link\/ether/ { print $2 }')

for address_name in $ADDRESSES; do
  name=$(echo "$address_name" | cut -d "," -f 1)
  address=$(echo "$address_name" | cut -d "," -f 2)

  cat << EOF
    -
     address: ${address}
     local_link_connection:
       switch_info: ${BRIDGE}
       port_id: ${name}
       switch_id: ${switch_mac}
     pxe_enabled: True
EOF

done
