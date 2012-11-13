# vim: tabstop=4 shiftwidth=4 softtabstop=4
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
# @author: Shifu Miao, Ruijie Networks, Inc.


from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from quantum.db.models_v2 import model_base

from quantum.db import model_base
from quantum.db.model_base import BASEV2


class RuijieVlanAllocation(model_base.BASEV2):
    """Represents allocation state of vlan_id on physical network"""
    __tablename__ = 'ruijie_vlan_allocations'

    physical_network = Column(String(64), nullable=False, primary_key=True)
    vlan_id = Column(Integer, nullable=False, primary_key=True,
                     autoincrement=False)
    allocated = Column(Boolean, nullable=False)

    def __init__(self, physical_network, vlan_id):
        self.physical_network = physical_network
        self.vlan_id = vlan_id
        self.allocated = False

    def __repr__(self):
        return "<VlanAllocation(%s,%d,%s)>" % (self.physical_network,
                                               self.vlan_id, self.allocated)


class RuijieNetworkBinding(model_base.BASEV2):
    """Represents binding of virtual network to physical realization"""
    __tablename__ = 'ruijie_network_bindings'

    network_id = Column(String(36),
                        ForeignKey('networks.id', ondelete="CASCADE"),
                        primary_key=True)

    network_type = Column(String(32), nullable=False)
    physical_network = Column(String(64))
    segmentation_id = Column(Integer)  # vlan_id

    def __init__(self, network_id, network_type, physical_network,
                 segmentation_id):
        self.network_id = network_id
        self.network_type = network_type
        self.physical_network = physical_network
        self.segmentation_id = segmentation_id

    def __repr__(self):
        return "<NetworkBinding(%s,%s,%s,%d)>" % (self.network_id,
                                                  self.network_type,
                                                  self.physical_network,
                                                  self.segmentation_id)


class RuijieSwitchEthBinding(BASEV2):
    """Represents a binding of Ruijie switch ip, Ruijie switch port id, Ruijie lldp neighbor MAC"""
    __tablename__ = 'ruijie_switch_eth_bindings'
    __table_args__ = {'extend_existing':True}

    ip_address = Column(String(255), primary_key=True)
    mac_address = Column(String(255), primary_key=True)
    port_id = Column(String(255), primary_key=True)

    def __init__(self, ip, mac, port):
        self.ip_address = ip
        self.mac_address = mac
        self.port_id = port

    def __repr__(self):
        return "<RuijieSwitchEthBinding(%s,%s,%s)>" % (self.ip_address, self.mac_address
                                                    , self.port_id)

class RuijieVmEthBinding(BASEV2):
    """Represents a binding of vm and network card"""
    __tablename__ = 'ruijie_vm_eth_bindings'
    __table_args__ = {'extend_existing':True}

    intf_uuid = Column(String(255), primary_key=True)
    mac_address = Column(String(255), primary_key=True)

    def __init__(self, id, mac):
        self.intf_uuid = id
        self.mac_address = mac

    def __repr__(self):
        return "<RuijieVmEthBinding(%s,%s)>" % (self.intf_uuid, self.mac_address)

class RuijieVlanBinding(BASEV2):
    """Represents a ruijie vlan binding"""
    __tablename__ = 'ruijie_vlan_bindings'
    __table_args__ = {'extend_existing':True}

    ip_address = Column(String(255), primary_key=True)
    port_id = Column(String(255), primary_key=True)
    vlan_id = Column(String(255), primary_key=True)
    intf_uuid = Column(String(255), primary_key=True)

    def __init__(self, ip, port, vlan, uuid):
        self.ip_address = ip
        self.port_id = port
        self.vlan_id = vlan
        self.intf_uuid = uuid

    def __repr__(self):
        return "<RuijieVlanBinding(%s,%s,%s,%s)>" % (self.ip_address, self.port_id
                                                  , self.vlan_id, self.intf_uuid)
        
class RuijieSwitchSshHostConfig(BASEV2):
    """Represents a config of Ruijie switch ssh server info and user info """
    __tablename__ = 'ruijie_switch_ssh_host_config'
    __table_args__ = {'extend_existing':True}

    host_id = Column(Integer, primary_key=True)
    ip_address = Column(String(255), primary_key=True)
    port_id = Column(String(255), primary_key=True)
    retry_times = Column(Integer)
    reconnect_time = Column(Integer)

    def __init__(self, id, ip, port, retry, recont):
        self.host_id = id
        self.ip_address = ip
        self.port_id = port
        self.retry_times = retry
        self.reconnect_time = recont

    def __repr__(self):
        return "<RuijieSwitchSshHostConfig(%s,%s,%s,%s,%s)>" % (self.host_id, self.ip_address
                                                    , self.port_id, self.retry_times
                                                    , self.reconnect_time)

class RuijieSwitchSshAuthConfig(BASEV2):
    """Represents a config of Ruijie switch ssh server info and user info """
    __tablename__ = 'ruijie_switch_ssh_author_config'
    __table_args__ = {'extend_existing':True}

    host_id = Column(Integer, primary_key=True)
    username = Column(String(255), primary_key=True)
    password = Column(String(255), primary_key=True)

    def __init__(self, id, user, passwd):
        self.host_id = id
        self.username = user
        self.password = passwd

    def __repr__(self):
        return "<RuijieSwitchSshAuthConfig(%s,%s,%s)>" % (self.host_id, self.username
                                                    , self.password)
