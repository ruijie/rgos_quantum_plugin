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
# @author: Aaron Rosen, Nicira Networks, Inc.
# @author: Bob Kukura, Red Hat, Inc.

import logging

from sqlalchemy.orm import exc

from quantum.common import exceptions as q_exc
from quantum.db import models_v2
import quantum.db.api as db
from quantum.openstack.common import cfg
from quantum.plugins.rgos.common import constants
from quantum.plugins.rgos.db import rgos_models

LOG = logging.getLogger(__name__)


def initialize():
    options = {"sql_connection": "%s" % cfg.CONF.DATABASE.sql_connection}
    options.update({"sql_max_retries": cfg.CONF.DATABASE.sql_max_retries})
    options.update({"reconnect_interval":
                   cfg.CONF.DATABASE.reconnect_interval})
    options.update({"base": models_v2.model_base.BASEV2})
    db.configure_db(options)


def get_network_binding(session, network_id):
    session = session or db.get_session()
    try:
        binding = (session.query(rgos_models.RuijieNetworkBinding).
                   filter_by(network_id=network_id).
                   one())
        return binding
    except exc.NoResultFound:
        return
            
def get_network_bindings(session=None): 
    session = session or db.get_session()
    try:
        binding = dict((bind.network_id, bind) 
                       for bind in session.query(rgos_models.RuijieNetworkBinding).all())
        return binding
    except exc.NoResultFound:
        return None

def add_network_binding(session, network_id, network_type,
                        physical_network, segmentation_id):
    with session.begin(subtransactions=True):
        binding = rgos_models.RuijieNetworkBinding(network_id, network_type,
                                               physical_network,
                                               segmentation_id)
        session.add(binding)


def sync_vlan_allocations(network_vlan_ranges):
    """Synchronize vlan_allocations table with configured VLAN ranges"""

    session = db.get_session()
    with session.begin():
        # process vlan ranges for each physical network separately
        for physical_network, vlan_ranges in network_vlan_ranges.iteritems():

            # determine current configured allocatable vlans for this
            # physical network
            vlan_ids = set()
            for vlan_range in vlan_ranges:
                vlan_ids |= set(xrange(vlan_range[0], vlan_range[1] + 1))

            # remove from table unallocated vlans not currently allocatable
            try:
                allocs = (session.query(rgos_models.RuijieVlanAllocation).
                          filter_by(physical_network=physical_network).
                          all())
                for alloc in allocs:
                    try:
                        # see if vlan is allocatable
                        vlan_ids.remove(alloc.vlan_id)
                    except KeyError:
                        # it's not allocatable, so check if its allocated
                        if not alloc.allocated:
                            # it's not, so remove it from table
                            LOG.debug("removing vlan %s on physical network "
                                      "%s from pool" %
                                      (alloc.vlan_id, physical_network))
                            session.delete(alloc)
            except exc.NoResultFound:
                pass

            # add missing allocatable vlans to table
            for vlan_id in sorted(vlan_ids):
                alloc = rgos_models.RuijieVlanAllocation(physical_network, vlan_id)
                session.add(alloc)


def get_vlan_allocation(physical_network, vlan_id):
    session = db.get_session()
    try:
        alloc = (session.query(rgos_models.RuijieVlanAllocation).
                 filter_by(physical_network=physical_network,
                           vlan_id=vlan_id).
                 one())
        return alloc
    except exc.NoResultFound:
        return


def reserve_vlan(session):
    with session.begin(subtransactions=True):
        alloc = (session.query(rgos_models.RuijieVlanAllocation).
                 filter_by(allocated=False).
                 first())
        if alloc:
            LOG.debug("reserving vlan %s on physical network %s from pool" %
                      (alloc.vlan_id, alloc.physical_network))
            alloc.allocated = True
            return (alloc.physical_network, alloc.vlan_id)
    raise q_exc.NoNetworkAvailable()


def reserve_specific_vlan(session, physical_network, vlan_id):
    with session.begin(subtransactions=True):
        try:
            alloc = (session.query(rgos_models.RuijieVlanAllocation).
                     filter_by(physical_network=physical_network,
                               vlan_id=vlan_id).
                     one())
            if alloc.allocated:
                if vlan_id == constants.FLAT_VLAN_ID:
                    raise q_exc.FlatNetworkInUse(physical_network=
                                                 physical_network)
                else:
                    raise q_exc.VlanIdInUse(vlan_id=vlan_id,
                                            physical_network=physical_network)
            LOG.debug("reserving specific vlan %s on physical network %s "
                      "from pool" % (vlan_id, physical_network))
            alloc.allocated = True
        except exc.NoResultFound:
            LOG.debug("reserving specific vlan %s on physical network %s "
                      "outside pool" % (vlan_id, physical_network))
            alloc = rgos_models.RuijieVlanAllocation(physical_network, vlan_id)
            alloc.allocated = True
            session.add(alloc)


def release_vlan(session, physical_network, vlan_id, network_vlan_ranges):
    with session.begin(subtransactions=True):
        try:
            alloc = (session.query(rgos_models.RuijieVlanAllocation).
                     filter_by(physical_network=physical_network,
                               vlan_id=vlan_id).
                     one())
            alloc.allocated = False
            inside = False
            for vlan_range in network_vlan_ranges.get(physical_network, []):
                if vlan_id >= vlan_range[0] and vlan_id <= vlan_range[1]:
                    inside = True
                    break
            if not inside:
                session.delete(alloc)
            LOG.debug("releasing vlan %s on physical network %s %s pool" %
                      (vlan_id, physical_network,
                       inside and "to" or "outside"))
        except exc.NoResultFound:
            LOG.warning("vlan_id %s on physical network %s not found" %
                        (vlan_id, physical_network))


