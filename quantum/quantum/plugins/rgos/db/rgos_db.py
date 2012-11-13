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
import logging
from sqlalchemy.orm import exc
import quantum.db.api as db
from quantum.openstack.common import cfg
from quantum.db import models_v2
from quantum.plugins.rgos.db import rgos_models

logging.basicConfig()
LOG = logging.getLogger(__name__)

def initialize():
    options = {"sql_connection": "%s" % cfg.CONF.DATABASE.sql_connection}
    options.update({"sql_max_retries": cfg.CONF.DATABASE.sql_max_retries})
    options.update({"reconnect_interval":
                   cfg.CONF.DATABASE.reconnect_interval})
    options.update({"base": models_v2.model_base.BASEV2})
    db.configure_db(options)


def get_ruijie_switch_eth_bindings():
    session = db.get_session()
    try:
        bindings = (session.query(rgos_models.RuijieSwitchEthBinding).
                    all())
    except exc.NoResultFound:
        return []
    res = []
    for x in bindings:
        res.append((x.ip_address, x.mac_address, x.port_id))
    return res

def get_ruijie_switch_eth_binding(mac):
    session = db.get_session()
    return (session.query(rgos_models.RuijieSwitchEthBinding).
            filter_by(mac_address=mac).
            all())

def get_ruijie_switch_eth_binding_byhost(ip):
    session = db.get_session()
    try:
        bindings = (session.query(rgos_models.RuijieSwitchEthBinding).
            filter_by(ip_address=ip).all())
    except exc.NoResultFound:
        return []
    res = []
    for x in bindings:
        res.append((x.ip_address, x.mac_address, x.port_id))
    return res
    

def remove_ruijie_switch_eth_binding(ip, mac, port):
    session = db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieSwitchEthBinding).
                   filter_by(ip_address=ip, mac_address=mac, port_id=port).
                   one())
        session.delete(binding)
    except exc.NoResultFound:
            pass
    session.flush()

def add_ruijie_switch_eth_binding(ip, mac, port):
    session = db.get_session()
    binding = (session.query(rgos_models.RuijieSwitchEthBinding).
                   filter_by(ip_address=ip, mac_address=mac).
                   all())
    if binding != []:
        return
    binding = rgos_models.RuijieSwitchEthBinding(ip, mac, port)
    session.add(binding)
    session.flush()
    return

def get_ruijie_vm_eth_bindings():
    session = db.get_session()
    try:
        bindings = (session.query(rgos_models.RuijieVmEthBinding).
                    all())
    except exc.NoResultFound:
        return []
    res = []
    for x in bindings:
        res.append((x.intf_uuid, x.mac_address))
    return res

def get_ruijie_vm_eth_binding(id):
    session = db.get_session()
    return (session.query(rgos_models.RuijieVmEthBinding).
            filter_by(intf_uuid=id).
            all())

def remove_ruijie_vm_eth_binding(id, mac):
    session = db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieVmEthBinding).
                   filter_by(intf_uuid=id, mac_address=mac).
                   one())
        session.delete(binding)
    except exc.NoResultFound:
            pass
    session.flush()
    
def add_ruijie_vm_eth_binding(id, mac):
    session = db.get_session()
    binding = (session.query(rgos_models.RuijieVmEthBinding).
                   filter_by(intf_uuid=id, mac_address=mac).
                   all())
    if binding != []:
        return
    binding = rgos_models.RuijieVmEthBinding(id, mac)
    session.add(binding)
    session.flush()
    return

def get_ruijie_vlan_bindings():
    session = db.get_session()
    try:
        bindings = (session.query(rgos_models.RuijieVlanBinding).
                    all())
    except exc.NoResultFound:
        return []
    res = []
    for x in bindings:
        res.append((x.ip_address, x.port_id, x.vlan_id, x.intf_uuid))
    return res

def get_ruijie_vlan_binding(ip, port, vlan):
    session = db.get_session()
    return (session.query(rgos_models.RuijieVlanBinding).
            filter_by(ip_address=ip, port_id=port, vlan_id=vlan).
            all())

def remove_ruijie_vlan_binding(ip, port, vlan, uuid):
    session = db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieVlanBinding).
                   filter_by(ip_address=ip, port_id=port, vlan_id=vlan
                             ,intf_uuid=uuid).one())
        session.delete(binding)
    except exc.NoResultFound:
            pass
    session.flush()

def add_ruijie_vlan_binding(ip, port, vlan, uuid):
    session = db.get_session()
    binding = (session.query(rgos_models.RuijieVlanBinding).
                   filter_by(ip_address=ip, port_id=port, vlan_id=vlan
                             ,intf_uuid=uuid).all())
    if binding != []:
        return
    binding = rgos_models.RuijieVlanBinding(ip, port, vlan, uuid)
    session.add(binding)
    session.flush()
    return 


def get_ruijie_attached_ip(vif_id, net_id):
    LOG.info("get_ruijie_attached_ip, vif id is %s, net id is %s" 
             % (vif_id, net_id))
    ip = ''
    vm_eth_binding = get_ruijie_vm_eth_binding(vif_id)
    if vm_eth_binding == []:
        return ip;
    mac_address = vm_eth_binding[0].mac_address
    LOG.info("get_ruijie_attached_ip mac_address = %s " % mac_address)
    switch_binding = get_ruijie_switch_eth_binding(mac_address)
    if switch_binding == []:
        return ip;
    ip = switch_binding[0].ip_address

    return ip


def get_port(port_id):
    session = db.get_session()
    try:
        port = session.query(models_v2.Port).filter_by(id=port_id).one()
    except exc.NoResultFound:
        port = None
    return port


def set_port_status(port_id, status):
    session = db.get_session()
    try:
        port = session.query(models_v2.Port).filter_by(id=port_id).one()
        port['status'] = status
        session.merge(port)
        session.flush()
    except exc.NoResultFound:
        raise q_exc.PortNotFound(port_id=port_id)


def set_ruijie_switch_host_cfg(index, ip, port, retry, reconnect):
    session = db.get_session()
    binding = (session.query(rgos_models.RuijieSwitchSshHostConfig).
                   filter_by(host_id=index).
                   all())
    if binding != []:
        return
    binding = rgos_models.RuijieSwitchSshHostConfig(index, ip, port, retry, reconnect)
    session.add(binding)
    session.flush()
    return

def remove_ruijie_switch_host_cfg(index):
    session = db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieSwitchSshHostConfig).
                   filter_by(host_id=index).
                   one())
        session.delete(binding)
    except exc.NoResultFound:
            pass
    session.flush()
    
def get_ruijie_switch_allhost_cfg():
    session = db.get_session()
    return (session.query(rgos_models.RuijieSwitchSshHostConfig).all())
    
def get_ruijie_switch_host_cfg( host ):
    session = db.get_session()
    return (session.query(rgos_models.RuijieSwitchSshHostConfig).
            filter_by(ip_address=host).
            all())

def set_ruijie_switch_user_cfg(index, user, passwd):
    session = db.get_session()
    binding = (session.query(rgos_models.RuijieSwitchSshAuthConfig).
                   filter_by(host_id=index).
                   all())
    if binding != []:
        return
    binding = rgos_models.RuijieSwitchSshAuthConfig(index, user, passwd)
    session.add(binding)
    session.flush()
    return

def remove_ruijie_switch_user_cfg(index):
    session = db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieSwitchSshAuthConfig).
                   filter_by(host_id=index).
                   one())
        session.delete(binding)
    except exc.NoResultFound:
            pass
    session.flush()

def get_ruijie_switch_user_cfg( index ):
    session = db.get_session()
    return (session.query(rgos_models.RuijieSwitchSshAuthConfig).
            filter_by(host_id=index).
            all())
