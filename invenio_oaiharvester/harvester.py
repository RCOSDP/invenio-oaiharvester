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

import re
import requests
from collections import OrderedDict
from functools import partial
from celery import shared_task
from lxml import etree
from weko_records.models import ItemType
from .models import HarvestSettings
from weko_deposit.api import WekoDeposit
from invenio_db import db

DEFAULT_FIELD = [
    'title_en',
    'title_ja',
    'keywords',
    'keywords_en',
    'pubdate',
    'lang']


def list_sets(url, encoding='utf-8'):
    sets = []
    payload = {
        'verb' : 'ListSets'}
    while True:
        response = requests.get(url, params=payload)
        et = etree.XML(response.text.encode(encoding))
        sets = sets + et.findall('./ListSets/set', namespaces=et.nsmap)
        resumptionToken = et.find('./ListSets/resumptionToken', namespaces=et.nsmap)
        if resumptionToken is not None and resumptionToken.text is not None:
            payload['resumptionToken'] = resumptionToken.text
        else:
            break
    return sets


def list_records(
        url,
        from_date=None,
        until_date=None,
        metadata_prefix=None,
        setspecs='*',
        encoding='utf-8'):
    payload = {
        'verb' : 'ListRecords',
        'from' : from_date,
        'until' : until_date,
        'metadataPrefix': metadata_prefix,
        'set': setspecs}
    records = []
    while True:
        response = requests.get(url, params=payload)
        et = etree.XML(response.text.encode(encoding))
        records = records + et.findall('./ListRecords/record', namespaces=et.nsmap)
        resumptionToken = et.find('./ListRecords/resumptionToken', namespaces=et.nsmap)
        if resumptionToken is not None and resumptionToken.text is not None:
            payload['resumptionToken'] = resumptionToken.text
        else:
            break
    return records


def map_field(schema):
    res = {}
    for field_name in schema['properties']:
        if field_name not in DEFAULT_FIELD:
            res[schema['properties'][field_name]['title']] = field_name
    return res


def get_newest_itemtype_info(type_name):
    target = None
    for t in ItemType.query.all():
        if t.item_type_name.name == type_name:
            if target == None or target.updated < t.updated:
                target = t
    return target


def add_creator(schema, res, creator_name, lang=''):
    creator_field = map_field(schema)['Creator']
    subitems = map_field(schema['properties'][creator_field]['items'])
    creator_name_array_name = subitems['Creator Name']
    creator_name_array_subitems = \
        map_field(schema['properties'][creator_field]['items']['properties'][creator_name_array_name]['items'])
    item = {subitems['Affiliation']:'',
            subitems['Creator Alternative']:'',
            subitems['Creator Name Identifier']:'',
            subitems['Family Name']:'',
            subitems['Given Name']:'',
            subitems['Creator Name'] : {
                creator_name_array_subitems['Creator Name']:creator_name,
                creator_name_array_subitems['Language']:lang}}
    if creator_field not in res:
        res[creator_field] = []
    res[creator_field].append(item)


def add_contributor(schema, res, contributor_name, lang=''):
    contributor_field = map_field(schema)['Contributor']
    subitems = map_field(schema['properties'][contributor_field]['items'])
    contributor_name_array_name = subitems['Contributor Name']
    contributor_name_array_subitems = \
        map_field(schema['properties'][contributor_field]['items']['properties'][contributor_name_array_name]['items'])
    item = {subitems['Affiliation']:'',
            subitems['Contributor Alternative']:'',
            subitems['Contributor Name Identifier']:'',
            subitems['Family Name']:'',
            subitems['Given Name']:'',
            subitems['Contributor Name'] : {
                contributor_name_array_subitems['Contributor Name']:contributor_name,
                contributor_name_array_subitems['Language']:lang}}
    if contributor_field not in res:
        res[contributor_field] = []
    res[contributor_field].append(item)


def add_relation(schema, res, relation, relation_type=''):
    relation_field = map_field(schema)['Relation']
    subitems = map_field(schema['properties'][relation_field]['items'])
    related_identifier_array_name = subitems['Related Identifier']
    related_identifier_array_subitems = \
        map_field(schema['properties'][relation_field]['items']['properties'][related_identifier_array_name]['items'])
    related_title_array_name = subitems['Related Title']
    related_title_array_subitems = \
        map_field(schema['properties'][relation_field]['items']['properties'][related_title_array_name]['items'])
    item = {subitems['Relation']:relation,
            subitems['Relation Type']:relation_type,
            subitems['Related Identifier']: {
                related_identifier_array_subitems['Related Identifier'],
                related_identifier_array_subitems['Related Identifier Type']},
            subitems['Related Title']: {
                related_title_array_subitems['Related Title'],
                related_title_array_subitems['Language']}}
    if relation_field not in res:
        res[relation_field] = []
    res[relation_field].append(item)


def add_rights(schema, res, rights, lang='', rights_resource=''):
    rights_field = map_field(schema)['Rights']
    subitems = map_field(schema['properties'][rights_field]['items'])
    rights_array_name = subitems['Rights']
    rights_array_subitems = \
        map_field(schema['properties'][rights_field]['items']['properties'][rights_array_name]['items'])
    item = {subitems['Rights Resource']:rights_resource,
            subitems['Rights']: {
                rights_array_subitems['Rights']:rights,
                rights_array_subitems['Language']:lang}}
    if rights_field not in res:
        res[rights_field] = []
    res[rights_field].append(item)


def add_identifier(schema, res, identifier, identifier_type=''):
    identifier_field = map_field(schema)['Identifier']
    subitems = map_field(schema['properties'][identifier_field]['items'])
    identifier_item_name = subitems['Identifier']
    identifier_type_item_name = subitems['Identifier Type']
    if identifier_field not in res:
        res[identifier_field] = []
    res[identifier_field].append({identifier_item_name:identifier, identifier_type_item_name:identifier_type})


def add_description(schema, res, description, description_type='', lang=''):
    description_field = map_field(schema)['Description']
    subitems = map_field(schema['properties'][description_field]['items'])
    description_item_name = subitems['Description']
    description_type_item_name = subitems['Description Type']
    language_item_name = subitems['Language']
    if description_field not in res:
        res[description_field] = []
    res[description_field].append({
        description_item_name : description,
        description_type_item_name:description_type,
        language_item_name : lang})


def add_subject(schema, res, subject, subject_uri='', subject_scheme='', lang=''):
    subject_field = map_field(schema)['Subject']
    subitems = map_field(schema['properties'][subject_field]['items'])
    subject_item_name = subitems['Subject']
    subject_uri_item_name = subitems['Subject URI']
    subject_scheme_item_name = subitems['Subject Scheme']
    language_item_name = subitems['Language']
    if subject_field not in res:
        res[subject_field] = []
    res[subject_field].append({
        subject_item_name : subject,
        subject_uri_item_name : subject_uri,
        subject_scheme_item_name : subject_scheme,
        language_item_name : lang})


def add_title(schema, res, title, lang=''):
#    if 'title_en' not in res:
#        res['title_en'] = title
#    if 'title_ja' not in res:
#        res['title_ja'] = title
    title_field = map_field(schema)['Title']
    subitems = map_field(schema['properties'][title_field]['items'])
    title_item_name = subitems['Title']
    language_item_name = subitems['Language']
    if title_field not in res:
        res[title_field] = []
    res[title_field].append({title_item_name:title, language_item_name:lang})


def add_language(schema, res, lang):
#    if 'lang' not in res:
#        res['lang'] = lang
    language_field = map_field(schema)['Language']
    subitems = map_field(schema['properties'][language_field]['items'])
    language_item_name = subitems['Language']
    if language_field not in res:
        res[language_field] = []
    res[language_field].append({language_item_name:lang})


def add_date(schema, res, date, date_type=''):
#    if 'pubdate' not in res:
#        res['pubdate'] = date
    date_field = map_field(schema)['Date']
    subitems = map_field(schema['properties'][date_field]['items'])
    date_item_name = subitems['Date']
    date_type_item_name = subitems['Date Type']
    if date_field not in res:
        res[date_field] = []
    res[date_field].append({date_item_name:date, date_type_item_name:date_type})


def add_publisher(schema, res, publisher, lang=''):
    publisher_field = map_field(schema)['Publisher']
    subitems = map_field(schema['properties'][publisher_field]['items'])
    publisher_item_name = subitems['Publisher']
    language_item_name = subitems['Language']
    if publisher_field not in res:
        res[publisher_field] = []
    res[publisher_field].append({publisher_item_name:publisher, language_item_name:lang})


RESOURCE_TYPE_MAP = {
    'conference paper' : 'Article',
    'data paper' : 'Article',
    'departmental bulletin paper' : 'Article',
    'editorial' : 'Article',
    'journal article' : 'Article',
    'periodical' : 'Article',
    'review article' : 'Article',
    'article' : 'Article',
    'Book' : 'Book',
    'book part' : 'Book',
    'cartographic material' : 'Cartographic Material',
    'map' : 'Cartographic Material',
    'conference object' : 'Conference object',
    'conference proceedings' : 'Conference object',
    'conference poster' : 'Conference object',
    'presentation' : 'Conference object',
    'dataset' : 'Dataset',
    'image' : 'Image',
    'still image' : 'Image',
    'moving image' : 'Image',
    'video' : 'Image',
    'lecture' : 'Lecture',
    'patent' : 'Patent',
    'internal report' : 'Report',
    'report' : 'Report',
    'research report' : 'Report',
    'technical report' : 'Report',
    'policy report' : 'Report',
    'report part' : 'Report',
    'working paper' : 'Report',
    'research paper' : 'Report',
    'sound' : 'Sound',
    'thesis' : 'Thesis',
    'bachelor thesis' : 'Thesis',
    'master thesis' : 'Thesis',
    'doctoral thesis' : 'Thesis',
    'thesis or dissertation' : 'Thesis',
    'interactive resource' : 'Multiple',
    'learning material' : 'Multiple',
    'musical notation' : 'Multiple',
    'research proposal' : 'Multiple',
    'software' : 'Multiple',
    'technical documentation' : 'Multiple',
    'workflow' : 'Multiple',
    'other' : 'Multiple',
}


def map_sets(sets, encoding='utf-8'):
    res = OrderedDict()
    pattern = '<setSpec>(.+)</setSpec><setName>(.+)</setName>'
    for s in sets:
        xml = etree.tostring(s, encoding=encoding).decode()
        m = re.search(pattern, xml)
        spec = m.group(1)
        name = m.group(2)
        if spec and name:
            res[spec] = name 
    return res


class DCMapper:
    def __init__(self, xml):
        self.xml = xml
        m_type = '<dc:type.*>(.+?)</dc:type>'
        type_tags = re.findall(m_type, self.xml)
        self.itemtype = get_newest_itemtype_info('Multiple')
        for t in type_tags:
            if t.lower() in RESOURCE_TYPE_MAP:
                self.itemtype \
                    = get_newest_itemtype_info(RESOURCE_TYPE_MAP[t.lower()])
                break


    def specs(self):
        pattern = '<setSpec>(.+?)</setSpec>'
        return re.findall(pattern, self.xml)


    def map(self):
        res = {'$schema': self.itemtype.id}
        dc_tags = {
            'title' : [], 'creator' : [], 'contributor' : [], 'rights' : [],
            'subject' :[], 'description' :[], 'publisher' : [], 'date' : [],
            'type' : [], 'format' : [], 'identifier' : [], 'source' : [],
            'language' : [], 'relation' : [], 'coverage' : []}
        add_funcs = {
            'creator' : partial(add_creator, self.itemtype.schema, res),
            'contributor' : partial(add_contributor, self.itemtype.schema, res),
            'title' : partial(add_title, self.itemtype.schema, res),
            'subject' : partial(add_subject, self.itemtype.schema, res),
            'description' : partial(add_description, self.itemtype.schema, res),
            'publisher' : partial(add_publisher, self.itemtype.schema, res),
            'date': partial(add_date, self.itemtype.schema, res),
            'identifier': partial(add_identifier, self.itemtype.schema, res),
            'language': partial(add_language, self.itemtype.schema, res),
            'relation' partial(add_relation, self.itemtype.schema, res),
            'rights': partial(add_rights, self.itemtype.schema, res)}
        for tag in dc_tags:
            if tag in add_funcs:
                m = '<dc:{0}.*>(.+?)</dc:{0}>'.format(tag)
                dc_tags[tag] = re.findall(m, self.xml)
                for value in dc_tags[tag]:
                    add_funcs[tag](value)
        return res
