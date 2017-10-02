#!/usr/bin/env bash

# **cleanup-nodes**

# Cleans up baremetal poseur nodes and volumes created during ironic setup
# Assumes calling user has proper libvirt group membership and access.

set -ex

# Make tracing more educational
export PS4='+ ${BASH_SOURCE:-}:${FUNCNAME[0]:-}:L${LINENO:-}:   '

LIBVIRT_STORAGE_POOL=${LIBVIRT_STORAGE_POOL:-"default"}
LIBVIRT_CONNECT_URI=${LIBVIRT_CONNECT_URI:-"qemu:///system"}

NAME=$1
VM_INTERFACE_COUNT=$2

export VIRSH_DEFAULT_CONNECT_URI=$LIBVIRT_CONNECT_URI

VOL_NAME="$NAME.qcow2"
virsh list | grep -q $NAME && virsh destroy $NAME
virsh list --inactive | grep -q $NAME && virsh undefine $NAME --nvram

# Delete the Virtual BMC
if [[ $(type -P vbmc) != "" ]]; then
    vbmc list | grep -a $NAME && vbmc delete $NAME
fi

if virsh pool-list | grep -q $LIBVIRT_STORAGE_POOL ; then
    virsh vol-list $LIBVIRT_STORAGE_POOL | grep -q $VOL_NAME &&
        virsh vol-delete $VOL_NAME --pool $LIBVIRT_STORAGE_POOL
fi

for i in $(seq 1 $VM_INTERFACE_COUNT); do
  sudo ip tuntap del dev tap-${NAME}i${i} mode tap 
done
