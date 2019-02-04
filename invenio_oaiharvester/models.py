# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2011, 2012, 2013, 2014, 2015, 2016 CERN.
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

"""OAI harvest database models."""

from __future__ import absolute_import, print_function
from flask import current_app
import datetime
import enum
from invenio_db import db
from weko_index_tree.models import Index

class OAIHarvestConfig(db.Model):
    """Represents a OAIHarvestConfig record."""

    __tablename__ = 'oaiharvester_configs'

    id = db.Column(db.Integer, primary_key=True)
    baseurl = db.Column(db.String(255), nullable=False, server_default='')
    metadataprefix = db.Column(db.String(255), nullable=False,
                               server_default='oai_dc')
    comment = db.Column(db.Text, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    lastrun = db.Column(db.DateTime, default=datetime.datetime(
        year=1900, month=1, day=1
    ), nullable=True)
    setspecs = db.Column(db.Text, nullable=False)

    def save(self):
        """Save object to persistent storage."""
        with db.session.begin_nested():
            db.session.merge(self)

    def update_lastrun(self, new_date=None):
        """Update the 'lastrun' attribute of object to now."""
        self.lastrun = new_date or datetime.datetime.now()





class HarvestSettings(db.Model):
    """Harvest Settings"""
    class UpdateStyle(enum.IntEnum):
        Difference = 0
        Bulk = 1

    __tablename__ = "harvest_settings"

    id = db.Column(db.Integer, primary_key=True)
    repository_name = db.Column(db.String(20), unique=True, nullable=False)
    base_url = db.Column(db.String(255), nullable=False)
    from_date = db.Column(db.Date, nullable=True)
    until_date = db.Column(db.Date, nullable=True)
    set_spec = db.Column(db.String(255), nullable=True)
    metadata_prefix = db.Column(db.String(255), nullable=False)

    index_id = db.Column(
        db.BigInteger,
        db.ForeignKey(Index.id),
        nullable=False
    )
    target_index = db.relationship(Index, backref='target_index', foreign_keys=[index_id])

    update_style = db.Column(
        db.String(1), nullable=False,
        default=lambda: current_app.config['OAIHARVESTER_DEFAULT_UPDATE_STYLE'])

    auto_distribution = db.Column(
        db.String(1), nullable=False,
        default=lambda: current_app.config['OAIHARVESTER_DEFAULT_AUTO_DISTRIBUTION'])

__all__ = ('OAIHarvestConfig',
           'HarvestSettings')
