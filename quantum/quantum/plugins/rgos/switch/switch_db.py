# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Ruijie network, Inc.
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
# @author: Paul liu, Ruijie Networks, Inc.

import logging
import quantum.plugins.rgos.switch 
from quantum.plugins.rgos.db import rgos_db

LOG = logging.getLogger(__name__)

def mac_converter(mac):
    '''
    Conversion MAC, for example:
    mac: '1234.5678.9abc'
    return 12:34:56:78:9a:bc
    '''
    tmp = []
    tmp.append(mac[0:2])
    tmp.append(mac[2:4])
    tmp.append(mac[5:7])
    tmp.append(mac[7:9])
    tmp.append(mac[10:12])
    tmp.append(mac[12:14])
    sign = ':'
    return sign.join(tmp)

def get_all_port_neighbors():
    """Lists all the switch:port and neighbors data """
    pass



def get_port_neighbors(svi, ifx):
    """Lists a switch:port and neighbors data """
    pass



def add_port_neighbors(neighbor_list):
    """Adds a switch:port and neighbors data"""

    mac = ''
    switch_bings = []
    
    # set the port and mac  
    for i in neighbor_list:
        neighbor_tuple = i
        ip = neighbor_tuple[0]
        mac = neighbor_tuple[1]
        port = neighbor_tuple[2]
        # set switch port neighbors info to local db
        switch_bings = rgos_db.get_ruijie_switch_eth_binding(mac)
        if switch_bings == []:
            rgos_db.add_ruijie_switch_eth_binding(ip, mac, port)
        else:
            LOG.debug("add_port_neighbors failed the mac already existed \r\n")


def remove_port_neighbors(neighbor_list):
    """Removes a switch:port and neighbors data"""
    mac = ''
    switch_bings = []
    
    # set the port and mac  
    for i in neighbor_list:
        neighbor_tuple = i
        ip = neighbor_tuple[0]
        mac = neighbor_tuple[1]
        port = neighbor_tuple[2]
        # set switch port neighbors info to local db
        switch_bings = rgos_db.get_ruijie_switch_eth_binding(mac)
        if switch_bings == []:
            LOG.debug("remove_port_neighbors failed the record not existed \r\n")
        else:
            rgos_db.remove_ruijie_switch_eth_binding(ip, mac, port)
    
    pass


def update_port_neighbors(svi, neighbor_list):
    """Updates switch:port and neighbors data"""
    pass


def add_hostinfo(index, sshhost, sshport, retry, reconnect):
    """Add a switch:port cfg"""
    idx = index
    ip = sshhost
    port = sshport
    rgos_db.set_ruijie_switch_host_cfg( idx, ip, port, retry, reconnect)
    pass

def update_hostinfo(index, sshhost, sshport, retry, reconnect):
    """Updates switch:port cfg"""
    idx = index
    ip = sshhost
    port = sshport
    rgos_db.set_ruijie_switch_host_cfg( idx, ip, port, retry, reconnect )
    pass

def remove_hostinfo(index):
    """Removes a switch info """
    idx = index
    rgos_db.remove_ruijie_switch_host_cfg( idx )
    pass

def get_hostinfo( ):
    """Gets a all host cfg info"""
    switch_server_hostcfg = rgos_db.get_ruijie_switch_allhost_cfg( )
    if switch_server_hostcfg == []:
        LOG.debug("get_hostinfo is null ! \r\n")
    else:
        LOG.debug("get_hostinfo = %s \r\n", switch_server_hostcfg)
    return switch_server_hostcfg

def get_hostinfo_byhost(sshhost):
    """Gets a user info"""
    host = sshhost
    switch_server_hostcfg = rgos_db.get_ruijie_switch_host_cfg( host )
    if switch_server_hostcfg == []:
        LOG.debug("get_hostinfo_byhost is null ! \r\n")
    else:
        LOG.debug("get_hostinfo_byhost = %s \r\n", switch_server_hostcfg)
    return switch_server_hostcfg

def get_sshserver_id(sshhost):

    switch_server_hostcfg = get_hostinfo_byhost(sshhost)
    host_id = switch_server_hostcfg[0].host_id
    LOG.debug("get_sshserver_id id = %s \r\n", host_id)

    return host_id

def add_userinfo(index, username, password):
    """Add a user auth cfg"""

    idx = index
    user = username
    passwd = password
    rgos_db.set_ruijie_switch_user_cfg( idx, user, passwd )
    pass

def update_userinfo(index, username, password):
    """Updates sser auth cfg"""
    idx = index
    user = username
    passwd = password
    rgos_db.set_ruijie_switch_user_cfg( idx, user, passwd)
    pass

def remove_userinfo(index):
    """Removes a user info"""
    idx = index
    rgos_db.remove_ruijie_switch_user_cfg( idx )
    pass

def get_userinfo(index):
    """Gets a user info"""
    idx = index
    switch_server_usercfg = rgos_db.get_ruijie_switch_user_cfg( idx )
    if switch_server_usercfg == []:
        LOG.debug("get_userinfo is null with id = %s \r\n", idx)
    else:
        LOG.debug("get_userinfo = %s \r\n", switch_server_usercfg)

    return switch_server_usercfg

