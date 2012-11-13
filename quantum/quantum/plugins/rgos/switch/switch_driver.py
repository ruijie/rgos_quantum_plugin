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

import socket
import string
import logging
from quantum.plugins.rgos.ssh import sshclient
from quantum.plugins.rgos.switch import switch_db
from quantum.plugins.rgos.switch import switch_api
from quantum.plugins.rgos.db import rgos_db
from quantum.plugins.rgos.vlan import vlan_mgr

LOG = logging.getLogger(__name__)

def parse_recived_message(recv_str, cli, host_info):

    if len(recv_str) == 0:
        LOG.error("parse_recived_message para erro: recv_str !")
        return -1

    if len(cli) == 0:
        LOG.error("parse_recived_message para erro: cli!")
        return -1

    # parse the recive message by cli type
    if cli == 'show lldp neighbors detail \r\n':
        # get the neighor mac & local interface info in recv message
        ret = get_lldp_neighbor_details(recv_str, host_info)
        if ret == -1:
            LOG.error("parse_recived_message get_lldp_neighbor erro end!")
            return -1
    
    if cli == 'show lldp neighbors \r\n':
        # get the neighor mac & local interface info in recv message
        LOG.debug("parse_recived_message get_lldp_neighbor start ")
        ret = get_lldp_neighbor(recv_str, host_info)
        if ret == -1:
            LOG.error("parse_recived_message get_lldp_neighbor erro end!")
            return -1
    
    LOG.debug("parse_recived_message end!")
    return 0


def scan_server_lldp(chan, host_info):

    LOG.debug("scan_server_lldp Start !" )

    try:
        ret = 0
        chan.settimeout(1.0)
        # get switch cli mode info via ssh
        switch_mode_info = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_mode_info)
        # send cli command to switch via ssh
        switch_cli = 'show lldp neighbors detail \r\n'
        LOG.debug("can_server_lldp send start switch_cli = %s " ,switch_cli)
        switch_api.send_switch_cli(chan, switch_cli)
        # recive the cli return info via ssh
        switch_cli_return = ''
        switch_cli_return = switch_api.get_switchinfo_cliexecut(chan, switch_mode_info)
        LOG.debug("scan_server_lldp switch_cli_return =\r\n %s \r\n" ,switch_cli_return)
        # analyse the swirch return message 
        ret = parse_recived_message(switch_cli_return, switch_cli, host_info)
        if ret == -1:
            LOG.error("scan_server_lldp parse_recived_message erro!")
        else:
            LOG.debug("scan_server_lldp parse_recived_message success!" )

    finally:
        LOG.debug("scan_server_lldp end !" )

def update_server_lldp():
    ret = -1
    
    h_allconfig = get_sshserver_hostinfo()
    if h_allconfig == []:
        ret = -1
        return ret
    
    for x in h_allconfig:
        ssh_host = x.ip_address
        ssh_port = int(x.port_id)
        retry_maxtimes = int(x.retry_times)
        reconnect_interval = int(x.reconnect_time)
        # get user info from db by host
        username = get_sshserver_username(ssh_host)
        passwd = get_sshserver_password(ssh_host)

        LOG.debug("scan remote ssh_host ip: %s" % ssh_host)
        LOG.debug("scan retry_maxtimes: %s" % retry_maxtimes)
        LOG.debug("scan reconnect_interval: %s" % reconnect_interval)
        LOG.debug("scan ssh_port: %s" % ssh_port)
        LOG.debug("scan remote_switch_user: %s" % username)
        LOG.debug("scan remote_switch_pass: %s" % passwd)
        hostinfo_t = (ssh_host, ssh_port, retry_maxtimes, reconnect_interval)
        t = sshclient.ssh_connect(username, passwd, ssh_host, ssh_port)
        if t == -1:
            LOG.debug("Ssh connect failed t == -1 " )
        else:
            chan = sshclient.ssh_channel(t)
            if chan == -1:
                LOG.debug("Ssh channel create failed chan == -1 " )
            else:
                #pass
                scan_server_lldp(chan, hostinfo_t)
            sshclient.ssh_close(chan, t)
            LOG.debug("Ssh connect end ! " )
        
    ret = 0
    return ret

def get_server_lldpneighbors(chan):

    try:
        ret = 0
        chan.settimeout(1.0)
        # get switch cli mode info via ssh
        switch_mode_info = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_mode_info)
        # send cli command to switch via ssh
        switch_cli = 'show lldp neighbors \r\n'
        switch_api.send_switch_cli(chan, switch_cli)
        # recive the cli return info via ssh
        switch_cli_return = ''
        switch_cli_return = switch_api.get_switchinfo_cliexecut(chan, switch_mode_info)
        # analyse the swirch return message 
        ret = parse_recived_message(switch_cli_return, switch_cli)
        if ret == -1:
            LOG.error("get_server_lldpneighbors parse_recived_message erro!")
        else:
            LOG.debug("get_server_lldpneighbors parse_recived_message success!" )

    finally:
        LOG.debug("get_server_lldpneighbors end !" )

def set_switch_vlan(ssh_host, ifx, vlan):
    
    # paramater check is here
    
    # create cli command
    sshhost = ssh_host
    host_t = ''
    switch_port_mode = 'access'
    switch_ifx = ifx
    switch_vlan = str(vlan)
    vlanall =  '1-4094'
    vlanlist = vlanall
    access = 'ACCESS'
    trunk = 'TRUNK'
    uplink = 'UPLINK'
    portmode = ''
    return_switchport_info = ''
    
    # first step into vlan mode 
    cli_confmode = 'configure\r\n'
    cli_show_ifx_mode = 'show interfaces ' + switch_ifx + ' switchport\r\n'
    cli_vlanmode = 'vlan ' + switch_vlan + '\r\n'
    #print 'set_switch_vlan cli_vlanmode = %s \r\n' % cli_vlanmode,
    cli_ifx_mode = 'interface ' + switch_ifx +  '\r\n'
    # bug for eth1 native 1 will not get dhcp ip
    portmode = trunk
    cli_ifx_set_trunkmode = 'switchport mode '+ portmode +'\r\n'
    portmode = uplink
    cli_ifx_set_uplinkmode = 'switchport mode '+ portmode +'\r\n'
    cli_ifx_remove_vlan = 'switchport tru allow vlan r '+ vlanlist + '\r\n'
    vlanlist = switch_vlan
    cli_ifx_add_vlan = 'switchport tru allow vlan add ' + vlanlist + '\r\n'
    cli_exit = 'exit\r\n'
    cli_conf_exit = 'exit\r\n'
    
    # create ssh connect by host
    host_t = get_sshserver_hostinfo_byhost( ssh_host )
    sshport = int(host_t[1])
    user = get_sshserver_username(sshhost)
    password = get_sshserver_password(sshhost)
    
    t= sshclient.ssh_connect(user, password, sshhost, sshport)
    if t == -1:
        LOG.error("Set_switch_vlan ssh connect failed t == -1")
        return -1
    
    chan = sshclient.ssh_channel(t)
    if chan == -1:
        LOG.error("Set_switch_vlan ssh channel create failed chan == -1")
        return -1
    
    # send the cli to switch
    
    try:
        chan.settimeout(5.0)
        # get switch cli mode info via ssh
        switch_mode_info = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_mode_info)
        
        # send 'conf' cli command to switch via ssh
        switch_api.send_switch_cli(chan, cli_confmode)
        switch_cli_return = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_cli_return)
        LOG.debug("set_switch_vlan cli_confmode return = %s \r\n" ,switch_mode_info)
        # send 'vlan xx ' cli command to switch via ssh Create or Set vlan
        switch_api.send_switch_cli(chan, cli_vlanmode)
        # send cli command exit vlan mode
        switch_api.send_switch_cli(chan, cli_exit)
        
        # Check interface mode
        switch_api.send_switch_cli(chan, cli_show_ifx_mode)
        # Get the interface mode info
        return_switchport_info = switch_api.get_switchinfo_cliexecut(chan,switch_mode_info)
        LOG.debug("set_switch_vlan cli_confmode return_switchport_info = \r\n%s \r\n" ,return_switchport_info)
        # Parse the interface mode info
        switch_port_mode = switch_api.get_switchport_mode(return_switchport_info, switch_ifx)
        LOG.debug("set_switch_vlan cli_confmode switch_port_mode = %s \r\n" ,switch_port_mode)
        #into interface mode
        switch_api.send_switch_cli(chan, cli_ifx_mode)
        #if the ifx is access mode should switch to trunnk then remova all vlan ,finally set vlan 
        if switch_port_mode == access:
            LOG.debug("set_switch_vlan switch_port_mode is access!")
            # change portmode into trunk
            #send_switch_cli(chan, cli_ifx_set_trunkmode)
            #print 'set_switch_vlan cli_ifx_set_trunkmode send! \r\n'
            # change portmode into uplink
            switch_api.send_switch_cli(chan, cli_ifx_set_uplinkmode)

            # remova all vlan list
            switch_api.send_switch_cli(chan, cli_ifx_remove_vlan)
            LOG.debug("set_switch_vlan cli_ifx_remove_vlan send!")

            # add vlan into allow vlan list
            switch_api.send_switch_cli(chan, cli_ifx_add_vlan)
            LOG.debug("set_switch_vlan cli_ifx_add_vlan send!")
        elif switch_port_mode == trunk:
            LOG.debug("set_switch_vlan switch_port_mode is trunk!")
            # add vlan into trunk allow vlan list
            switch_api.send_switch_cli(chan, cli_ifx_add_vlan)
        elif switch_port_mode == uplink:
            LOG.debug("set_switch_vlan switch_port_mode is uplink!")
            # add vlan into trunk allow vlan list
            switch_api.send_switch_cli(chan, cli_ifx_add_vlan)
        else:
            LOG.error("set_switch_vlan err : port mode error")

        # send cli command exit interface mode and config mode
        switch_api.send_switch_cli(chan, cli_exit)
        switch_api.send_switch_cli(chan, cli_conf_exit)

    finally:
        LOG.debug("set_switch_vlan end !")

    # close the ssh conect with switch
    sshclient.ssh_close(chan, t)

    return 0

def unset_switch_vlan(ssh_host, ifx, vlan):
    # send cli to switch by ssh connet

    # paramater check is here

    # create cli command

    sshhost = ssh_host
    switch_ifx = ifx
    switch_vlan = str(vlan)

    # first step into vlan mode 
    cli_confmode = 'configure\r\n'
    cli_vlanmode = 'vlan ' + switch_vlan + '\r\n'

    cli_vlan_noaddifx = 'no add interface ' + switch_ifx + '\r\n'

    cli_exit = 'exit\r\n'
    cli_conf_exit = 'exit\r\n'
	
    # create ssh connect by host
    host_t = get_sshserver_hostinfo_byhost( ssh_host )
    sshport = int(host_t[1])
    user = get_sshserver_username(sshhost)
    password = get_sshserver_password(sshhost)
    
    t= sshclient.ssh_connect(user, password, sshhost, sshport)
    if t == -1:
        LOG.error("unset_switch_vlan ssh connect failed t == -1")
        return -1
    
    chan = sshclient.ssh_channel(t)
    if chan == -1:
        LOG.error("unset_switch_vlan ssh channel create failed chan == -1")
        return -1
    
    # send the cli to switch
    
    try:
        chan.settimeout(5.0)
        # get switch cli mode info via ssh
        switch_mode_info = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_mode_info)
        
        switch_api.send_switch_cli(chan, cli_confmode)
        switch_cli_return = ''
        switch_mode_info = switch_api.get_switchinfo_climode(chan, switch_cli_return)
        LOG.debug("set_switch_vlan cli_confmode return = %s ", switch_mode_info)
        
        # Check interface mode
        cli_show_ifx_mode = 'show interfaces ' + switch_ifx + ' switchport \r\n'
        switch_api.send_switch_cli(chan, cli_show_ifx_mode)
        # Get the interface mode info
        return_switchport_info = switch_api.get_switchinfo_cliexecut(chan,switch_mode_info)
        LOG.debug("set_switch_vlan cli_confmode return_switchport_info = \r\n%s \r\n", return_switchport_info)
        # Parse the interface mode info
        switch_port_mode = switch_api.get_switchport_mode(return_switchport_info, switch_ifx)
        LOG.debug("set_switch_vlan cli_confmode switch_port_mode = %s ", switch_port_mode)
        
        if switch_port_mode == 'ACCESS':
            # send cli command into vlan mode
            switch_api.send_switch_cli(chan, cli_vlanmode)
            # send cli command to switch via ssh
            switch_api.send_switch_cli(chan, cli_vlan_noaddifx)
            # send cli command exit vlan mode and config mode
            switch_api.send_switch_cli(chan, cli_exit)
            switch_api.send_switch_cli(chan, cli_conf_exit)
        elif switch_port_mode == 'TRUNK':
            #into interface mode
            cli_ifx_mode = 'interface ' + switch_ifx +  '\r\n'
            switch_api.send_switch_cli(chan, cli_ifx_mode)

            # remova vlan from vlan list
            cli_ifx_remove_vlan = 'switchport trunk allowed vlan rem '+ switch_vlan + '\r\n'
            switch_api.send_switch_cli(chan, cli_ifx_remove_vlan)
            # send cli command exit vlan mode and config mode
            switch_api.send_switch_cli(chan, cli_exit)
            switch_api.send_switch_cli(chan, cli_conf_exit)
        elif switch_port_mode == 'UPLINK':
            #into interface mode
            cli_ifx_mode = 'interface ' + switch_ifx +  '\r\n'
            switch_api.send_switch_cli(chan, cli_ifx_mode)

            # remova vlan from vlan list
            cli_ifx_remove_vlan = 'switchport trunk allowed vlan rem '+ switch_vlan + '\r\n'

            switch_api.send_switch_cli(chan, cli_ifx_remove_vlan)
            # send cli command exit vlan mode and config mode
            switch_api.send_switch_cli(chan, cli_exit)
            switch_api.send_switch_cli(chan, cli_conf_exit)
        else:
            LOG.error("unset_switch_vlan switch_port_mode is error!")
        LOG.debug("unset_switch_vlan send_switch_cli SUCCESS! ")

    finally:
        LOG.debug("unset_switch_vlan end !")

    # close the ssh conect with switch
    sshclient.ssh_close(chan, t)
    
    return 0


def update_lldp_neighbor(host, new_neighbor_list):

    if new_neighbor_list == []:
        return
    LOG.debug('old lldp neighbor host: %s', host)
    LOG.debug('old lldp neighbor new_neighbor_list: %s', new_neighbor_list)
    old_bindings = rgos_db.get_ruijie_switch_eth_binding_byhost(host)
    
    new_bindings = []
    for x in new_neighbor_list:
        ethmac = switch_db.mac_converter(x[3])
        ifx = x[0]
        new_bindings.append((host, ethmac.decode("utf8"), ifx.decode("utf8")))
    
    LOG.debug('old lldp neighbor bindings: %s', old_bindings)
    LOG.debug('new lldp neighbor bindings: %s', new_bindings)
    old_bindings_set = set(old_bindings)
    new_bindings_set = set(new_bindings)
    add_bindings_set = new_bindings_set - old_bindings_set
    del_bindings_set = old_bindings_set - new_bindings_set
    add_bindings = list(add_bindings_set)
    del_bindings = list(del_bindings_set)
    LOG.debug('add lldp neighbor bindings: %s', add_bindings)
    LOG.debug('del lldp neighbor bindings: %s', del_bindings)
    
    # save lldp neighbors info to db
    # new create lldp info into db
    switch_db.add_port_neighbors(add_bindings)

    # remove old lldp info into db
    switch_db.remove_port_neighbors(del_bindings)


def get_lldp_neighbor_details(recv_str, host_info):

    #print 'get_lldp_neighbor start! \r\n'
    if len(recv_str) == 0:
        LOG.error("get_lldp_neighbor para erro: recv_str !")
        return -1

    # save the data to local array
    neighbor_list = []

    neighbor_list = get_neighbor_list_details( recv_str )

    # host should get from db by config set
    host = host_info[0]
    LOG.debug("get_lldp_neighbor_details host = %s ",host)

    # Update the host's lldp neighbor info
    update_lldp_neighbor(host, neighbor_list)

    #print 'get_lldp_neighbor end! \r\n'
    return 0

def get_lldp_neighbor(recv_str, host_info):

    if len(recv_str) == 0:
        LOG.error("get_lldp_neighbor para erro: recv_str !")
        return -1

    # save the data to local array
    neighbor_list = []

    neighbor_list = get_neighbor_list( recv_str )
    
    # host should get from db by config set
    host = host_info[0]
    # save lldp neighbors info to db
    update_lldp_neighbor(host, neighbor_list)

    return 0

def get_neighbor_list_details( recv_str ):

    # save the data to local array
    neighbor_list = []
    recv_tmp = ''
    tuple_count = 0
    recv_str_tail = 0

    # parse the recive message by cli type
    # init the data
    Local_ifx = 'LLDP neighbor-information of port ['
    Local_ifx_val = ''
    Local_ifx_tail = ']\r\n'
    
    Neighbor_index = 'Neighbor index                    : '
    Neighbor_index_val = ''

    Device_type = '  Device type                       : '
    
    ChassisID_type = '  Chassis ID type                   : '
    ChassisID_type_val = ''
    
    ChassisID = '  Chassis ID                        : '
    ChassisID_val = ''
    
    SystemName = '  System name                       : '
    SystemName_val = ''
    
    System_des = '  System description                : '
    
    PortID_type = '  Port ID type                      : '
    PortID_type_val = ''
    
    PortID = 'Port ID                           : '
    PortID_val = ''
    
    Port_des = '  Port description                  :'
    
    Port_VLANID = 'Port VLAN ID                      : '
    Port_VLANID_val = ''
    
    PPVID = '  Port and protocol VLAN ID(PPVID)  : '
    UnitEnd = '  Maximum frame Size                :'

    while True:

        ret = recv_str.find(UnitEnd)
        if ret == -1:
            break;
        recv_str_tail = ret + len(UnitEnd)
        recv_tmp = recv_str[0:recv_str_tail]
        # get val message by search string in revice message
        Local_ifx_val = switch_api.get_val_by_str(Local_ifx, Local_ifx_tail, recv_tmp)
        if len(Local_ifx_val) == 0:
            LOG.debug("get_lldp_neighbor can not find Local_ifx_val !")

        Neighbor_index_val = switch_api.get_val_by_str(Neighbor_index, Device_type, recv_tmp)
        if len(Neighbor_index_val) == 0:
            LOG.error("get_lldp_neighbor Neighbor_index_val not find = %s ",Neighbor_index_val)
            break
        Neighbor_index_val = Neighbor_index_val[:-2] 
    
        ChassisID_type_val = switch_api.get_val_by_str(ChassisID_type, ChassisID, recv_tmp)
        ChassisID_type_val = ChassisID_type_val[:-2]
    
        ChassisID_val = switch_api.get_val_by_str(ChassisID, SystemName, recv_tmp)
        ChassisID_val = ChassisID_val[:ChassisID_val.find('\r\n')]
    
        SystemName_val = switch_api.get_val_by_str(SystemName, System_des, recv_tmp)
        SystemName_val = SystemName_val[:-2]
    
        PortID_type_val = switch_api.get_val_by_str(PortID_type, PortID, recv_tmp)
        PortID_type_val = PortID_type_val[:PortID_type_val.find('\r\n')]
    
        PortID_val = switch_api.get_val_by_str(PortID, Port_des, recv_tmp)
        PortID_val = PortID_val[:PortID_val.find('\r\n')]
    
        Port_VLANID_val = switch_api.get_val_by_str(Port_VLANID, PPVID, recv_tmp)
        Port_VLANID_val = Port_VLANID_val[:-2]

        recv_str = recv_str[recv_str_tail:-1]
        LOG.debug("get_lldp_neighbor recv_str 3 = %s \r\n ",recv_str)

        if len(Local_ifx_val) > 0:
            ifx = Local_ifx_val
        neighbor_tuple = (ifx, Neighbor_index_val, PortID_type_val, PortID_val)
        neighbor_list.insert( tuple_count, neighbor_tuple )
        tuple_count = tuple_count +1
        LOG.debug("get_lldp_neighbor serach = %d times\r\n ",tuple_count)
        continue

    return neighbor_list

def get_neighbor_list( recv_str ):

    # save the data to local array
    neighbor_list = []
    recv_tmp = ''
    tuple_count = 0
    recv_str_tail = 0

    # parse the recive message by cli type
    # init the data

    SystemName = 'System Name'
    SystemName_val = ''
    System_des = '  System description                : ' 
    Local_ifx = 'Local Intf'
    Local_ifx_val = ''
    Local_ifx_tail = ']\r\n'
    PortID = 'Port ID'
    PortID_val = ''
    Port_des = '  Port description                  :'
    Capability = 'Capability'
    Capability_val = ''
    
    Agingtime = 'Aging-time'
    Agingtime_val = ''
    Neighbor_index_val = ''
    ChassisID_type_val = ''
    ChassisID_val = ''
    
    while True:

        SystemName_val = switch_api.get_val_by_str(SystemName, System_des, recv_tmp)
        SystemName_val = SystemName_val[:-2]
        #print 'get_lldp_neighbor SystemName_val = %s \r\n' % SystemName_val,

        # get val message by search string in revice message
        Local_ifx_val = switch_api.get_val_by_str(Local_ifx, Local_ifx_tail, recv_tmp)
        if len(Local_ifx_val) == 0:
            print'get_lldp_neighbor can not find Local_ifx_val !\r\n'
        #print 'get_lldp_neighbor Local_ifx_val = %s \r\n' % Local_ifx_val,
    
        PortID_val = switch_api.get_val_by_str(PortID, Port_des, recv_tmp)
        PortID_val = PortID_val[:-2]
        #print 'get_lldp_neighbor PortID_val = %s \r\n' % PortID_val,

        recv_str = recv_str[recv_str_tail:-1]
        #print '\r\n#################################################### \r\n'
        #print 'get_lldp_neighbor recv_str 3 = %s \r\n' % recv_str,
        #print '\r\n#################################################### \r\n'
        #print 'get_lldp_neighbor recv_str_head = %d \r\n' % recv_str_tail,

        if len(Local_ifx_val) > 0:
            ifx = Local_ifx_val
        #print 'get_lldp_neighbor ifx = %s \r\n' % ifx,
        neighbor_tuple = (ifx, Neighbor_index_val, ChassisID_type_val, ChassisID_val)
        neighbor_list.insert( tuple_count, neighbor_tuple )
        tuple_count = tuple_count +1

        continue

    return neighbor_list


def set_sshserver_hostinfo(index, sshhost, sshport, retry, reconnect):
    # parameter check

    # save host info into db
    ret = switch_db.get_hostinfo_byhost(sshhost)
    if ret == [] :
        # not find host info ,Create new one
        switch_db.add_hostinfo(index, sshhost, sshport, retry, reconnect)
    else:
        # find old hostinfo ,Update it 
        switch_db.update_hostinfo(index, sshhost, sshport, retry, reconnect)
    return 0

def get_sshserver_hostinfo():

    # There will get all hostinfo from db
    hostinfo = switch_db.get_hostinfo()

    return hostinfo

def get_sshserver_hostinfo_byhost( sshhost ):

    # There Should get hostinfo from db
    hostinfo = switch_db.get_hostinfo_byhost(sshhost)
    if hostinfo != []:
        h_host = hostinfo[0].ip_address
        h_port = hostinfo[0].port_id
        h_retry = hostinfo[0].retry_times
        h_recont = hostinfo[0].reconnect_time
        hostinfo_t = (h_host, h_port, h_retry, h_recont)

    return hostinfo_t

def set_sshserver_userinfo(index, username, passwd):
    # parameter check
    
    #save user config info 
    # should save into db
    userinfo_t = (index, username, passwd)
    ret = switch_db.get_userinfo(index)
    if ret == [] :
        # not find user info ,Create new one
        switch_db.add_userinfo(index, username, passwd)
    else:
        # find old user info ,Update it 
        switch_db.update_userinfo(index, username, passwd)

    return 0


def get_sshserver_username( sshhost ):
    
    # get server id from db by host
    index =  switch_db.get_sshserver_id(sshhost)

    # get username from db by host id
    usercfg = switch_db.get_userinfo(index)
    LOG.debug("get_sshserver_username usercfg = %s ",usercfg)
    username = usercfg[0].username
    LOG.debug("get_sshserver_username username = %s",username)
    return username

def get_sshserver_password( sshhost):
    
    # get server id from db by host
    index =  switch_db.get_sshserver_id(sshhost)
    # get username from db by host id
    usercfg = switch_db.get_userinfo(index)
    passwd = usercfg[0].password
    LOG.debug("get_sshserver_password passwd = %s ",passwd)
    return passwd


def set_ruijie_vlan(vif_id, net_id):
    LOG.debug("set_ruijie_vlan, vif id is %s, net id is %s",vif_id, net_id)
    vm_eth_binding = rgos_db.get_ruijie_vm_eth_binding(vif_id)
    if vm_eth_binding == []:
        return
    mac_address = vm_eth_binding[0].mac_address
    LOG.debug("interface id %s has been connected to mac %s",vif_id, mac_address)
    switch_binding = rgos_db.get_ruijie_switch_eth_binding(mac_address)
    if switch_binding == []:
        return;
    ip = switch_binding[0].ip_address
    ifx = switch_binding[0].port_id
    ovs_binding = vlan_mgr.get_network_binding(None, net_id)
    if ovs_binding == None:
        return
    vlan = ovs_binding.segmentation_id
    LOG.debug("the switch ip is %s, ifx is %s, vlan is %s",ip, ifx, vlan)
    ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, vlan)
    if ruijie_vlan_binding == []:
        LOG.debug("to set the vlan of ruijie switch now")
        set_switch_vlan(ip, ifx, vlan)
    rgos_db.add_ruijie_vlan_binding(ip, ifx, vlan, vif_id)
    return
    
def unset_ruijie_vlan(vif_id, net_id):

    LOG.debug("unset_ruijie_vlan, net id is %s, vif id is %s",net_id, vif_id)
    vm_eth_binding = rgos_db.get_ruijie_vm_eth_binding(vif_id)
    if vm_eth_binding == []:
        return
    mac_address = vm_eth_binding[0].mac_address
    LOG.debug("vif id %s has been connected to mac %s",vif_id, mac_address)
    switch_binding = rgos_db.get_ruijie_switch_eth_binding(mac_address)
    if switch_binding == []:
        return;
    ip = switch_binding[0].ip_address
    ifx = switch_binding[0].port_id
    ovs_binding = vlan_mgr.get_network_binding(None, net_id)
    if ovs_binding == None:
        return
    vlan = ovs_binding.segmentation_id
    LOG.debug("the switch ip is %s, ifx is %s, vlan is %s",ip, ifx, vlan)
    uuid = 0
    rgos_db.remove_ruijie_vlan_binding(ip, ifx, vlan, uuid)
    ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, vlan)
    if ruijie_vlan_binding == []:
        LOG.debug("to unset the vlan of ruijie switch now")
        unset_switch_vlan(ip, ifx, vlan)
    return 

def update_ruijie_vlan(vif_id, net_id, old_seg_id):
    
    LOG.debug("update_ruijie_vlan, net id is %s, vif id is %s, old vid %s",net_id, vif_id, old_seg_id)
    vm_eth_binding = rgos_db.get_ruijie_vm_eth_binding(vif_id)
    if vm_eth_binding == []:
        return
    mac_address = vm_eth_binding[0].mac_address
    LOG.debug("interface id %s has been connected to mac %s",vif_id, mac_address)
    switch_binding = rgos_db.get_ruijie_switch_eth_binding(mac_address)
    if switch_binding == []:
        return;
    ip = switch_binding[0].ip_address
    ifx = switch_binding[0].port_id
    ovs_binding = vlan_mgr.get_network_binding(None, net_id)
    if ovs_binding == None:
        return
    vlan = ovs_binding.segmentation_id
    
    # del old ruijie switch vlan
    rgos_db.remove_ruijie_vlan_binding(ip, ifx, old_seg_id, vif_id)
    ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, old_seg_id)
    if ruijie_vlan_binding == []:
        LOG.debug("to unset the vlan of ruijie switch now")
        unset_switch_vlan(ip, ifx, old_seg_id)
    
    ruijie_vlan_binding = rgos_db.get_ruijie_vlan_binding(ip, ifx, vlan)
    if ruijie_vlan_binding == []:
        LOG.debug("to set the vlan of ruijie switch now")
        set_switch_vlan(ip, ifx, vlan)
    rgos_db.add_ruijie_vlan_binding(ip, ifx, vlan, vif_id)
    
    return 

