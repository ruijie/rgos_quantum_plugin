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
import socket
import string
from quantum.plugins.rgos.ssh import sshclient
from quantum.plugins.rgos.db import rgos_db

LOG = logging.getLogger(__name__)

def get_switchinfo_climode(chan, switch_mode_info):

    while True:
        try:
            switch_mode_info = chan.recv(1024)
            LOG.debug("get_switchinfo_climode recive switch_mode_info = %s ", switch_mode_info)
            if len(switch_mode_info) == 0:
                LOG.debug("\r\n get_switchinfo_climode *** EOF\r\n")
            break
        except socket.timeout:
            break

    return switch_mode_info

def send_switch_cli(chan, cli):

    try:
        # send cli for get switch info
        space = ' '
        if len(cli) == 0:
            LOG.debug("send_switch_cli para erro:[cli] !")
        LOG.debug("send_switch_cli len(cli) = %d \r\n", len(cli))
        switch_cli = cli
        y = chan.send(switch_cli)
        # Recive the send message about cli
        if switch_cli != space:
            get_send2switch_cli(chan, switch_cli)

    except socket.timeout:
        pass


def get_send2switch_cli(chan, switch_cli):

    if len(switch_cli) == 0:
        LOG.debug("get_send2switch_cli para erro !")
        return

    cli_str = ''
    while True:
        try:
            x = chan.recv(512)
            if len(cli_str) < len(switch_cli):
                cli_str = cli_str + x
                continue
            break
        except socket.timeout:
            break


def get_switchinfo_cliexecut(chan,switch_mode_info):

    switch_cli_return = ''
    recv_buf = 120
    recv_times = 1
    while True:
        try:
            # recive the switch cli return info
            y = ''
            more = '--More--'
            enter = '\r\n'
            y = chan.recv(recv_buf)
            if len(y) != len(switch_mode_info):
                # cli return not completed countine recive!
                if y.find(more,0,) == -1:
                    switch_cli_return = switch_cli_return + y
                    continue
                else:
                    # when recv the 'more' message ,auto send space and enter command ,contuine recive show
                    LOG.debug("recv switch cli return info is too much, send space continue recive ...")
                    switch_cli_more = ' '
                    send_switch_cli(chan, switch_cli_more)
                    continue
            else:
                # cli return message is recviced complete!
                LOG.debug("recv switch_cli len(y) = switch_mode_info %d quit recv !\r\n", len(switch_mode_info))
                break

            LOG.debug("recv switch cli return info is completed ! ")
        except socket.timeout:
            break

    return switch_cli_return


def get_val_by_str(headstr, tailstr, message):

    val = ''
    
    head = message.find(headstr)
    if head == -1:
        LOG.debug("get_val_by_str not find head !")
        return val
    head = head + len(headstr)

    tail = message.find(tailstr)
    if tail == -1:
        LOG.debug("get_val_by_str not find tail !")
        return val
    val = message[head:tail]
    return val


def get_switchport_mode(recv_info, ifx):
    str_ifx = ''
    list_ifx = []
    portmode = ''
    port_info = ''
    info_head = -1
    info_tail= -1
    
    # parse the recv_info 
    str_ifx = ifx
    if str_ifx.find('GigabitEthernet') == -1:
        list_ifx = str_ifx.split()
        str_ifx = list_ifx[1]

    info_head = recv_info.find(str_ifx)
    if  info_head != -1:
        info_tail = recv_info.find('\r\n',info_head)
        if info_tail != -1:
            port_info = recv_info[info_head:info_tail]
            val = port_info.find('TRUNK')
            if val != -1:
                portmode = 'TRUNK'
                return portmode
            val = port_info.find('ACCESS')
            if val != -1:
                portmode = 'ACCESS'
                return portmode
            val = port_info.find('UPLINK')
            if val != -1:
                portmode = 'UPLINK'
                return portmode
        else:
            LOG.debug("get_switchport_mode error can not find tail !")

    LOG.debug("get_switchport_mode error can not find ifx !")
    return portmode
