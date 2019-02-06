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

import os
from flask import abort, current_app, flash, request, app
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.fields import QuerySelectField
from flask_admin.form import rules
from flask_babelex import gettext as _
from flask_wtf import FlaskForm
from markupsafe import Markup
from invenio_admin.forms import LazyChoices
from wtforms.fields import RadioField, SubmitField
from weko_index_tree.models import Index
from .models import HarvestSettings

def _(x):
    return x

def link(text, link_func):
    """Generate a object formatter for links.."""
    def object_formatter(v, c, m, p):
        """Format object view link."""
        return Markup('<a href="{0}">{1}</a>'.format(
            link_func(m), text))
    return object_formatter

class HarvestSettingView(ModelView):
    can_create = True
    can_delete = True
    can_edit = True
    can_view_details = True
    page_size = 25

    # from .views import blueprint
    # # details_template = current_app.config['OAIHARVESTER_DETAIL_TEMPLATE']
    #
    # details_template = os.path.join(blueprint.root_path,
    #                                 blueprint.template_folder,
    #                                 'admin/harvest_details.html')

    column_formatters = dict(
        # Harvesting='<a id="harvesting-btn" class="btn btn-primary" href="#">Run</a>',
        Harvesting=link('Objects', '#'),

    )
    column_details_list = (
        'repository_name',
        'base_url',
        'from_date',
        'until_date',
        'set_spec',
        'metadata_prefix',
        'target_index.index_name',
        'update_style',
        'auto_distribution',
        # 'Harvesting',
    )

    # details_template = current_app.config['OAIHARVESTER_DETAIL_TEMPLATE']
    # form_overrides = dict(
    #     target_index=QuerySelectField,
    #     update_style=RadioField)
    # form_args = dict(
    #     target_index=dict(
    #         query_factory=lambda : Index.query.all(),
    #         get_pk=lambda index : index.id,
    #         get_label=lambda index : index.index_name),
    #     update_style=dict(
    #         choices=[(0, 'Difference'), (1, 'Bulk')]))
    form_base_class = FlaskForm
    form_columns = (
        'repository_name', 'base_url', 'from_date',
        'until_date', 'set_spec', 'metadata_prefix', 'target_index',
        'update_style', 'auto_distribution'
    )
    column_list = (
        'repository_name',
        'base_url',
        'from_date',
        'until_date',
        'set_spec',
        'metadata_prefix',
        'target_index.index_name',
        'update_style',
        'auto_distribution',
    )
    form_create_rules = (
        'repository_name',
        'base_url',
        'from_date',
        'until_date',
        'set_spec',
        'metadata_prefix',
        'target_index',
        'update_style',
        'auto_distribution',
        rules.HTML('<div class="form-group"><div class="col-md-2"></div>'
                   '<div class="col-md-10"><a id="harvesting-btn" '
                   'class="btn btn-primary" href="#">Harvesting</a></div></div>'),
    )
    form_choices = dict(
        update_style=LazyChoices(lambda: current_app.config[
            'OAIHARVESTER_UPDATE_STYLE_OPTIONS'].items()),
        auto_distribution=LazyChoices(lambda: current_app.config[
            'OAIHARVESTER_AUTO_DISTRIBUTION_OPTIONS'].items()))


harvest_admin_view = dict(
    modelview=HarvestSettingView,
    model=HarvestSettings,
    category=_('OAI-PMH'),
    name = _('Harvesting'))

