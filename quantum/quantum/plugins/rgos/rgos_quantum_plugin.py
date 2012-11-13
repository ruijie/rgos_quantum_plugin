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

# @author: Paul liu, Ruijie Networks, Inc.

import logging
import os
import sys

from quantum.api.v2 import attributes
from quantum.common import constants as q_const
from quantum.common import exceptions as q_exc
from quantum.common import topics
from quantum.db import db_base_plugin_v2
from quantum.db import dhcp_rpc_base
from quantum.db import l3_db
from quantum.extensions import providernet as provider
from quantum.openstack.common import context
from quantum.openstack.common import cfg
from quantum.openstack.common import rpc
from quantum.openstack.common.rpc import dispatcher
from quantum.openstack.common.rpc import proxy
from quantum import policy
from quantum.plugins.rgos.common import config
from quantum.plugins.rgos.common import constants
from quantum.plugins.rgos.db import rgos_db
from quantum.plugins.rgos.vlan import vlan_mgr as rgos_vlanmgr
from quantum.plugins.rgos.ssh import sshclient
from quantum.plugins.rgos.switch import switch_driver

LOG = logging.getLogger(__name__)


class RgosRpcCallbacks(dhcp_rpc_base.DhcpRpcCallbackMixin):

    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'

    def __init__(self, rpc_context, notifier):
        self.rpc_context = rpc_context
        self.notifier = notifier

    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return dispatcher.RpcDispatcher([self])

    def get_device_details(self, rpc_context, **kwargs):
        """Agent requests device details"""
        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug("Device %s details requested from %s", device, agent_id)
        port = rgos_db.get_port(device)
        if port:
            binding = rgos_vlanmgr.get_network_binding(None, port['network_id'])
            entry = {'device': device,
                     'network_id': port['network_id'],
                     'port_id': port['id'],
                     'admin_state_up': port['admin_state_up'],
                     'network_type': binding.network_type,
                     'segmentation_id': binding.segmentation_id,
                     'physical_network': binding.physical_network}
            # Set the port status to UP
            rgos_db.set_port_status(port['id'], q_const.PORT_STATUS_ACTIVE)
        else:
            entry = {'device': device}
            LOG.debug("%s can not be found in database", device)
        return entry

    def update_device_down(self, rpc_context, **kwargs):
        """Device no longer exists on agent"""
        # (TODO) garyk - live migration and port status
        agent_id = kwargs.get('agent_id')
        device = kwargs.get('device')
        LOG.debug("Device %s no longer exists on %s", device, agent_id)
        port = rgos_db.get_port(device)
        if port:
            entry = {'device': device,
                     'exists': True}
            # Set port status to DOWN
            rgos_db.set_port_status(port['id'], q_const.PORT_STATUS_DOWN)
        else:
            entry = {'device': device,
                     'exists': False}
            LOG.debug("%s can not be found in database", device)
        return entry


class AgentNotifierApi(proxy.RpcProxy):


    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic):
        super(AgentNotifierApi, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)
        self.topic_network_delete = topics.get_topic_name(topic,
                                                          topics.NETWORK,
                                                          topics.DELETE)
        self.topic_port_update = topics.get_topic_name(topic,
                                                       topics.PORT,
                                                       topics.UPDATE)


    def network_delete(self, context, network_id):
        self.fanout_cast(context,
                         self.make_msg('network_delete',
                                       network_id=network_id),
                         topic=self.topic_network_delete)

    def port_update(self, context, port, network_type, segmentation_id,
                    physical_network):
        self.fanout_cast(context,
                         self.make_msg('port_update',
                                       port=port,
                                       network_type=network_type,
                                       segmentation_id=segmentation_id,
                                       physical_network=physical_network),
                         topic=self.topic_port_update)



class RgosQuantumPlugin(db_base_plugin_v2.QuantumDbPluginV2,
                         l3_db.L3_NAT_db_mixin):

    # This attribute specifies whether the plugin supports or not
    # bulk operations. Name mangling is used in order to ensure it
    # is qualified by class
    __native_bulk_support = True
    supported_extension_aliases = ["provider", "router"]

    def __init__(self, configfile=None):
        rgos_db.initialize()
        self._parse_network_vlan_ranges()
        rgos_vlanmgr.sync_vlan_allocations(self.network_vlan_ranges)
        self.tenant_network_type = cfg.CONF.RGOS.tenant_network_type
        if self.tenant_network_type not in [constants.TYPE_LOCAL,
                                            constants.TYPE_VLAN,
                                            constants.TYPE_NONE]:
            LOG.error("Invalid tenant_network_type: %s",
                      self.tenant_network_type)
            sys.exit(1)
        self.agent_rpc = cfg.CONF.AGENT.rpc
        self.setup_rpc()
        self._parse_remote_switch_conf()
        self._init_rgos_remote()

    def _init_rgos_remote(self):
        #init the RGOS remote conf
        #rgos switch
        h_allconfig = switch_driver.get_sshserver_hostinfo()
        for x in h_allconfig:
            ssh_host = x.ip_address
            ssh_port = int(x.port_id)
            retry_maxtimes = int(x.retry_times)
            reconnect_interval = int(x.reconnect_time)
            # get user info from db by host
            username = switch_driver.get_sshserver_username(ssh_host)
            passwd = switch_driver.get_sshserver_password(ssh_host)

            LOG.debug("Init remote ssh_host ip: %s" % ssh_host)
            LOG.debug("Init retry_maxtimes: %s" % retry_maxtimes)
            LOG.debug("Init reconnect_interval: %s" % reconnect_interval)
            LOG.debug("Init ssh_port: %s" % ssh_port)
            LOG.debug("Init remote_switch_user: %s" % username)
            LOG.debug("Init remote_switch_pass: %s" % passwd)
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
                    switch_driver.scan_server_lldp(chan, hostinfo_t)
                sshclient.ssh_close(chan, t)
            LOG.debug("Ssh connect end ! " )

    def setup_rpc(self):
        # RPC support
        self.topic = topics.PLUGIN
        self.rpc_context = context.RequestContext('quantum', 'quantum',
                                                  is_admin=False)
        self.conn = rpc.create_connection(new=True)
        self.notifier = AgentNotifierApi(topics.AGENT)
        self.callbacks = RgosRpcCallbacks(self.rpc_context, self.notifier)
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        # Consume from all consumers in a thread
        self.conn.consume_in_thread()

    def _parse_network_vlan_ranges(self):
        self.network_vlan_ranges = {}
        for entry in cfg.CONF.RGOS.network_vlan_ranges:
            entry = entry.strip()
            if ':' in entry:
                try:
                    physical_network, vlan_min, vlan_max = entry.split(':')
                    self._add_network_vlan_range(physical_network.strip(),
                                                 int(vlan_min),
                                                 int(vlan_max))
                except ValueError as ex:
                    LOG.error("Invalid network VLAN range: \'%s\' - %s",
                              entry, ex)
                    sys.exit(1)
            else:
                self._add_network(entry)
        LOG.info("Network VLAN ranges: %s", self.network_vlan_ranges)


    def _add_network_vlan_range(self, physical_network, vlan_min, vlan_max):
        self._add_network(physical_network)
        self.network_vlan_ranges[physical_network].append((vlan_min, vlan_max))

    def _add_network(self, physical_network):
        if physical_network not in self.network_vlan_ranges:
            self.network_vlan_ranges[physical_network] = []

    def _check_provider_view_auth(self, context, network):
        return policy.check(context,
                            "extension:provider_network:view",
                            network)

    def _enforce_provider_set_auth(self, context, network):
        return policy.enforce(context,
                              "extension:provider_network:set",
                              network)

    def _extend_network_dict_provider(self, context, network):
        if self._check_provider_view_auth(context, network):
            binding = rgos_vlanmgr.get_network_binding(context.session,
                                                    network['id'])
            network[provider.NETWORK_TYPE] = binding.network_type

            if binding.network_type == constants.TYPE_VLAN:
                network[provider.PHYSICAL_NETWORK] = binding.physical_network
                network[provider.SEGMENTATION_ID] = binding.segmentation_id


    def _process_provider_create(self, context, attrs):
        network_type = attrs.get(provider.NETWORK_TYPE)
        physical_network = attrs.get(provider.PHYSICAL_NETWORK)
        segmentation_id = attrs.get(provider.SEGMENTATION_ID)

        network_type_set = attributes.is_attr_set(network_type)
        physical_network_set = attributes.is_attr_set(physical_network)
        segmentation_id_set = attributes.is_attr_set(segmentation_id)

        if not (network_type_set or physical_network_set or
                segmentation_id_set):
            return (None, None, None)

        # Authorize before exposing plugin details to client
        self._enforce_provider_set_auth(context, attrs)

        if not network_type_set:
            msg = _("provider:network_type required")
            raise q_exc.InvalidInput(error_message=msg)
        elif network_type == constants.TYPE_VLAN:
            if not segmentation_id_set:
                msg = _("provider:segmentation_id required")
                raise q_exc.InvalidInput(error_message=msg)
            if segmentation_id < 1 or segmentation_id > 4094:
                msg = _("provider:segmentation_id out of range "
                        "(1 through 4094)")
                raise q_exc.InvalidInput(error_message=msg)
        else:
            msg = _("provider:network_type %s not supported" % network_type)
            raise q_exc.InvalidInput(error_message=msg)

        if network_type == constants.TYPE_VLAN:
            if physical_network_set:
                if physical_network not in self.network_vlan_ranges:
                    msg = _("unknown provider:physical_network %s" %
                            physical_network)
                    raise q_exc.InvalidInput(error_message=msg)
            elif 'default' in self.network_vlan_ranges:
                physical_network = 'default'
            else:
                msg = _("provider:physical_network required")
                raise q_exc.InvalidInput(error_message=msg)

        return (network_type, physical_network, segmentation_id)

    def _check_provider_update(self, context, attrs):
        network_type = attrs.get(provider.NETWORK_TYPE)
        physical_network = attrs.get(provider.PHYSICAL_NETWORK)
        segmentation_id = attrs.get(provider.SEGMENTATION_ID)

        network_type_set = attributes.is_attr_set(network_type)
        physical_network_set = attributes.is_attr_set(physical_network)
        segmentation_id_set = attributes.is_attr_set(segmentation_id)

        if not (network_type_set or physical_network_set or
                segmentation_id_set):
            return

        # Authorize before exposing plugin details to client
        self._enforce_provider_set_auth(context, attrs)

        msg = _("plugin does not support updating provider attributes")
        raise q_exc.InvalidInput(error_message=msg)


    def _parse_remote_switch_conf(self):
        self.switch_server_cfg = {}
        
        switch_tmp =  cfg.CONF.SWITCHAGENT.remote_switch_server
        if ';' in switch_tmp:
            switch_server_cfg = switch_tmp.split(';')
        
        for entry in switch_server_cfg:
            entry = entry.strip()
            if ':' in entry:
                try:
                    index, username, password, server, sshport = entry.split(':')
                    LOG.info("_parse_remote_switch_conf index: %s , username = %s ,pass =%s ", index,username,password)
                    LOG.info("_parse_remote_switch_conf server = %s ,sshport =%s ", server,sshport)
                    self._add_remote_switch_conf(index, username, password, server, sshport)
                except ValueError as ex:
                    LOG.error("Invalid network VLAN range: \'%s\' - %s",
                                entry, ex)
                    sys.exit(1)

    def _add_remote_switch_conf(self, index, username, password, server, sshport):

        ssh_host = server
        ssh_port = sshport
        username = username
        passwd = password
        retry_maxtimes = cfg.CONF.SWITCHAGENT.ssh_max_retries
        reconnect_interval = cfg.CONF.SWITCHAGENT.reconnect_interval
        LOG.debug("_add_remote_switch_conf: remote ssh_host ip: %s" % ssh_host)
        LOG.debug("_add_remote_switch_conf: retry_maxtimes: %s" % retry_maxtimes)
        LOG.debug("_add_remote_switch_conf: reconnect_interval: %s" % reconnect_interval)
        LOG.debug("_add_remote_switch_conf: ssh_port: %s" % ssh_port)
        LOG.debug("_add_remote_switch_conf: remote_switch_user: %s" % username)
        LOG.debug("_add_remote_switch_conf: remote_switch_pass: %s" % passwd)
        switch_driver.set_sshserver_hostinfo(index, ssh_host, ssh_port, retry_maxtimes, reconnect_interval)
        switch_driver.set_sshserver_userinfo(index, username, passwd)

    def create_network(self, context, network):
        (network_type, physical_network,
         segmentation_id) = self._process_provider_create(context,
                                                          network['network'])

        session = context.session
        with session.begin(subtransactions=True):
            if not network_type:
                # tenant network
                network_type = self.tenant_network_type
                if network_type == constants.TYPE_NONE:
                    raise q_exc.TenantNetworksDisabled()
                elif network_type == constants.TYPE_VLAN:
                    (physical_network,
                     segmentation_id) = rgos_vlanmgr.reserve_vlan(session)

                # no reservation needed for TYPE_LOCAL
            else:
                # provider network
                if network_type == constants.TYPE_VLAN:
                    rgos_vlanmgr.reserve_specific_vlan(session, physical_network,
                                                    segmentation_id)

                # no reservation needed for TYPE_LOCAL
            net = super(RgosQuantumPlugin, self).create_network(context,
                                                                 network)
            rgos_vlanmgr.add_network_binding(session, net['id'], network_type,
                                          physical_network, segmentation_id)

            self._process_l3_create(context, network['network'], net['id'])
            self._extend_network_dict_provider(context, net)
            self._extend_network_dict_l3(context, net)
            # note - exception will rollback entire transaction
        LOG.debug("Created network: %s", net['id'])
        return net

    def update_network(self, context, id, network):
        self._check_provider_update(context, network['network'])
        segmentation_id =  network['network']['segmentation_id']
        LOG.debug("update_network: segmentation id = %s", segmentation_id)
        session = context.session
        with session.begin(subtransactions=True):
            binding = rgos_vlanmgr.get_network_binding(session, id)
            if binding.network_type == constants.TYPE_VLAN:
                rgos_vlanmgr.release_vlan(session, binding.physical_network,
                                       binding.segmentation_id,
                                       self.network_vlan_ranges)
                rgos_vlanmgr.reserve_specific_vlan(session, binding.physical_network,
                                       segmentation_id)
                session.delete(binding)
                session.flush()
                rgos_vlanmgr.add_network_binding(session, id, binding.network_type,
                                          binding.physical_network, segmentation_id)

        session = context.session
        with session.begin(subtransactions=True):
            net = super(RgosQuantumPlugin, self).update_network(context, id,
                                                                 network)
            self._process_l3_update(context, network['network'], id)
            self._extend_network_dict_provider(context, net)
            self._extend_network_dict_l3(context, net)
        return net

    def delete_network(self, context, id):
        session = context.session
        with session.begin(subtransactions=True):
            binding = rgos_vlanmgr.get_network_binding(session, id)
            super(RgosQuantumPlugin, self).delete_network(context, id)
            if binding.network_type == constants.TYPE_VLAN:
                rgos_vlanmgr.release_vlan(session, binding.physical_network,
                                       binding.segmentation_id,
                                       self.network_vlan_ranges)
            # the network_binding record is deleted via cascade from
            # the network record, so explicit removal is not necessary
        if self.agent_rpc:
            self.notifier.network_delete(self.rpc_context, id)

    def get_network(self, context, id, fields=None):
        net = super(RgosQuantumPlugin, self).get_network(context, id, None)
        self._extend_network_dict_provider(context, net)
        self._extend_network_dict_l3(context, net)
        return self._fields(net, fields)

    def get_networks(self, context, filters=None, fields=None):
        nets = super(RgosQuantumPlugin, self).get_networks(context, filters,
                                                            None)
        for net in nets:
            self._extend_network_dict_provider(context, net)
            self._extend_network_dict_l3(context, net)

        nets = self._filter_nets_l3(context, nets, filters)

        return [self._fields(net, fields) for net in nets]

    def update_port(self, context, id, port):
        if self.agent_rpc:
            original_port = super(RgosQuantumPlugin, self).get_port(context,
                                                                     id)
        port = super(RgosQuantumPlugin, self).update_port(context, id, port)
        if self.agent_rpc:
            if original_port['admin_state_up'] != port['admin_state_up']:
                binding = rgos_vlanmgr.get_network_binding(None,
                                                        port['network_id'])
                self.notifier.port_update(self.rpc_context, port,
                                          binding.network_type,
                                          binding.segmentation_id,
                                          binding.physical_network)
        return port

    def delete_port(self, context, id, l3_port_check=True):

        # if needed, check to see if this is a port owned by
        # and l3-router.  If so, we should prevent deletion.
        if l3_port_check:
            self.prevent_l3_port_deletion(context, id)
        self.disassociate_floatingips(context, id)
        return super(RgosQuantumPlugin, self).delete_port(context, id)
