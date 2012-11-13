# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 Nicira Networks, Inc.
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
# @author: Shifu Miao, Ruijie Networks, Inc.

from quantum.db import api as db
from quantum.plugins.openvswitch.ruijie import ruijie_db as ruijie_db
from quantum.plugins.openvswitch import ovs_db
from quantum.plugins.openvswitch.ruijie import ruijie_vlan

def setUp():
    db.clear_db()

def tearDown():
    db.clear_db()
    
def TestSwitchEthBinding():
    binding = ruijie_db.get_ruijie_switch_eth_bindings()
    if binding != []:
        assert 0
    ruijie_db.add_ruijie_switch_eth_binding("192.168.21.35", "0050.56bc.0003", "GigabitEthernet 3/0/20");
    binding = ruijie_db.get_ruijie_switch_eth_binding("0050.56bc.0003")
    if binding == []:
        assert 0
    ruijie_db.remove_ruijie_switch_eth_binding("192.168.21.35", "0050.56bc.0003", "GigabitEthernet 3/0/20")
    binding = ruijie_db.get_ruijie_switch_eth_bindings()
    if binding != []:
        assert 0

def TestVmEthBinding():
    binding = ruijie_db.get_ruijie_vm_eth_bindings()
    if binding != []:
        assert 0
    ruijie_db.add_ruijie_vm_eth_binding("123456789", "0050.56bc.0003");
    binding = ruijie_db.get_ruijie_vm_eth_binding("123456789")
    if binding == []:
        assert 0
    ruijie_db.remove_ruijie_vm_eth_binding("123456789", "0050.56bc.0003")
    binding = ruijie_db.get_ruijie_vm_eth_bindings()
    if binding != []:
        assert 0

def TestRuijieVlanBinding():
    binding = ruijie_db.get_ruijie_vlan_bindings()
    if binding != []:
        assert 0
    ruijie_db.add_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", "VLAN100", "aaaa")
    binding = ruijie_db.get_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", "VLAN100")
    if binding == []:
        assert 0
    ruijie_db.remove_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", "VLAN100", "aaaa")
    binding = ruijie_db.get_ruijie_vlan_bindings()
    if binding != []:
        assert 0

def TestRuijieVlanSetting():
    ruijie_db.add_ruijie_switch_eth_binding("192.168.21.35", "0050.56bc.0003", "GigabitEthernet 3/0/20");
    ruijie_db.add_ruijie_vm_eth_binding("intf_id", "0050.56bc.0003");
    ovs_db.add_vlan_binding(100, "network_id")
    ruijie_vlan.set_ruijie_vlan("intf_id", "network_id")
    binding = ruijie_db.get_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", 100)
    if binding == []:
        assert 0

def TestRuijieVlanUnsetting():
    db.clear_db()
    net = db.network_create("miaosf", "net1")
    port = db.port_create(net.uuid)
    db.port_set_attachment(port.uuid, net.uuid, "intf_id")
    
    ruijie_db.add_ruijie_switch_eth_binding("192.168.21.35", "0050.56bc.0003", "GigabitEthernet 3/0/20");
    ruijie_db.add_ruijie_vm_eth_binding("intf_id", "0050.56bc.0003");
    
    ovs_db.add_vlan_binding(200, net.uuid)
    ruijie_vlan.set_ruijie_vlan("intf_id", net.uuid)
    binding = ruijie_db.get_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", 200)
    if binding == []:
        assert 0
    ruijie_vlan.unset_ruijie_vlan(net.uuid, port.uuid)
    binding = ruijie_db.get_ruijie_vlan_binding("192.168.21.35", "GigabitEthernet 3/0/20", 200)
    if binding != []:
        assert 0