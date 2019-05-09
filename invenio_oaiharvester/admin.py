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

import os
import sys

from flask import current_app, flash, redirect, request, url_for
from flask_admin import expose
from flask_admin.contrib.sqla import ModelView
from flask_babelex import gettext as _
from invenio_admin.forms import LazyChoices
from markupsafe import Markup

from .models import HarvestSettings
from .tasks import run_harvesting


def _(x):
    return x


def link(text, link_func):
    """Generate a object formatter for links.."""
    def object_formatter(v, c, m, p):
        """Format object view link."""
        return Markup('<a id="hvt-btn" class="btn btn-primary" '
                      'href="{0}?id={2}">{1}</a>'.format(link_func(m), text,
                                                         m.id))
    return object_formatter


class HarvestSettingView(ModelView):
    """Harvest setting page view."""

    @expose('/harvesting/')
    def harvesting(self):
        """Run harvesting."""
        run_harvesting.delay(request.args.get('id'))
        flash('running harvesting...')
        return redirect(url_for('harvestsettings.index_view'))

    can_create = True
    can_delete = True
    can_edit = True
    can_view_details = True
    page_size = 25

    column_formatters = dict(
        Harvesting=link('Run', lambda o: url_for(
            'harvestsettings.harvesting')),
    )
    column_details_list = (
        'repository_name', 'base_url', 'from_date', 'until_date',
        'set_spec', 'metadata_prefix', 'target_index.index_name',
        'update_style', 'auto_distribution', 'Harvesting',
    )

    form_columns = (
        'repository_name', 'base_url', 'from_date', 'until_date',
        'set_spec', 'metadata_prefix', 'target_index',
        'update_style', 'auto_distribution'
    )
    column_list = (
        'repository_name', 'base_url', 'from_date', 'until_date',
        'set_spec', 'metadata_prefix', 'target_index.index_name',
        'update_style', 'auto_distribution',
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
    name=_('Harvesting'))
