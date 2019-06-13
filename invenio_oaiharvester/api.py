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

"""Invenio-OAIHarvester API to harvest items from OAI-PMH servers.

If you need to schedule or run harvests from inside of Python, you can use our
API:

.. code-block:: python

    from invenio_oaiharvester.api import get_records

    request, records = get_records(identifiers=["oai:arXiv.org:1207.7214"],
                                   url="http://export.arxiv.org/oai2")
    for record in records:
        print rec.raw
"""

from __future__ import absolute_import, print_function

import datetime

from flask import current_app, render_template
from invenio_db import db
from invenio_mail.api import send_mail
from sickle import Sickle
from sickle.oaiexceptions import NoRecordsMatch
from weko_accounts.api import get_user_info_by_role_name

from .errors import NameOrUrlMissing, WrongDateCombination
from .utils import get_oaiharvest_object, RunStat
from .models import HarvestSettings


def _(x):
    return x


def list_records(metadata_prefix=None, from_date=None, until_date=None,
                 url=None, name=None, setspecs=None, encoding=None):
    """Harvest multiple records from an OAI repo.

    :param metadata_prefix: The prefix for the metadata return
                            (defaults to 'oai_dc').
    :param from_date: The lower bound date for the harvesting (optional).
    :param until_date: The upper bound date for the harvesting (optional).
    :param url: The The url to be used to create the endpoint.
    :param name: The name of the OAIHarvestConfig to use instead of passing
                 specific parameters.
    :param setspecs: The 'set' criteria for the harvesting (optional).
    :param encoding: Override the encoding returned by the server. ISO-8859-1
                     if it is not provided by the server.
    :return: request object, list of harvested records
    """
    lastrun = None
    if name:
        url, _metadata_prefix, lastrun, _setspecs = get_info_by_oai_name(name)

        # In case we provide a prefix, we don't want it to be
        # overwritten by the one we get from the name variable.
        if metadata_prefix is None:
            metadata_prefix = _metadata_prefix
        if setspecs is None:
            setspecs = _setspecs
    elif not url:
        raise NameOrUrlMissing(
            "Retry using the parameters -n <name> or -u <url>."
        )

    request = Sickle(url, encoding=encoding)

    # By convention, when we have a url we have no lastrun, and when we use
    # the name we can either have from_date (if provided) or lastrun.
    dates = {
        'from': from_date or lastrun,
        'until': until_date
    }

    # Sanity check
    if (dates['until'] is not None) and (dates['from'] > dates['until']):
        raise WrongDateCombination("'Until' date larger than 'from' date.")

    lastrun_date = datetime.datetime.now()

    # Use a dict to only return the same record once
    # (e.g. if it is part of several sets)
    records = {}
    setspecs = setspecs.split() or [None]
    for spec in setspecs:
        params = {
            'metadataPrefix': metadata_prefix or "oai_dc"
        }
        params.update(dates)
        if spec:
            params['set'] = spec
        try:
            for record in request.ListRecords(**params):
                records[record.header.identifier] = record
        except NoRecordsMatch:
            continue

    # Update lastrun?
    if from_date is None and until_date is None and name is not None:
        oai_source = get_oaiharvest_object(name)
        oai_source.update_lastrun(lastrun_date)
        oai_source.save()
        db.session.commit()
    return request, records.values()


def get_records(identifiers, metadata_prefix=None, url=None, name=None,
                encoding=None):
    """Harvest specific records from an OAI repo via OAI-PMH identifiers.

    :param metadata_prefix: The prefix for the metadata return
                            (defaults to 'oai_dc').
    :param identifiers: list of unique identifiers for records to be harvested.
    :param url: The The url to be used to create the endpoint.
    :param name: The name of the OAIHarvestConfig to use instead of passing
                 specific parameters.
    :param encoding: Override the encoding returned by the server. ISO-8859-1
                     if it is not provided by the server.
    :return: request object, list of harvested records
    """
    if name:
        url, _metadata_prefix, _, __ = get_info_by_oai_name(name)

        # In case we provide a prefix, we don't want it to be
        # overwritten by the one we get from the name variable.
        if metadata_prefix is None:
            metadata_prefix = _metadata_prefix
    elif not url:
        raise NameOrUrlMissing(
            "Retry using the parameters -n <name> or -u <url>."
        )

    request = Sickle(url, encoding=encoding)
    records = []
    for identifier in identifiers:
        arguments = {
            'identifier': identifier,
            'metadataPrefix': metadata_prefix or "oai_dc"
        }
        records.append(request.GetRecord(**arguments))
    return request, records


def get_info_by_oai_name(name):
    """Get basic OAI request data from the OAIHarvestConfig model.

    :param name: name of the source (OAIHarvestConfig.name)

    :return: (url, metadataprefix, lastrun as YYYY-MM-DD, setspecs)
    """
    obj = get_oaiharvest_object(name)
    lastrun = obj.lastrun.strftime("%Y-%m-%d")
    return obj.baseurl, obj.metadataprefix, lastrun, obj.setspecs


def send_run_status_mail(end_time, harvesting, stat):
    """Send harvest runnig status mail."""
    try:
        result = ''
        if stat.status == RunStat.Status.SUCCESS:
            result = _('Successful')
        elif stat.status == RunStat.Status.PAUSE:
            result = _('Suspended')
        elif stat.status == RunStat.Status.CANCEL:
            result = _('Cancel')
        elif stat.status == RunStat.Status.ERROR:
            result = _('Failed')
        # mail title
        subject = _('harvester running status') + \
                   ' [{0}({1})] [{2}]'.format(harvesting.repository_name,
                                              harvesting.id,
                                              result)
        # recipient mail list
        users = []
        users += get_user_info_by_role_name('Repository Administrator')
        users += get_user_info_by_role_name('Community Administrator')
        mail_list = []
        for user in users:
            mail_list.append(user.email)

        update_style = \
            HarvestSettings.UpdateStyle(int(harvesting.update_style)).name
        # send mail
        send_mail(subject, mail_list,
                  html=\
                  render_template('invenio_oaiharvester/run_stat_mail.html',
                                  result_text=result,
                                  harvesting=harvesting,
                                  stat=stat,
                                  end_time=end_time,
                                  update_style=update_style))
    except Exception as ex:
        current_app.logger.error(ex)
