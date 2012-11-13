#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 Nicira Networks, Inc.
# Copyright 2012 Ruijie network, Inc.
# All Rights Reserved.
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
#
# @author: Pan Qijun, Ruijie Networks, Inc.

import logging
import sys
import time

import eventlet
from sqlalchemy.ext import sqlsoup

from quantum.agent import rpc as agent_rpc
from quantum.agent.linux import ip_lib
from quantum.agent.linux import ovs_lib
from quantum.agent.linux import utils
from quantum.common import constants as q_const
from quantum.common import config as logging_config
from quantum.common import topics
from quantum.openstack.common import cfg
from quantum.openstack.common import context
from quantum.openstack.common import rpc
from quantum.openstack.common.rpc import dispatcher
from quantum.plugins.rgos.common import config
from quantum.plugins.rgos.common import constants
from quantum.db import models_v2
import quantum.db.api as db
from quantum.plugins.rgos.db import rgos_db
from quantum.plugins.rgos.vlan import vlan_mgr as rgos_vlanmgr
from quantum.plugins.rgos.switch import switch_driver
from quantum.plugins.rgos.ssh import sshclient


logging.basicConfig()
LOG = logging.getLogger(__name__)


# A placeholder for dead vlans.
DEAD_VLAN_TAG = "4095"

# A class to represent a VIF (i.e., a port that has 'iface-id' and 'vif-mac'
# attributes set).
class LocalVLANMapping:
    def __init__(self, vlan, network_type, physical_network, segmentation_id,
                 vif_ports=None):
        if vif_ports is None:
            vif_ports = {}
        self.vlan = vlan
        self.network_type = network_type
        self.physical_network = physical_network
        self.segmentation_id = segmentation_id
        self.vif_ports = vif_ports

    def __str__(self):
        return ("lv-id = %s type = %s phys-net = %s phys-id = %s" %
                (self.vlan, self.network_type, self.physical_network,
                 self.segmentation_id))

class Port(object):
    """Represents a quantum port.

    Class stores port data in a ORM-free way, so attributres are
    still available even if a row has been deleted.
    """

    def __init__(self, p):
        self.id = p.id
        self.network_id = p.network_id
        self.device_id = p.device_id
        self.admin_state_up = p.admin_state_up
        self.status = p.status

    def __eq__(self, other):
        '''Compare only fields that will cause us to re-wire.'''
        try:
            return (self and other
                    and self.id == other.id
                    and self.admin_state_up == other.admin_state_up)
        except:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.id)


class OVSQuantumAgent(object):
    '''Implements OVS-based VLANs networks.

    local bridges is created: an integration bridge (defaults to
    'br-int'). An additional bridge is created for each physical 
    network interface used for VLANs networks.

    All VM VIFs are plugged into the integration bridge. VM VIFs on a
    given virtual network share a common "local" VLAN (i.e. not
    propagated externally). The VLAN id of this local VLAN is mapped
    to the physical networking details realizing that virtual network.

    For each virtual networks realized as a VLANs network, a
    veth is used to connect the local VLAN on the integration bridge
    with the physical network bridge, with flow rules adding,
    modifying, or stripping VLAN tags as necessary.
    '''

    # Lower bound on available vlans.
    MIN_VLAN_TAG = 1

    # Upper bound on available vlans.
    MAX_VLAN_TAG = 4094

    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'

    def __init__(self, integ_br, local_ip,
                 bridge_mappings, root_helper,
                 polling_interval, reconnect_interval, lldp_timeout, rpc):
        '''Constructor.

        :param integ_br: name of the integration bridge.
        :param local_ip: local IP address of this hypervisor.
        :param bridge_mappings: mappings from phyiscal interface to bridge.
        :param root_helper: utility to use when running shell cmds.
        :param polling_interval: interval (secs) to poll DB.
        :param reconnect_internal: retry interval (secs) on DB error.
        :param lldp_timeout: interval (minutes) to update lldp neighbors.
        :param rpc: if True use RPC interface to interface with plugin.
        '''
        self.root_helper = root_helper
        self.available_local_vlans = set(
            xrange(OVSQuantumAgent.MIN_VLAN_TAG,
                   OVSQuantumAgent.MAX_VLAN_TAG))
        self.setup_integration_br(integ_br)
        self.setup_physical_bridges(bridge_mappings)
        self.local_vlan_map = {}
        self.polling_interval = polling_interval
        self.reconnect_interval = reconnect_interval
        self.lldp_timeout = lldp_timeout
        self.local_ip = local_ip

        self.rpc = rpc
        if rpc:
            self.setup_rpc(integ_br)

    def setup_rpc(self, integ_br):
        mac = utils.get_interface_mac(integ_br)
        self.agent_id = '%s%s' % ('ovs', (mac.replace(":", "")))
        self.topic = topics.AGENT
        self.plugin_rpc = agent_rpc.PluginApi(topics.PLUGIN)

        # RPC network init
        self.context = context.RequestContext('quantum', 'quantum',
                                              is_admin=False)
        # Handle updates from service
        self.dispatcher = self.create_rpc_dispatcher()
        # Define the listening consumers for the agent
        consumers = [[topics.PORT, topics.UPDATE],
                     [topics.NETWORK, topics.DELETE]]
        self.connection = agent_rpc.create_consumers(self.dispatcher,
                                                     self.topic,
                                                     consumers)

    # Used for get mac by linux vnic
    def get_interface_mac_list(self):
        net = {}
        f = open("/proc/net/dev")
        lines = f.readlines()
        f.close()
        for line in lines[2:]:
            con = line.split()
            name = con[0].rstrip(":")
            net[name] = utils.get_interface_mac(name)
        
        return net
    
    # Used for get mac by ubuntu nic device
    def get_eth_mac_list(self):
        net = {}
        f = open("/proc/net/dev")
        lines = f.readlines()
        f.close()
        for line in lines[2:]:
            con = line.split()
            name = con[0].rstrip(":")
            if name[0:3] == "eth":
                net[name] = utils.get_interface_mac(name)
        
        return net

    def get_net_uuid(self, vif_id):
        for network_id, vlan_mapping in self.local_vlan_map.iteritems():
            if vif_id in vlan_mapping.vif_ports:
                return network_id

    def network_delete(self, context, **kwargs):
        LOG.debug("network_delete received")
        network_id = kwargs.get('network_id')
        LOG.debug("Delete %s", network_id)
        # The network may not be defined on this agent
        lvm = self.local_vlan_map.get(network_id)
        if lvm:
            self.reclaim_local_vlan(network_id, lvm)
        else:
            LOG.debug("Network %s not used on agent.", network_id)

    def port_update(self, context, **kwargs):
        LOG.debug("port_update received")
        port = kwargs.get('port')
        network_type = kwargs.get('network_type')
        segmentation_id = kwargs.get('segmentation_id')
        physical_network = kwargs.get('physical_network')
        vif_port = self.int_br.get_vif_port_by_id(port['id'])
        self.treat_vif_port(vif_port, port['id'], port['network_id'],
                            network_type, physical_network,
                            segmentation_id, port['admin_state_up'])


    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return dispatcher.RpcDispatcher([self])

    def provision_local_vlan(self, net_uuid, network_type, physical_network,
                             segmentation_id):
        '''Provisions a local VLAN.

        :param net_uuid: the uuid of the network associated with this vlan.
        :param network_type: the network type ('vlan', 'local')
        :param physical_network: the physical network for 'vlan'
        :param segmentation_id: the VID for 'vlan'
        '''

        if not self.available_local_vlans:
            LOG.error("No local VLAN available for net-id=%s", net_uuid)
            return
        lvid = self.available_local_vlans.pop()
        LOG.info("Assigning %s as local vlan for net-id=%s", lvid, net_uuid)
        self.local_vlan_map[net_uuid] = LocalVLANMapping(lvid, network_type,
                                                         physical_network,
                                                         segmentation_id)


        if network_type == constants.TYPE_VLAN:
            if physical_network in self.phys_brs:
                # outbound
                br = self.phys_brs[physical_network]
                br.add_flow(priority=4,
                            in_port=self.phys_ofports[physical_network],
                            dl_vlan=lvid,
                            actions="mod_vlan_vid:%s,normal" % segmentation_id)
                # inbound
                self.int_br.add_flow(priority=3,
                                     in_port=self.
                                     int_ofports[physical_network],
                                     dl_vlan=segmentation_id,
                                     actions="mod_vlan_vid:%s,normal" % lvid)
            else:
                LOG.error("Cannot provision VLAN network for net-id=%s "
                          "- no bridge for physical_network %s", net_uuid,
                          physical_network)
        elif network_type == constants.TYPE_LOCAL:
            # no flows needed for local networks
            pass
        else:
            LOG.error("Cannot provision unknown network type %s for "
                      "net-id=%s", network_type, net_uuid)

    def reclaim_local_vlan(self, net_uuid, lvm):
        '''Reclaim a local VLAN.

        :param net_uuid: the network uuid associated with this vlan.
        :param lvm: a LocalVLANMapping object that tracks (vlan, lsw_id,
            vif_ids) mapping.'''
        LOG.info("Reclaiming vlan = %s from net-id = %s", lvm.vlan, net_uuid)

        if lvm.network_type == constants.TYPE_VLAN:
            print lvm.physical_network
            if lvm.physical_network in self.phys_brs:
                # outbound
                br = self.phys_brs[lvm.physical_network]
                br.delete_flows(in_port=self.phys_ofports[lvm.
                                                          physical_network],
                                dl_vlan=lvm.vlan)
                # inbound
                br = self.int_br
                br.delete_flows(in_port=self.int_ofports[lvm.physical_network],
                                dl_vlan=lvm.segmentation_id)
        elif lvm.network_type == constants.TYPE_LOCAL:
            # no flows needed for local networks
            pass
        else:
            LOG.error("Cannot reclaim unknown network type %s for net-id=%s",
                      lvm.network_type, net_uuid)

        del self.local_vlan_map[net_uuid]
        self.available_local_vlans.add(lvm.vlan)

    # modify by panqijun@ruijie.com.cn
    def update_vm_vlan(self, net_uuid, new_seg_id):
        '''
        update VM vlan
        '''
        LOG.info("update vm vlan net_id %s seg_id %s", net_uuid, new_seg_id)
        try:
            lvm = self.local_vlan_map[net_uuid]
        except KeyError:
            return
        
        if lvm == None:
            return
        if lvm.network_type == constants.TYPE_VLAN:
            # outbound
            br = self.phys_brs[lvm.physical_network]
            br.delete_flows(in_port=self.phys_ofports[lvm.physical_network], dl_vlan=lvm.vlan)
            br.add_flow(priority=4,
                        in_port=self.phys_ofports[lvm.physical_network],
                        dl_vlan=lvm.vlan,
                        actions="mod_vlan_vid:%s,normal" % new_seg_id)
            # inbound
            br = self.int_br
            br.delete_flows(in_port=self.int_ofports[lvm.physical_network], 
                            dl_vlan=lvm.segmentation_id)
            
            self.int_br.add_flow(priority=3,
                                 in_port=self.int_ofports[lvm.physical_network],
                                 dl_vlan=new_seg_id,
                                 actions="mod_vlan_vid:%s,normal" % lvm.vlan)
            # update segmentation_id in local vlan mapping
            lvm.segmentation_id = new_seg_id
            return
        elif lvm.network_type == constants.TYPE_LOCAL:
            # not support
            pass
        else:
            LOG.error("Cannot reclaim unknown network type %s for net-id=%s",
                      lvm.network_type, net_uuid)
    
    def update_ruijie_vlan(self, vif, net_uuid, old_seg_id):
        LOG.debug('update ruijie vlan vif %s net_id %s seg_id %s', vif, net_uuid, old_seg_id) 
        switch_driver.update_ruijie_vlan(vif, net_uuid, old_seg_id)

    def update_vlan(self, old_net_bindings, vm_eth_bindings):
        new_net_bindings = rgos_vlanmgr.get_network_bindings()
        vif_ids = set(vm_eth_bindings.keys())
        vif_net_bindings = dict((vif_id, self.get_net_uuid(vif_id)) for vif_id in vif_ids)
        LOG.debug('old_net_bindings %s', old_net_bindings) 
        LOG.debug('new_net_bindings %s', new_net_bindings) 
        LOG.debug('vif_ids %s', vif_ids) 
        LOG.debug('vif_net_bindings %s', vif_net_bindings) 
        
        # update vm flows rules
        for net_id, bind in new_net_bindings.items():
            if net_id in old_net_bindings:
                if bind.segmentation_id == old_net_bindings[net_id].segmentation_id:
                    continue
                if bind.network_type != constants.TYPE_VLAN:
                    continue
                self.update_vm_vlan(net_id, bind.segmentation_id)
        
        # update ruijie vlan 
        for vif, vif_net_id in vif_net_bindings.items():
            if vif_net_id in new_net_bindings and vif_net_id in old_net_bindings:
                new_vid = new_net_bindings[vif_net_id].segmentation_id
                old_vid = old_net_bindings[vif_net_id].segmentation_id
                if new_vid != old_vid:
                    self.update_ruijie_vlan(vif, vif_net_id, old_vid)

                
        return new_net_bindings
            
    def port_bound(self, port, net_uuid,
                   network_type, physical_network, segmentation_id):
        '''Bind port to net_uuid/lsw_id and install flow for inbound traffic
        to vm.

        :param port: a ovslib.VifPort object.
        :param net_uuid: the net_uuid this port is to be associated with.
        :param network_type: the network type ('vlan', local')
        :param physical_network: the physical network for 'vlan' 
        :param segmentation_id: the VID for 'vlan' 
        '''
        if net_uuid not in self.local_vlan_map:
            self.provision_local_vlan(net_uuid, network_type,
                                      physical_network, segmentation_id)
        lvm = self.local_vlan_map[net_uuid]
        lvm.vif_ports[port.vif_id] = port

        self.int_br.set_db_attribute("Port", port.port_name, "tag",
                                     str(lvm.vlan))
        if int(port.ofport) != -1:
            self.int_br.delete_flows(in_port=port.ofport)
        # modify by panqijun@ruijie.com.cn
        self.set_ruijie_vlan(port.vif_id, net_uuid)

    def port_unbound(self, vif_id, net_uuid=None):
        '''Unbind port.

        Removes corresponding local vlan mapping object if this is its last
        VIF.

        :param vif_id: the id of the vif
        :param net_uuid: the net_uuid this port is associated with.'''
        if net_uuid is None:
            net_uuid = self.get_net_uuid(vif_id)

        if not self.local_vlan_map.get(net_uuid):
            LOG.info('port_unbound() net_uuid %s not in local_vlan_map',
                     net_uuid)
            return
        lvm = self.local_vlan_map[net_uuid]

        if vif_id in lvm.vif_ports:
            del lvm.vif_ports[vif_id]
        else:
            LOG.info('port_unbound: vif_id %s not in local_vlan_map', vif_id)

        if not lvm.vif_ports:
            self.reclaim_local_vlan(net_uuid, lvm)
        # modify by panqijun@ruijie.com.cn
        self.unset_ruijie_vlan(vif_id, net_uuid)
        
    def port_dead(self, port):
        '''Once a port has no binding, put it on the "dead vlan".

        :param port: a ovs_lib.VifPort object.'''
        self.int_br.set_db_attribute("Port", port.port_name, "tag",
                                     DEAD_VLAN_TAG)
        self.int_br.add_flow(priority=2, in_port=port.ofport, actions="drop")

    def setup_integration_br(self, integ_br):
        '''Setup the integration bridge.

        Create patch ports and remove all existing flows.

        :param integ_br: the name of the integration bridge.'''
        self.int_br = ovs_lib.OVSBridge(integ_br, self.root_helper)
        self.int_br.delete_port("patch-tun")
        self.int_br.remove_all_flows()
        # switch all traffic using L2 learning
        self.int_br.add_flow(priority=1, actions="normal")


    def setup_physical_bridges(self, bridge_mappings):
        '''Setup the physical network bridges.

        Creates phyiscal network bridges and links them to the
        integration bridge using veths.

        :param bridge_mappings: map physical network names to bridge names.'''
        self.phys_brs = {}
        self.int_ofports = {}
        self.phys_ofports = {}
        ip_wrapper = ip_lib.IPWrapper(self.root_helper)
        for physical_network, bridge in bridge_mappings.iteritems():
            # setup physical bridge
            if not ip_lib.device_exists(bridge, self.root_helper):
                LOG.error("Bridge %s for physical network %s does not exist",
                          bridge, physical_network)
                sys.exit(1)
            br = ovs_lib.OVSBridge(bridge, self.root_helper)
            br.remove_all_flows()
            br.add_flow(priority=1, actions="normal")
            self.phys_brs[physical_network] = br

            # create veth to patch physical bridge with integration bridge
            int_veth_name = constants.VETH_INTEGRATION_PREFIX + bridge
            self.int_br.delete_port(int_veth_name)
            phys_veth_name = constants.VETH_PHYSICAL_PREFIX + bridge
            br.delete_port(phys_veth_name)
            if ip_lib.device_exists(int_veth_name, self.root_helper):
                ip_lib.IPDevice(int_veth_name, self.root_helper).link.delete()
            int_veth, phys_veth = ip_wrapper.add_veth(int_veth_name,
                                                      phys_veth_name)
            self.int_ofports[physical_network] = self.int_br.add_port(int_veth)
            self.phys_ofports[physical_network] = br.add_port(phys_veth)

            # block all untranslated traffic over veth between bridges
            self.int_br.add_flow(priority=2,
                                 in_port=self.int_ofports[physical_network],
                                 actions="drop")
            br.add_flow(priority=2,
                        in_port=self.phys_ofports[physical_network],
                        actions="drop")

            # enable veth to pass traffic
            int_veth.link.set_up()
            phys_veth.link.set_up()


    def vm_eth_bind(self, vif, eth_mac):
        LOG.debug('add vm eth binding, vif: %s eth_mac: %s', vif, eth_mac)
        net_uuid = self.get_net_uuid(vif)
        rgos_db.add_ruijie_vm_eth_binding(vif, eth_mac)

        # update Ruijie switch
        switch_binding = rgos_db.get_ruijie_switch_eth_binding(eth_mac)
        if switch_binding == []:
            return;
        ip = switch_binding[0].ip_address
        ifx = switch_binding[0].port_id
        ovs_binding = rgos_vlanmgr.get_network_binding(None, net_uuid)
        if ovs_binding == None:
            return
        vlan = ovs_binding.segmentation_id
        LOG.info("the switch ip is %s, ifx is %s, vlan is %s" 
                 % (ip, ifx, vlan))
        ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, vlan)
        if ruijie_vlan_binding == []:
            LOG.info("to set the vlan of ruijie switch now")
            switch_driver.set_switch_vlan(ip, 22, ifx, vlan)
        rgos_db.add_ruijie_vlan_binding(ip, ifx, vlan, vif)

    def vm_eth_unbind(self, vif, eth_mac):
        LOG.debug('del vm eth binding, vif: %s eth_mac: %s', vif, eth_mac)
        net_uuid = self.get_net_uuid(vif)
        rgos_db.remove_ruijie_vm_eth_binding(vif, eth_mac)

        # update Ruijie switch
        switch_binding = rgos_db.get_ruijie_switch_eth_binding(eth_mac)
        if switch_binding == []:
            return;
        ip = switch_binding[0].ip_address
        ifx = switch_binding[0].port_id
        ovs_binding = rgos_vlanmgr.get_network_binding(None, net_uuid)
        if ovs_binding == None:
            return
        vlan = ovs_binding.segmentation_id
        LOG.info("the switch ip is %s, ifx is %s, vlan is %s" 
                 % (ip, ifx, vlan))
        rgos_db.remove_ruijie_vlan_binding(ip, ifx, vlan, vif)
        ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, vlan)
        if ruijie_vlan_binding == []:
            LOG.info("to set the vlan of ruijie switch now")
            switch_driver.unset_switch_vlan(ip, 22, ifx, vlan)

    def vm_eth_binding(self, old_bindings):
        vifs = self.int_br.get_vif_port_set()
        eths_mac = self.get_eth_mac_list()
        new_bindings = {}
        port_names = []

        # get eth in first physical network bridge
        for physical_network in self.phys_brs:
            port_names = self.phys_brs[physical_network].get_port_name_list()
            if port_names != None:
                break;
            # get eth in integration bridge
            else:
                port_names = self.int_br.get_port_name_list() # ['eth1']

        # remove VM interface form port_names
        for name in port_names:
            external_ids = self.int_br.db_get_map("Interface", name, "external_ids")
            if "attached-mac" in external_ids:
                port_names.remove(name)

        # find Physical Ethernet card in OVS Bridge build new vm eth bindings
        for name in port_names:
            if name in eths_mac:
                for vif in vifs:
                    new_bindings[vif] = eths_mac[name]
                break
        old_bindings_vifs = set(old_bindings.keys())
        new_bindings_vifs = set(new_bindings.keys())
        add_bindings_vifs = new_bindings_vifs - old_bindings_vifs
        del_bindings_vifs = old_bindings_vifs - new_bindings_vifs
        add_bindings = dict((vif, new_bindings[vif]) for vif in add_bindings_vifs)
        del_bindings = dict((vif, old_bindings[vif]) for vif in del_bindings_vifs)
        LOG.debug('old vm eth bindings: %s', old_bindings)
        LOG.debug('new vm eth bindings: %s', new_bindings)
        LOG.debug('add vm eth bindings: %s', add_bindings)
        LOG.debug('del vm eth bindings: %s', del_bindings)

        # deal vm eth change
        for vif, eth_mac in new_bindings.items():
            if vif in old_bindings:
                if old_bindings[vif] == eth_mac:
                    continue
                self.vm_eth_unbind(vif, old_bindings[vif])
            self.vm_eth_bind(vif, eth_mac)
            
        # deal vm eth binding del
        for vif, eth_mac in del_bindings.items():
            self.vm_eth_unbind(vif, eth_mac)
        
        # deal vm eth binding add
        for vif, eth_mac in add_bindings.items():
            self.vm_eth_bind(vif, eth_mac)
        
        return new_bindings

    def set_ruijie_vlan(self, vif_id, net_id):
        LOG.debug('Try to set ruijie vlan, vif_id %s, net_id %s', vif_id, net_id)
        switch_driver.set_ruijie_vlan(vif_id, net_id)
        
    def unset_ruijie_vlan(self, vif_id, net_id):
        LOG.debug('Try to unset ruijie vlan, vif_id %s, net_id %s', vif_id, net_id)
        switch_driver.unset_ruijie_vlan(vif_id, net_id)


    def update_ports(self, registered_ports):
        ports = self.int_br.get_vif_port_set()
        if ports == registered_ports:
            return
        added = ports - registered_ports
        removed = registered_ports - ports
        return {'current': ports,
                'added': added,
                'removed': removed}

    def treat_vif_port(self, vif_port, port_id, network_id, network_type,
                       physical_network, segmentation_id, admin_state_up):
        if vif_port:
            if admin_state_up:
                self.port_bound(vif_port, network_id, network_type,
                                physical_network, segmentation_id)
            else:
                self.port_dead(vif_port)
        else:
            LOG.debug("No VIF port for port %s defined on agent.", port_id)

    def treat_devices_added(self, devices):
        resync = False
        for device in devices:
            LOG.info("Port %s added", device)
            try:
                details = self.plugin_rpc.get_device_details(self.context,
                                                             device,
                                                             self.agent_id)
            except Exception as e:
                LOG.debug("Unable to get port details for %s: %s", device, e)
                resync = True
                continue
            port = self.int_br.get_vif_port_by_id(details['device'])
            if 'port_id' in details:
                LOG.info("Port %s updated. Details: %s", device, details)
                self.treat_vif_port(port, details['port_id'],
                                    details['network_id'],
                                    details['network_type'],
                                    details['physical_network'],
                                    details['segmentation_id'],
                                    details['admin_state_up'])
            else:
                LOG.debug("Device %s not defined on plugin", device)
                if (port and int(port.ofport) != -1):
                    self.port_dead(port)
        return resync

    def treat_devices_removed(self, devices):
        resync = False
        for device in devices:
            LOG.info("Attachment %s removed", device)
            try:
                details = self.plugin_rpc.update_device_down(self.context,
                                                             device,
                                                             self.agent_id)
            except Exception as e:
                LOG.debug("port_removed failed for %s: %s", device, e)
                resync = True
            if details['exists']:
                LOG.info("Port %s updated.", device)
                # Nothing to do regarding local networking
            else:
                LOG.debug("Device %s not defined on plugin", device)
                self.port_unbound(device)
        return resync

    def process_network_ports(self, port_info):
        resync_a = False
        resync_b = False
        if 'added' in port_info:
            resync_a = self.treat_devices_added(port_info['added'])
        if 'removed' in port_info:
            resync_b = self.treat_devices_removed(port_info['removed'])
        # If one of the above opertaions fails => resync with plugin
        return (resync_a | resync_b)

    def update_lldp_neighbor(self):
        resync = False
        LOG.debug('Try to update all host lldp neighbors ')
        ret = switch_driver.update_server_lldp()
        if ret == 0:
            resync = True

        return (resync)


    def rpc_loop(self):
        sync = True
        cnt = 0
        ports = set()
        vm_eth_bindings = {}
        old_net_bindings = {}
        scan = (self.lldp_timeout * 60)/self.polling_interval

        while True:
            start = time.time()
            if sync:
                LOG.info("Agent out of sync with plugin!")
                ports.clear()
                sync = False
            
            # update vm eth binding
            LOG.debug('update vm eth bindings in rpc_roop') 
            vm_eth_bindings = self.vm_eth_binding(vm_eth_bindings)
            
            # update vlan
            old_net_bindings = self.update_vlan(old_net_bindings, vm_eth_bindings)

            port_info = self.update_ports(ports)
            # notify plugin about port deltas
            if port_info:
                LOG.debug("Agent loop has new devices!")
                # If treat devices fails - indicates must resync with plugin
                sync = self.process_network_ports(port_info)
                ports = port_info['current']
            
            # update lldp neighbor info between kvm and switch
            if cnt >= scan:
                LOG.debug("Agent loop start update lldp info !")
                self.update_lldp_neighbor()
                cnt = 0
            else:
                cnt = cnt +1
            
            # sleep till end of polling interval
            elapsed = (time.time() - start)
            if (elapsed < self.polling_interval):
                time.sleep(self.polling_interval - elapsed)
            else:
                LOG.debug("Loop iteration exceeded interval (%s vs. %s)!",
                          self.polling_interval, elapsed)


    def daemon_loop(self, db_connection_url):
        if self.rpc:
            self.rpc_loop()

def main():
    eventlet.monkey_patch()
    cfg.CONF(args=sys.argv, project='quantum')

    # (TODO) gary - swap with common logging
    logging_config.setup_logging(cfg.CONF)

    integ_br = cfg.CONF.RGOS.integration_bridge
    db_connection_url = cfg.CONF.DATABASE.sql_connection
    polling_interval = cfg.CONF.AGENT.polling_interval
    reconnect_interval = cfg.CONF.DATABASE.reconnect_interval
    root_helper = cfg.CONF.AGENT.root_helper
    rpc = cfg.CONF.AGENT.rpc
    local_ip = cfg.CONF.RGOS.local_ip
    lldp_timeout = cfg.CONF.AGENT.lldp_timeout
    
    options = {"sql_connection": db_connection_url}
    options.update({"sql_max_retries": -1})
    options.update({"reconnect_interval": reconnect_interval})
    db.configure_db(options)
    
    bridge_mappings = {}
    for mapping in cfg.CONF.RGOS.bridge_mappings:
        mapping = mapping.strip()
        if mapping != '':
            try:
                physical_network, bridge = mapping.split(':')
                bridge_mappings[physical_network] = bridge
                LOG.info("Physical network %s mapped to bridge %s",
                         physical_network, bridge)
            except ValueError as ex:
                LOG.error("Invalid bridge mapping: \'%s\' - %s", mapping, ex)
                sys.exit(1)

    plugin = OVSQuantumAgent(integ_br, local_ip, bridge_mappings,
                             root_helper, polling_interval, 
                             reconnect_interval, lldp_timeout, rpc)

    # Start everything.
    plugin.daemon_loop(db_connection_url)

    sys.exit(0)

if __name__ == "__main__":
    main()
