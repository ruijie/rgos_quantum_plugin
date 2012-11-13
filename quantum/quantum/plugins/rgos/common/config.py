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

from quantum.openstack.common import cfg


DEFAULT_BRIDGE_MAPPINGS = []
DEFAULT_VLAN_RANGES = []
DEFAULT_SWITCH_SERVER = []

database_opts = [
    cfg.StrOpt('sql_connection', default='sqlite://'),
    cfg.IntOpt('sql_max_retries', default=-1),
    cfg.IntOpt('reconnect_interval', default=2),
]

rgos_opts = [
    cfg.StrOpt('integration_bridge', default='br-int'),
    cfg.StrOpt('local_ip', default='127.0.0.1'),
    cfg.ListOpt('bridge_mappings',
                default=DEFAULT_BRIDGE_MAPPINGS,
                help="List of <physical_network>:<bridge>"),
    cfg.StrOpt('tenant_network_type', default='local',
               help="Network type for tenant networks "
               "(local, vlan, or none)"),
    cfg.ListOpt('network_vlan_ranges',
                default=DEFAULT_VLAN_RANGES,
                help="List of <physical_network>:<vlan_min>:<vlan_max> "
                "or <physical_network>"),
]

switch_opts = [
    cfg.StrOpt('remote_switch_server', default=DEFAULT_SWITCH_SERVER,
                help="List of <index>:<username>:<password>:<server>:<port>; "),
    cfg.IntOpt('ssh_max_retries', default=-1),
    cfg.IntOpt('reconnect_interval', default=2),
]

agent_opts = [
    cfg.IntOpt('polling_interval', default=2),
    cfg.IntOpt('lldp_timeout', default=2),
    cfg.StrOpt('root_helper', default='sudo'),
    cfg.BoolOpt('rpc', default=True),
]

cfg.CONF.register_opts(database_opts, "DATABASE")
cfg.CONF.register_opts(rgos_opts, "RGOS")
cfg.CONF.register_opts(agent_opts, "AGENT")
cfg.CONF.register_opts(switch_opts, "SWITCHAGENT")
