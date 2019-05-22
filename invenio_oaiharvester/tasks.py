# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Celery tasks used by Invenio-OAIHarvester."""

from __future__ import absolute_import, print_function

import signal
from celery import current_task, shared_task
from lxml import etree
from weko_deposit.api import WekoDeposit
from invenio_db import db
from .harvester import DCMapper, list_sets, map_sets
from .harvester import list_records as harvester_list_records
from .models import HarvestSettings
from .api import get_records, list_records
from .signals import oaiharvest_finished
from .utils import get_identifier_names
from weko_index_tree.models import Index


@shared_task
def get_specific_records(identifiers, metadata_prefix=None, url=None,
                         name=None, signals=True, encoding=None,
                         **kwargs):
    """Harvest specific records from an OAI repo via OAI-PMH identifiers.

    :param metadata_prefix: The prefix for the metadata return (e.g. 'oai_dc')
    :param identifiers: list of unique identifiers for records to be harvested.
    :param url: The The url to be used to create the endpoint.
    :param name: The name of the OAIHarvestConfig to use instead of passing
                 specific parameters.
    :param signals: If signals should be emitted about results.
    :param encoding: Override the encoding returned by the server. ISO-8859-1
                     if it is not provided by the server.
    """
    identifiers = get_identifier_names(identifiers)
    request, records = get_records(identifiers, metadata_prefix, url, name,
                                   encoding)
    if signals:
        oaiharvest_finished.send(request, records=records, name=name, **kwargs)


@shared_task
def list_records_from_dates(metadata_prefix=None, from_date=None,
                            until_date=None, url=None,
                            name=None, setspecs=None, signals=True,
                            encoding=None, **kwargs):
    """Harvest multiple records from an OAI repo.

    :param metadata_prefix: The prefix for the metadata return (e.g. 'oai_dc')
    :param from_date: The lower bound date for the harvesting (optional).
    :param until_date: The upper bound date for the harvesting (optional).
    :param url: The The url to be used to create the endpoint.
    :param name: The name of the OAIHarvestConfig to use instead of passing
                 specific parameters.
    :param setspecs: The 'set' criteria for the harvesting (optional).
    :param signals: If signals should be emitted about results.
    :param encoding: Override the encoding returned by the server. ISO-8859-1
                     if it is not provided by the server.
    """
    request, records = list_records(
        metadata_prefix,
        from_date,
        until_date,
        url,
        name,
        setspecs,
        encoding
    )
    if signals:
        oaiharvest_finished.send(request, records=records, name=name, **kwargs)


def create_indexes(parent_id, sets):
    existed_leaves = Index.query.filter_by(parent=parent_id).all()
    if existed_leaves:
        pos = max([idx.position for idx in existed_leaves]) + 1
    else:
        pos = 0
    specs = [leaf.index_link_name_english for leaf in existed_leaves]
    parent_idx = Index.query.filter_by(id=parent_id).first()
    for s in sets:
        if s not in specs:
            idx = Index()
            idx.parent = parent_id
            idx.browsing_role = parent_idx.browsing_role
            idx.contribute_role = parent_idx.contribute_role
            idx.index_name = sets[s]
            idx.index_name_english = sets[s]
            idx.index_link_name_english = s
            idx.public_state = True
            idx.recursive_public_state = True
            idx.position = pos
            pos = pos + 1
            db.session.add(idx)
            db.session.commit()


def map_indexes(index_specs, parent_id):
    res = []
    for spec in index_specs:
        idx = Index.query.filter_by(
            index_link_name_english=spec, parent=parent_id).first()
        res.append(idx.id)
    return res


def create_item(record, harvesting):
    xml = etree.tostring(record, encoding='utf-8').decode()
    mapper = DCMapper(xml)
    json = mapper.map()
    json['$schema'] = '/items/jsonschema/' + str(mapper.itemtype.id)
    dep = WekoDeposit.create({})
    if int(harvesting.auto_distribution):
        indexes = map_indexes(mapper.specs(), harvesting.index_id)
    else:
        indexes = [harvesting.index_id]
    dep.update({'actions': 'publish', 'index': indexes}, json)
    db.session.commit()
    dep.commit()


@shared_task
def run_harvesting(id):
    harvesting = HarvestSettings.query.filter_by(id=id).first()
    harvesting.task_id = current_task.request.id
    db.session.commit()
    try:
        if int(harvesting.auto_distribution):
            sets = list_sets(harvesting.base_url)
            sets_map = map_sets(sets)
            create_indexes(harvesting.index_id, sets_map)
        DCMapper.update_itemtype_map()
        rtoken = harvesting.resumption_token
        pause = False
        def sigterm_handler(*args):
            nonlocal pause
            pause=True
        signal.signal(signal.SIGTERM, sigterm_handler)
        while True:
            records, rtoken = harvester_list_records(
                harvesting.base_url,
                harvesting.from_date.__str__() if harvesting.from_date else None,
                harvesting.until_date.__str__() if harvesting.until_date else None,
                harvesting.metadata_prefix,
                harvesting.set_spec,
                rtoken)
            for record in records:
                try:
                    create_item(record, harvesting)
                except:
                    db.session.rollback()
            harvesting.resumption_token = rtoken
            db.session.commit()
            if (not rtoken) or (pause == True):
                break
    finally:
        harvesting.task_id = None
        db.session.commit()

