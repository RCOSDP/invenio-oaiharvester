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

from datetime import datetime

import celery
from flask import abort, current_app, flash, jsonify, redirect, request, session, \
    url_for
from flask_admin import expose
from flask_admin.contrib.sqla import ModelView
from flask_babelex import gettext as _
from flask_login import current_user
from invenio_admin.forms import LazyChoices
from invenio_db import db
from markupsafe import Markup

from . import config
from .models import HarvestSettings
from .tasks import link_error_handler, link_success_handler, run_harvesting


def _(x):
    return x


def run_time():
    def object_formatter(v, c, m, p):
        harvesting = HarvestSettings.query.filter_by(id=m.id).first()
        if harvesting.task_id != None or harvesting.resumption_token != None:
            return Markup(_('Start Time: ') + '<div id="start_time"></div>' +
                          _('End Time: ') + '<div id="end_time"></div>')
    return object_formatter


def run_stats():
    def object_formatter(v, c, m, p):
        harvesting = HarvestSettings.query.filter_by(id=m.id).first()
        if harvesting.task_id == None and harvesting.resumption_token == None:
            return Markup(_('Harvesting is not running'))
        elif harvesting.task_id == None:
            return Markup(_('Harvesting is paused with resumption token: ') +
                          harvesting.resumption_token)
        else:
            return Markup(_('Task ID: ') + '<div id="task_id">' +
                          harvesting.task_id + '</div>' + '</br>' +
                          _('Records Processed: ') + '<div id="task_total">' +
                          str(harvesting.item_processed) + '</div>' +
                          _('Task Status: ') + '<div id="task_status"></div>')
    return object_formatter


def control_btns():
    """Generate a object formatter for buttons."""
    def object_formatter(v, c, m, p):
        """Format object view."""
        run_url = url_for('harvestsettings.run')
        run_text =_('Run')
        run_btn = '<a id="hvt-btn" class="btn btn-primary" href="{0}?id={1}">{2}</a>'.format(
            run_url, m.id, run_text)
        resume_text =_('Resume')
        resume_btn = '<a id="resume-btn" class="btn btn-primary" href="{0}?id={1}">{2}</a>'.format(
            run_url, m.id, resume_text)
        pause_url = url_for('harvestsettings.pause')
        pause_text =_('Pause')
        pause_btn = '<a id="pause-btn" class="btn btn-warning" href="{0}?id={1}">{2}</a>'.format(
            pause_url, m.id, pause_text)
        clear_url = url_for('harvestsettings.clear')
        clear_text =_('Clear')
        clear_btn = '<a id="clear-btn" class="btn btn-danger" href="{0}?id={1}">{2}</a>'.format(
            clear_url, m.id, clear_text)
        harvesting = HarvestSettings.query.filter_by(id=m.id).first()
        if harvesting.task_id == None and harvesting.resumption_token == None:
            return Markup(run_btn)
        elif harvesting.task_id == None:
            return Markup(resume_btn + clear_btn)
        else:
            return Markup(pause_btn)
    return object_formatter


class HarvestSettingView(ModelView):
    """Harvest setting page view."""

    @expose('/run/')
    def run(self):
        """Run harvesting."""
        run_harvesting.apply_async(args=(
            request.args.get('id'), datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z'),
            {'ip_address': request.remote_addr,
             'user_agent': request.user_agent.string,
             'user_id': (
                current_user.get_id() if current_user.is_authenticated else None),
             'session_id': session.get('sid_s')}),
             link=link_success_handler.s(),
             link_error=link_error_handler.s())
        return redirect(url_for('harvestsettings.details_view',
                                id=request.args.get('id')))


    @expose('/pause/')
    def pause(self):
        """Pause harvesting."""
        harvesting = HarvestSettings.query.filter_by(id=request.args.get('id')).first()
        celery.current_app.control.revoke(harvesting.task_id, terminate=True)
        return redirect(url_for('harvestsettings.details_view',
                                id=request.args.get('id')))


    @expose('/clear/')
    def clear(self):
        """Clear harvesting."""
        harvesting = HarvestSettings.query.filter_by(id=request.args.get('id')).first()
        harvesting.task_id = None
        harvesting.resumption_token = None
        harvesting.item_processed = 0
        db.session.commit()
        return redirect(url_for('harvestsettings.details_view',
                                id=request.args.get('id')))


    @expose('/status/<string:task_id>', methods=['GET'])
    def get_task_status(self, task_id):
        """Get the status of the harvest task."""
        if not task_id:
            return abort(500)

        task_result = celery.result.AsyncResult(task_id)
        if task_result.state == 'SUCCESS':
            response = {
                'start_time': task_result.info[0]['start_time'],
                'end_time': task_result.info[0]['end_time'],
                'total_records': task_result.info[0]['total_records'],
                'state': task_result.state
            }
        else:  # PENDING ERROR or other state
            response = {
                'start_time': '',
                'end_time': '',
                'total_records': '',
                'state': task_result.state
            }
        return jsonify(response)

    details_template = 'invenio_oaiharvester/admin/harvest_details.html'
    can_create = True
    can_delete = True
    can_edit = True
    can_view_details = True
    page_size = 25

    column_formatters = dict(
        running_status=run_stats(),
        run_time=run_time(),
        Harvesting=control_btns()
    )
    column_details_list = (
        'repository_name', 'base_url', 'from_date', 'until_date',
        'set_spec', 'metadata_prefix', 'target_index.index_name',
        'update_style', 'auto_distribution', 'running_status', 'run_time',
        'Harvesting',
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
    name=_('Harvesting'),
)

__all__ = (
    'harvest_admin_view'
)
