# -*- coding: utf-8 -*-
#
# This file is part of WEKO3.
# Copyright (C) 2017 National Institute of Informatics.
#
# WEKO3 is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# WEKO3 is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WEKO3; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.

"""WEKO3 module docstring."""

import sys

from flask import abort, current_app, flash, request
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.fields import QuerySelectField
from flask_babelex import gettext as _
from wtforms.fields import RadioField
from weko_index_tree.models import Index
from .models import HarvestSettings

def _(x):
    return x

class HarvestSettingView(ModelView):
    can_create = True
    can_delete = True
    can_edit = True
    can_view_details = True
    page_size = 25
    form_overrides = dict(
        target_index=QuerySelectField,
        update_style=RadioField)
    form_args = dict(
        target_index=dict(
            query_factory=lambda : Index.query.all(),
            get_pk=lambda index : index.id,
            get_label=lambda index : index.index_name),
        update_style=dict(
            choices=[(0, 'Difference'), (1, 'Bulk')]))



harvest_admin_view = dict(
    modelview=HarvestSettingView,
    model=HarvestSettings,
    category=_('OAI-PMH'),
    name = _('Harvesting'))
