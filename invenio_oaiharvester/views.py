# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 National Institute of Informatics.
#
# weko-sitemap is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module of weko-sitemap."""

from __future__ import absolute_import, print_function

from flask import Blueprint
from flask_babelex import gettext as _

blueprint = Blueprint(
    'invenio_oaiharvester',
    __name__,
    template_folder='templates',
    static_folder='static',
)
