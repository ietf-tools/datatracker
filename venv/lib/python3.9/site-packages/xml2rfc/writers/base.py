# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

import calendar
import codecs
import copy
import datetime
import textwrap
import os
import re
import xml2rfc.log
import xml2rfc.util
import xml2rfc.utils

from lxml import etree
from argparse import Namespace
from urllib.parse import urlparse

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass

from xml2rfc import strings, log
from xml2rfc.util.date import extract_date, augment_date, format_date, get_expiry_date
from xml2rfc.util.file import can_access, FileAccessError
from xml2rfc.util.name import short_author_ascii_name_parts, full_author_name_expansion, short_author_name_parts
from xml2rfc.util.unicode import is_svg
from xml2rfc.utils import namespaces, find_duplicate_ids, slugify


SUBSERIES = {
        'STD': 'Internet Standard',
        'BCP': 'Best Current Practice',
        'FYI': 'For Your Information',
}

DEADLY_ERRORS = [
    'Element svg has extra content: script',
    'Did not expect element script there',
]

default_silenced_messages = [
#    ".*[Pp]ostal address",
]


default_options = Namespace()
default_options.__dict__ = {
        'accept_prepped': None,
        'add_xinclude': None,
        'allow_local_file_access': False,
        'basename': None,
        'bom': False,
        'cache': None,
        'clear_cache': False,
        'css': None,
        'config_file': None,
        'country_help': False,
        'date': None,
        'datestring': None,
        'debug': False,
        'docfile': False,
        'doc_template': None,
        'doi_base_url': 'https://doi.org/',
        'draft_revisions': False,
        'dtd': None,
        'expand': False,
        'external_css': False,
        'external_js': False,
        'filename': None,
        'first_page_author_org': True,
        'html': False,
        'id_base_url': 'https://datatracker.ietf.org/doc/html/',
        'id_html_archive_url': 'https://www.ietf.org/archive/id/',
        'id_reference_base_url': 'https://datatracker.ietf.org/doc/html/',
        'id_is_work_in_progress': True,
        'indent': 2,
        'info': False,
        'info_base_url': 'https://www.rfc-editor.org/info/',
        'inline_version_info': True,
        'legacy': False,
        'legacy_date_format': False,
        'legacy_list_symbols': False,
        'list_symbols': ('*', '-', 'o', '+'),
        'manpage': False,
        'metadata_js_url': 'metadata.min.js',
        'no_css': False,
        'no_dtd': None,
        'no_network': False,
        'nroff': False,
        'omit_headers': None,
        'orphans': 2,
        'output_filename': None,
        'output_path': None,
        'pagination': True,
        'pi_help': False,
        'pdf': False,
        'pdf_help': False,
        'preptool': False,
        'quiet': False,
        'remove_pis': False,
        'raw': False,
        'rfc': None,
        'rfc_base_url': 'https://www.rfc-editor.org/rfc/',
        'rfc_html_archive_url': 'https://www.rfc-editor.org/rfc/',
        'rfc_local': True,
        'rfc_reference_base_url': 'https://rfc-editor.org/rfc/',
        'silence': default_silenced_messages,
        'skip_config_files': False,
        'source': None,
        'strict': False,
        'table_hyphen_breaks': False,
        'table_borders': 'full',
        'template_dir': os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        'text': True,
        'unprep': False,
        'use_bib': False,
        'utf8': False,
        'values': False,
        'verbose': False,
        'version': False,
        'v2v3': False,
        'v3': True,
        'vocabulary': 'v2',
        'widows': 2,
        'warn_bare_unicode': False,
    }

class _RfcItem:
    """ A unique ID object for an anchored RFC element.
    
        Anchored elements are the following: Automatic sections, user (middle)
        sections, paragraphs, references, appendices, figures, and tables.
        
        RfcItems are collected into an index list in the base writer
    """
    def __init__(self, autoName, autoAnchor, counter='', title='', anchor='',
                 toc=True, level=1, appendix=False):
        self.counter = str(counter)
        self.autoName = autoName
        self.autoAnchor = autoAnchor
        self.title = title
        self.anchor = anchor
        self.toc = toc
        self.level = level
        self.appendix = appendix
        self.page = 0    # This will be set after buffers are complete!
        self.used = False


class _IrefItem:
    """ A unique ID object for an iref element """
    def __init__(self, anchor=None):
        self.pages = []
        self.subitems = {}
        self.anchor = anchor


class RfcWriterError(Exception):
    """ Exception class for errors during document writing """
    def __init__(self, msg):
        self.msg = msg


class BaseRfcWriter:
    """ Base class for all writers

        All public methods need to be overridden for a writer implementation.
    """

    # -------------------------------------------------------------------------
    # Attribute default values
    #
    # These will mainly come into play if DTD validation was disabled, and
    # processing that happens to rely on DTD populated attributes require a lookup
    defaults = {
        'section_toc':              'default',
        'xref_pageno':              'false',
        'xref_format':              'default',
        'iref_primary':             'false',
        'spanx_style':              'emph',
        'figure_suppress-title':    'false',
        'figure_title':             '',
        'figure_align':             'left',
        'vspace_blanklines':        0,
        'table_suppress-title':     'false',
        'table_title':              '',
        'table_align':              'center',
        'table_style':              'full',
        'ttcol_align':              'left',
        'ipr':                      'trust200902',
        'submissionType':           'IETF',
        'consensus':                'no',
    }

    # -------------------------------------------------------------------------
    # Boilerplate text
    boilerplate = {}

    # The RFC Editor's switchover date for https URLs
    boilerplate_https_date = datetime.date(year=2017, month=8, day=21)

    # Document stream names
    boilerplate['document_stream'] = {}
    boilerplate['document_stream']['IETF'] = \
        'Internet Engineering Task Force (IETF)'
    boilerplate['document_stream']['IAB'] = \
        'Internet Architecture Board (IAB)'
    boilerplate['document_stream']['IRTF'] = \
        'Internet Research Task Force (IRTF)'
    boilerplate['document_stream']['independent'] = \
        'Independent Submission'

    # Draft workgroup name
    boilerplate['draft_workgroup'] = 'Network Working Group'

    # Category names
    boilerplate['std'] = 'Standards Track'
    boilerplate['bcp'] = 'Best Current Practice'
    boilerplate['exp'] = 'Experimental'
    boilerplate['info'] = 'Informational'
    boilerplate['historic'] = 'Historic'

    # Series type
    boilerplate['series_name'] = {}
    boilerplate['series_name']['std'] = 'STD'
    boilerplate['series_name']['bcp'] = 'BCP'
    boilerplate['series_name']['info'] = 'FYI'

    # ISSN
    boilerplate['issn'] = '2070-1721'

    # 'Status of this Memo' boilerplate for RFCs
    boilerplate['status'] = {
        'std': {},
        'bcp': {},
        'exp': {},
        'info': {},
        'historic': {},
    }
    # 'Status of this Memo' boilerplate for RFCs
    boilerplate['status_5741'] = {
    }

    # Paragraph 1
    boilerplate['status']['std']['p1'] = \
        'This is an Internet Standards Track document.'
    boilerplate['status']['bcp']['p1'] = \
        'This memo documents an Internet Best Current Practice.'
    boilerplate['status']['exp']['p1'] = \
        'This document is not an Internet Standards Track specification; ' \
        'it is published for examination, experimental implementation, and ' \
        'evaluation.'
    boilerplate['status']['info']['p1'] = \
        'This document is not an Internet Standards Track specification; ' \
        'it is published for informational purposes.'
    boilerplate['status']['historic']['p1'] = \
        'This document is not an Internet Standards Track specification; ' \
        'it is published for the historical record.'

    # Paragraph 2 header
    boilerplate['status']['exp']['p2'] = \
        'This document defines an Experimental Protocol for the Internet ' \
        'community.'
    boilerplate['status']['historic']['p2'] = \
        'This document defines a Historic Document for the Internet ' \
        'community.'

    # Paragraph 2 body
    boilerplate['status']['IETF'] = \
        'This document is a product of the Internet Engineering Task Force ' \
        '(IETF).  It has been approved for publication by the Internet ' \
        'Engineering Steering Group (IESG).'
    boilerplate['status']['IETF_consensus'] = \
        'This document is a product of the Internet Engineering Task Force ' \
        '(IETF).  It represents the consensus of the IETF community.  It has ' \
        'received public review and has been approved for publication by ' \
        'the Internet Engineering Steering Group (IESG).'
    boilerplate['status']['IRTF'] = \
        'This document is a product of the Internet Research Task Force ' \
        '(IRTF).  The IRTF publishes the results of Internet-related ' \
        'research and development activities.  These results might not be ' \
        'suitable for deployment.'
    boilerplate['status']['IRTF_workgroup'] = \
        'This RFC represents the individual opinion(s) ' \
        'of one or more members of the %s Research Group of the Internet ' \
        'Research Task Force (IRTF).'
    boilerplate['status']['IRTF_workgroup_consensus'] = \
        'This RFC represents the consensus of the ' \
        '%s Research Group of the Internet Research Task Force (IRTF).'
    boilerplate['status']['IAB'] = \
        'This document is a product of the Internet Architecture Board ' \
        '(IAB) and represents information that the IAB has deemed valuable ' \
        'to provide for permanent record.'
    boilerplate['status']['IAB_consensus'] = (
        'This document is a product of the Internet Architecture Board ' 
        '(IAB) and represents information that the IAB has deemed valuable '
        'to provide for permanent record.  It represents the consensus of '
        'the Internet Architecture Board (IAB).')
    boilerplate['status']['independent'] = \
        'This is a contribution to the RFC Series, independently of any ' \
        'other RFC stream.  The RFC Editor has chosen to publish this ' \
        'document at its discretion and makes no statement about its value ' \
        'for implementation or deployment.'

    # Paragraph 2 last sentence
    boilerplate['status']['p2end_ietf_std'] = \
        'Further information on Internet Standards is available ' \
        'in Section 2 of RFC 7841.'
    boilerplate['status']['p2end_ietf_bcp'] = \
        'Further information on BCPs is available in Section 2 of RFC 7841.'
    boilerplate['status']['p2end_ietf_other'] = \
        'Not all documents approved by the IESG are candidates for any ' \
        'level of Internet Standard; see Section 2 of RFC 7841.'
    boilerplate['status']['p2end_other'] = \
        'Documents approved for publication by the %s are not ' \
        'candidates for any level of Internet Standard; see Section 2 of RFC ' \
        '7841.'

    boilerplate['status_5741']['p2end_ietf_std'] = \
        'Further information on Internet Standards is available ' \
        'in Section 2 of RFC 5741.'
    boilerplate['status_5741']['p2end_ietf_bcp'] = \
        'Further information on BCPs is available in Section 2 of RFC 5741.'
    boilerplate['status_5741']['p2end_ietf_other'] = \
        'Not all documents approved by the IESG are candidates for any ' \
        'level of Internet Standard; see Section 2 of RFC 5741.'
    boilerplate['status_5741']['p2end_other'] = \
        'Documents approved for publication by the %s are not ' \
        'candidates for any level of Internet Standard; see Section 2 of RFC ' \
        '5741.'

    # Paragraph 3
    boilerplate['status']['p3'] = (
        'Information about the current status of this document, any errata, '
        'and how to provide feedback on it may be obtained at '
        'http://www.rfc-editor.org/info/rfc%s.')
    boilerplate['status']['p3_s'] = (
        'Information about the current status of this document, any errata, '
        'and how to provide feedback on it may be obtained at '
        'https://www.rfc-editor.org/info/rfc%s.')

    # 'Status of this Memo' boilerplate for drafts
    boilerplate['status']['draft'] = [
       'Internet-Drafts are working documents of the Internet Engineering '
       'Task Force (IETF).  Note that other groups may also distribute '
       'working documents as Internet-Drafts.  The list of current Internet-'
       'Drafts is at http://datatracker.ietf.org/drafts/current/.',
       #
       'Internet-Drafts are draft documents valid for a maximum of six months '
       'and may be updated, replaced, or obsoleted by other documents at any '
       'time.  It is inappropriate to use Internet-Drafts as reference '
       'material or to cite them other than as "work in progress."']
    boilerplate['status']['draft_s'] = [
       'Internet-Drafts are working documents of the Internet Engineering '
       'Task Force (IETF).  Note that other groups may also distribute '
       'working documents as Internet-Drafts.  The list of current Internet-'
       'Drafts is at https://datatracker.ietf.org/drafts/current/.',
       #
       'Internet-Drafts are draft documents valid for a maximum of six months '
       'and may be updated, replaced, or obsoleted by other documents at any '
       'time.  It is inappropriate to use Internet-Drafts as reference '
       'material or to cite them other than as "work in progress."']

    boilerplate['draft_expire'] = \
       'This Internet-Draft will expire on %s.'

    # IPR status boilerplate
    boilerplate['ipr_200902_status'] = \
        'This Internet-Draft is submitted in full conformance ' \
        'with the provisions of BCP 78 and BCP 79.'
    boilerplate['ipr_200811_status'] = \
        'This Internet-Draft is submitted to IETF in full conformance ' \
        'with the provisions of BCP 78 and BCP 79.'
    
    # Copyright boilerplate
    boilerplate['base_copyright_header'] = \
        'Copyright (c) %s IETF Trust and the persons identified as the ' \
        'document authors.  All rights reserved.'
    boilerplate['base_copyright_body'] = (
        'This document is subject to BCP 78 and the IETF Trust\'s Legal '
        'Provisions Relating to IETF Documents '
        '(http://trustee.ietf.org/license-info) in effect on the date of '
        'publication of this document.  Please review these documents '
        'carefully, as they describe your rights and restrictions with respect '
        'to this document.')
    boilerplate['base_copyright_body_s'] = (
        'This document is subject to BCP 78 and the IETF Trust\'s Legal '
        'Provisions Relating to IETF Documents '
        '(https://trustee.ietf.org/license-info) in effect on the date of '
        'publication of this document.  Please review these documents '
        'carefully, as they describe your rights and restrictions with respect '
        'to this document.')

    # IPR values which append things to copyright
    boilerplate['ipr_200902_copyright_ietfbody'] = \
        'Code Components extracted from this document must ' \
        'include Simplified BSD License text as described in Section 4.e of ' \
        'the Trust Legal Provisions and are provided without warranty as ' \
        'described in the Simplified BSD License.'
    boilerplate['ipr_noModification_copyright'] = \
        'This document may not be modified, and derivative works of it may ' \
        'not be created, except to format it for publication as an RFC or ' \
        'to translate it into languages other than English.'
    boilerplate['ipr_noDerivatives_copyright'] = \
        'This document may not be modified, and derivative works of it may ' \
        'not be created, and it may not be published except as an ' \
        'Internet-Draft.'
    boilerplate['ipr_pre5378Trust200902_copyright'] = \
        'This document may contain material from IETF Documents or IETF ' \
        'Contributions published or made publicly available before ' \
        'November 10, 2008.  The person(s) controlling the copyright in some ' \
        'of this material may not have granted the IETF Trust the right to ' \
        'allow modifications of such material outside the IETF Standards ' \
        'Process. Without obtaining an adequate license from the person(s) ' \
        'controlling the copyright in such materials, this document may not ' \
        'be modified outside the IETF Standards Process, and derivative ' \
        'works of it may not be created outside the IETF Standards Process, ' \
        'except to format it for publication as an RFC or to translate it ' \
        'into languages other than English.'

    # Any extra boilerplate
    # Disabled. See issue #123, http://trac.tools.ietf.org/tools/xml2rfc/trac/ticket/123
    ## boilerplate['iprnotified'] = \
    ##     'The IETF has been notified of intellectual property rights ' \
    ##     'claimed in regard to some or all of the specification contained ' \
    ##     'in this document.  For more information consult the online list ' \
    ##     'of claimed rights.'
    
    # Stream approvers
    approvers = {
        'IAB': 'IAB',
        'IRTF': 'IRSG',
        'independent': 'RFC Editor',
    }

    # Valid IPR attributes
    supported_ipr = [
        'trust200902',
        'noModificationTrust200902',
        'noDerivativesTrust200902',
        'pre5378Trust200902',
        'trust200811',
        'noModificationTrust200811',
        'noDerivativesTrust200811',
        'none',
    ]

    # -------------------------------------------------------------------------

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None):
        if not quiet is None:
            options.quiet = quiet
        self.options = options
        self.date = date if date is not None else datetime.date.today()
        self.expire_string = ''
        self.ascii = False
        self.nbws_cond = u'\u00A0'
        self.eref_list = []
        self.xmlrfc = xmlrfc
        self.pis = self.xmlrfc.getpis()

        # We will refer to the XmlRfc document root as 'r'
        self.xmlrfc = xmlrfc
        self.r = xmlrfc.getroot()

        # Document counters
        self.ref_start = 1              # Start of reference counters
        self.refs_start = 1             # Start of references sections
        self.figure_count = 0
        self.table_count = 0
        self.eref_count = 0

        # Set RFC number and draft flag
        self.rfcnumber = self.r.attrib.get('number', '')
        self.draft = bool(not self.rfcnumber)
        
        # Used for two-pass indexing
        self.indexmode = False

        # Item Indicies
        self._index = []
        self._iref_index = {}

    def _make_iref(self, item, subitem=None, anchor=None):
        """ Create an iref ID object if it doesnt exist yet """
        last = None
        if item not in self._iref_index:
            self._iref_index[item] = _IrefItem()
            last = self._iref_index[item]
        if subitem and subitem not in self._iref_index[item].subitems:
            self._iref_index[item].subitems[subitem] = _IrefItem()
            last = self._iref_index[item].subitems[subitem]
        if last and anchor:
            last.anchor = anchor

    def _add_iref_to_index(self, element):
        item = element.attrib.get('item', None)
        if item:
            subitem = element.attrib.get('subitem', None)
            self._make_iref(item, subitem)
            # Store the buffer position for pagination data later
            pos = len(self.buf)
            if not self.indexmode:
                if pos not in self.iref_marks:
                    self.iref_marks[pos] = []
                self.iref_marks[pos].append((item, subitem))

    def _indexParagraph(self, counter, p_counter, anchor=None, toc=False):
        counter = str(counter)  # This is the section counter
        p_counter = str(p_counter)  # This is the paragraph counter
        autoName = 'Section ' + counter + ', Paragraph ' + p_counter
        autoAnchor = 'rfc.section.' + counter + '.p.' + p_counter
        item = _RfcItem(autoName, autoAnchor, anchor=anchor, toc=toc, counter=p_counter)
        self._index.append(item)
        return item

    def _indexListParagraph(self, p_counter, anchor, toc=False):
        p_counter = str(p_counter)
        autoName = 'Paragraph ' + p_counter
        item = _RfcItem(autoName, '', counter=p_counter, anchor=anchor, toc=toc)
        self._index.append(item)
        return item

    def _indexSection(self, counter, title=None, anchor=None, toc=True, \
                      level=1, appendix=False, numbered=True):
        counter = str(counter)
        if numbered:
            if appendix:
                autoName = 'Appendix' + self.nbws_cond + counter
                autoAnchor = 'rfc.appendix.' + counter
            else:
                autoName = 'Section' + self.nbws_cond + counter
                autoAnchor = 'rfc.section.' + counter
            item = _RfcItem(autoName, autoAnchor, counter=counter, title=title,
                           anchor=anchor, toc=toc, level=level, appendix=appendix)
        else:
            if not title:
                raise RfcWriterError("No title available when trying to insert index item for anchor %s" % anchor)
            autoAnchor = 'rfc.' + re.sub('[^A-Za-z0-9]+', '_', title).lower()
            item = _RfcItem(title, autoAnchor, title=title)
        self._index.append(item)
        return item

    def _indexReferences(self, counter, title=None, anchor=None, toc=True, \
                         subCounter=0, level=1):
        if subCounter < 1:
            autoName = 'References'
            autoAnchor = 'rfc.references'
        else:
            subCounter = str(subCounter)
            autoName = 'References' + self.nbws_cond + subCounter
            autoAnchor = 'rfc.references.' + subCounter
        item = _RfcItem(autoName, autoAnchor, counter=counter, title=title, \
                       anchor=anchor, toc=toc, level=level)
        self._index.append(item)
        return item
    
    def _indexFigure(self, counter, title=None, anchor=None, toc=False):
        counter = str(counter)
        autoName = 'Figure' + self.nbws_cond + counter
        autoAnchor = 'rfc.figure.' + counter
        item = _RfcItem(autoName, autoAnchor, counter=counter, title=title, anchor=anchor, \
                       toc=toc)
        self._index.append(item)
        return item
        
    def _indexTable(self, counter, title=None, anchor=None, toc=False):
        counter = str(counter)
        autoName = 'Table' + self.nbws_cond + counter
        autoAnchor = 'rfc.table.' + counter
        item = _RfcItem(autoName, autoAnchor, counter=counter, title=title, anchor=anchor, toc=toc)
        self._index.append(item)
        return item

    def _indexRef(self, counter, title=None, anchor=None, toc=False):
        counter = str(counter)
        if self.pis['symrefs'] == 'yes':
            autoName = '[' + (anchor or counter ) +']'
        else:
            autoName = '['+counter+']'
        autoAnchor = 'rfc.ref.' + counter
        item = _RfcItem(autoName, autoAnchor, counter=counter, title=title, anchor=anchor, toc=toc)
        self._index.append(item)
        return item

    def _indexCref(self, counter, anchor):
        counter = str(counter)
        autoName = 'Comment' + self.nbws_cond + anchor
        autoAnchor = 'rfc.comment.' + counter
        item = _RfcItem(autoName, autoAnchor, counter=counter, anchor=anchor, toc=False)
        self._index.append(item)
        return item

    def _indexAuthor(self, counter, anchor, name):
        autoName = name
        autoAnchor = 'rfc.author.%s' % counter
        item = _RfcItem(autoName, autoAnchor, counter=counter, anchor=anchor, toc=False)
        self._index.append(item)
        return item

    def get_initials(self, author):
        """author is an rfc2629 author element.  Return the author initials,
        fixed up according to current flavour and policy."""
        initials = author.attrib.get('initials', '')
        multiple = author.pis["multiple-initials"] == "yes"
        initials_list = re.split("[. ]+", initials)
        try:
            initials_list.remove('')
        except:
            pass
        if len(initials_list) > 0:
            if multiple:
                # preserve spacing, but make sure all parts have a trailing
                # period
                initials = initials.strip()
                initials += '.' if not initials.endswith('.') else ''
                initials = re.sub(r'([^.]) ', r'\g<1>. ', initials)
            else:
                initials = initials_list[0] + "."
        return initials

    def parse_pi(self, pi):
        return xml2rfc.utils.parse_pi(pi, self.pis)

    def get_numeric_pi(self, key, default):
        num = self.pis.get(key, None)
        if num is None:
            return default
        if not num.isdigit():
            xml2rfc.log.warn('Expected a numeric value for the %s PI, found "%s"' % (key, num))
            return default
        return int(num)

    def _getTocIndex(self):
        return [item for item in self._index if item.toc]
        
    def _getItemByAnchor(self, anchor):
        for item in self._index:
            if item.autoAnchor == anchor or item.anchor == anchor:
                return item
        return None
    
    def _validate_ipr(self):
        """ Ensure the application has boilerplate for the ipr attribute given """
        ipr = self.r.attrib.get('ipr', self.defaults['ipr'])
        if not ipr in self.supported_ipr:
            raise RfcWriterError('No boilerplate text available for '
            'ipr: \'%s\'.  Acceptable values are: ' % ipr + \
            ', '.join(self.supported_ipr))
        
    def is_numbered(self, node):
        attr = node.attrib.get('numbered', 'true')
        return attr in ['yes', 'true', ]
    
    def _format_date(self):
        """ Fix the date data """
        today = self.date
        date = self.r.find('front/date')
        assert date is not None, "Bug in schema validation: no date element in document"
        year = date.attrib.get('year')
        if not year:
            year = str(self.date.year)
            date.set('year', year)
        if not year.isdigit():
            xml2rfc.log.error("Expected a numeric year, found '%s'" % (year, ))
        year = int(year)
        #
        month = date.attrib.get('month')
        if not month:
            if year != today.year:
                xml2rfc.log.error("Cannot handle a <date> with year different than this year, and no month.  Using today's date.")
                year = today.year
            month = today.month
            date.set('month', str(month))
        else:
            if not month.isdigit():
                month = xml2rfc.util.date.normalize_month(month)
            month = int(month)
        #
        day = date.attrib.get('day')
        if day is None:
            temp_date = datetime.date(year=year, month=month, day=1)
            if today.year == year and today.month == month:
                day = today.day
            elif abs(today - temp_date) < datetime.timedelta(days=34):
                if datetime.date(year=year, month=month, day=1) < today:
                    # wrong month, and the first day of that month is earlier
                    # than today.  Use the last day of the month
                    day = calendar.monthrange(year, month)[1]
                else:
                    # wrong month, later than this month.  Use the first day.
                    day = 1
            else:
                day = 1
        else:
            day = int(day)

        self.date = datetime.date(year=year, month=month, day=day)

        # Setup the expiration string for drafts as published date + six months
        if self.draft:
            if not date.get('day'):
                date.set('day', str(day))
            if not date.get('month'):
                date.set('month', str(month))
            expire_date = self.date + datetime.timedelta(185)
            self.expire_string = expire_date.strftime('%B %d, %Y').replace(' 0', ' ')

    def _format_counter(self, text, count, list_length=1):
        """ Return a proper string for a formatted list bullet.  Allowed types:
                %c: Lowercase chars
                %C: Uppercase chars
                %d: Digits
                %i: Lowercase roman numerals
                %I: Uppercase roman numerals
                %o: octal
                %x: Lowercase hex
                %X: Uppercase hex
        """
        import math
        roman_widths = {        1:1,  2:2,  3:3,  4:2,  5:1,  6:2,  7:3,  8:4,  9:2,
                        10:1, 11:2, 12:3, 13:4, 14:3, 15:2, 16:3, 17:4, 18:5, 19:3,
                        20:2, 21:3, 22:4, 23:5, 24:4, 25:3, 26:4, 27:5, 28:6, 29:4, }
        #
        decimal_width = int(math.log(list_length, 10))
        roman_width = roman_widths.get(list_length, 6)
        letter_width = int(math.log(list_length, 26))
        hex_width = int(math.log(list_length, 16))
        octal_width = int(math.log(list_length, 8))
        extra_width = len(text)+1
        if '%d' in text:
            text = text.replace(r'%d', str(count)).ljust(decimal_width+extra_width)
        elif '%c' in text:
            text = text.replace(r'%c', xml2rfc.util.num.int2letter(count)).ljust(letter_width+extra_width)
        elif '%C' in text:
            text = text.replace(r'%C', xml2rfc.util.num.int2letter(count).upper()).ljust(letter_width+extra_width)
        elif '%i' in text:
            text = text.replace(r'%i', xml2rfc.util.num.int2roman(count)).ljust(roman_width+extra_width)
        elif '%I' in text:
            text = text.replace(r'%I', xml2rfc.util.num.int2roman(count).upper()).ljust(roman_width+extra_width)
        elif '%o' in text:
            text = text.replace(r'%o', oct(count).replace("0","",1)).replace("o","",1).ljust(octal_width+extra_width)
        elif '%x' in text:
            text = text.replace(r'%x', hex(count).replace("0x","",1)).ljust(hex_width+extra_width)
        elif '%X' in text:
            text = text.replace(r'%X', hex(count).replace("0x","",1).upper()).ljust(hex_width+extra_width)
        return text

    def _format_author_string(self, authors):
        """ Given a list of <author> elements, return a readable string of names """
        buf = []
        for i, author in enumerate(authors):
            organization = author.find('organization')
            initials, surname = short_author_name_parts(author)
            if i == len(authors) - 1 and len(authors) > 1:
                buf.append('and ')
            if surname:
                initials = self.get_initials(author) or initials or ''
                if i == len(authors) - 1 and len(authors) > 1:
                    # Last author is rendered in reverse
                    if len(initials) > 0:
                        buf.append(initials + ' ' + \
                                     surname)
                    else:
                        buf.append(surname)
                elif len(initials) > 0:
                    buf.append(surname + ', ' + initials)
                else:
                    buf.append(surname)
                if author.attrib.get('role', '') == 'editor':
                    buf.append(', Ed.')
            elif organization is not None and organization.text:
                # Use organization instead of name
                buf.append(organization.text.strip())
            else:
                continue
            if len(authors) == 2 and i == 0:
                buf.append(' ')
            elif i < len(authors) - 1:
                buf.append(', ')
        return ''.join(buf)

    def _prepare_top_left(self):
        """ Returns a lines of lines for the top left header """
        lines = []
        # Document stream / workgroup
        if not self.pis['private']:
            if self.draft:
                workgroup = self.r.find('front/workgroup')
                if workgroup is not None and workgroup.text:
                    lines.append(workgroup.text)
                else:
                    lines.append(self.boilerplate['draft_workgroup'])
            else:
                # Determine 'workgroup' from submissionType
                subtype = self.r.attrib.get('submissionType', 
                                            self.defaults['submissionType'])
                docstream = self.boilerplate['document_stream'].get(subtype)
                lines.append(docstream)

            # RFC number
            if not self.draft:
                lines.append('Request for Comments: ' + self.rfcnumber)
            elif not self.pis['private']:
                lines.append('Internet-Draft')

            # Series number
            category = self.r.attrib.get('category', '')
            seriesNo = self.r.attrib.get('seriesNo')
            if seriesNo is not None and category in self.boilerplate['series_name']:
                lines.append('%s: %s' % (self.boilerplate['series_name'][category], 
                                         seriesNo))

            # RFC relation notice
            approved_text = self.draft and '(if approved)' or ''
            obsoletes = self.r.attrib.get('obsoletes')
            if obsoletes:
                wrapper = textwrap.TextWrapper(width=40, subsequent_indent=' '*len('Obsoletes: '))
                line = 'Obsoletes: %s %s' % (obsoletes, approved_text)
                lines += wrapper.wrap(line)
            updates = self.r.attrib.get('updates')
            if updates:
                wrapper = textwrap.TextWrapper(width=40, subsequent_indent=' '*len('Updates: '))
                line = 'Updates: %s %s' % (updates, approved_text)
                lines += wrapper.wrap(line)

            # Category
            if category:
                cat_text = self.boilerplate[category]
                if self.draft:
                    lines.append('Intended status: ' + cat_text)
                else:
                    lines.append('Category: ' + cat_text)
            else:
                xml2rfc.log.warn('No category specified for document.')

            # Expiration notice for drafts
            if self.expire_string and not self.pis['private']:
                lines.append('Expires: ' + self.expire_string)

            # ISSN identifier
            if not self.draft:
                lines.append('ISSN: %s' % self.boilerplate['issn'])

        # Strip any whitespace from XML to make header as neat as possible
        lines = [ l.rstrip() for l in lines ]
        return lines

    def _prepare_top_right(self):
        """ Returns a list of lines for the top right header """
        lines = []
        # Keep track of previous organization and remove if redundant.
        last_org = None
        last_pos = None
        authors = self.r.findall('front/author')
        authors = [ a for a in authors if a.get('role') != 'contributor' ]
        for author in authors:
            role = author.attrib.get('role', '')
            if role == 'editor':
                role = ', Ed.'
            initials = self.get_initials(author)
            lines.append(initials + ' ' + author.attrib.\
                         get('surname', '') + role)
            organization = author.find('organization')
            org_name = ''
            if self.options.first_page_author_org:
                if organization is not None:
                    abbrev = organization.attrib.get("abbrev", None)
                    if  abbrev != None and abbrev.strip() != '':
                        org_name = abbrev.strip()
                    elif organization.text and organization.text.strip() != '':
                        org_name = organization.text.strip()
                if org_name == '':
                    lines.append('')
                else:
                    if org_name == last_org:
                        # Remove redundant organization
                        del lines[last_pos]
                    lines.append(org_name)
            last_org = org_name
            last_pos = len(lines)-1
        # remove blank lines between authors and date
        if lines[last_pos] == '':
            del lines[last_pos]
            last_pos = len(lines)-1

        date = self.r.find('front/date')
        if date is not None:
            year = date.attrib.get('year', '')
            month = date.attrib.get('month', '')
            day = date.attrib.get('day', '')
            if month:
                if month.isdigit():
                    month = calendar.month_name[int(month)]
                month = month + ' '
            if day:
                day = day + ', '
            lines.append(month + day + year)
            # Strip any whitespace from XML to make header as neat as possible
            lines = [ l.strip() for l in lines ]
        return lines

    def write_figure(self, figure):
        """ Writes <figure> elements """
        figure_align = figure.attrib.get('align', self.defaults['figure_align'])
        anchor = figure.attrib.get('anchor')
        title = figure.attrib.get('title', self.defaults['figure_title'])
        suppress_title = figure.attrib.get('suppress-title', 'false')

        # Keep track of count if there is an anchor, or PI was enabled
        if anchor or self.pis['figurecount'] == 'yes':
            self.figure_count += 1
        
        if anchor:
            # Insert anchor(s) for the figure
            self.insert_anchor('rfc.figure.' + str(self.figure_count))
            self.insert_anchor(anchor)
            if self.indexmode:
                # Add figure to the index, inserting any anchors necessary
                self._indexFigure(self.figure_count, anchor=anchor, title=title)

        # Write preamble
        preamble = figure.find('preamble')
        if preamble is not None:
            self.write_t_rec(preamble, align=figure_align)

        # iref
        for element in figure:
            if element.tag == 'iref':
                self._add_iref_to_index(element)

        # Write figure with optional delimiter
        delimiter = figure.pis['artworkdelimiter']
        artwork = figure.find('artwork')
        artwork_align = artwork.attrib.get('align', figure_align)
        blanklines = int(figure.pis['artworklines'])
        self.write_raw(artwork.text, align=artwork_align,
                       blanklines=blanklines, delimiter=delimiter,
                       source_line=figure.sourceline)

        # Write postamble
        postamble = figure.find('postamble')
        if postamble is not None:
            self.write_t_rec(postamble, align=figure_align)

        # Write label
        title = figure.attrib.get('title', '')
        if anchor or self.pis['figurecount'] == 'yes':
            if suppress_title == 'false':
                if title:
                    title = 'Figure ' + str(self.figure_count) + ': ' + title
                else:
                    title = 'Figure ' + str(self.figure_count)
        if title:
            self.write_label(title, type='figure', source_line=figure.sourceline)

    def write_table(self, table):
        """ Writes <texttable> elements """
        align = table.attrib.get('align', self.defaults['table_align'])
        anchor = table.attrib.get('anchor')
        title = table.attrib.get('title', self.defaults['table_title'])
        suppress_title = table.attrib.get('suppress-title', 'false')

        # Keep track of count if there is an anchor, or PI was enabled
        if anchor or self.pis['tablecount'] == 'yes':
            self.table_count += 1

        if anchor:
            # Insert anchor(s) for the table
            self.insert_anchor('rfc.table.' + str(self.table_count))
            self.insert_anchor(anchor)
            if self.indexmode:
                # Add table to the index, inserting any anchors necessary
                self._indexTable(self.table_count, anchor=anchor, title=title)

        # Write preamble
        preamble = table.find('preamble')
        if preamble is not None:
            self.write_t_rec(preamble, align=align)

        # Write table
        self.draw_table(table, table_num=self.table_count)

        # Write postamble
        postamble = table.find('postamble')
        if postamble is not None:
            self.write_t_rec(postamble, align=align)

        # Write label if anchor is set or PI figurecount = yes
        if anchor or self.pis['tablecount'] == 'yes':
            title = table.attrib.get('title', '')
            if suppress_title == 'false':
                if title:
                    title = 'Table ' + str(self.table_count) + ': ' + title
                else:
                    title = 'Table ' + str(self.table_count)
        if title:
            self.write_label(title, type='table', source_line=table.sourceline)

    def _index_t_rec(self, element):
        """ Traverse a <t> element only performing indexing operations """
        pass
        

    def numToAlpha(self, n):
        str = ""
        az = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        while n > 0:
            r = (n-1) % 26
            n = int((n-1)/26)
            str = az[r] + str
        return str

    def write_section_rec(self, section, count_str="1.", appendix=False,
                           level=0, numbered=True, emit_numbered="all", s_count=1):
        """ Recursively writes <section> elements 
        
            We use the self.indexmode flag to determine whether or not we
            render actual text at this point or just lookup header information
            to construct the index
        """
        if level > 0:
            anchor = section.attrib.get('anchor')
            title = section.attrib.get('title')
            include_toc = section.attrib.get('toc', self.defaults['section_toc']) != 'exclude' \
                          and (not appendix or self.pis['tocappendix'] == 'yes')
            if level == 1:
                numbered = numbered and self.is_numbered(section)
            else:
                numbered = self.is_numbered(section)
            if level > 1 and not numbered:
                if not self.indexmode:
                    xml2rfc.log.warn('Unnumbered subsections are not permitted: found section "%s" with attribute numbered="no" or "false"' % (title, ))
                numbered = True
            if self.indexmode:
                # Add section to the index
                self._indexSection(count_str, title=title, anchor=anchor,
                                   toc=include_toc, level=level,
                                   appendix=appendix, numbered=numbered)
            else:
                # Write the section heading
                if numbered:
                    autoAnchor = 'rfc.' + ('section.' if not appendix else 'appendix.') + count_str
                else:
                    autoAnchor = 'rfc.' + re.sub('[^A-Za-z0-9]+', '_', title).lower()
                bullet = appendix and level == 1 and 'Appendix %s' % count_str or count_str
                self.write_heading(title, bullet=bullet + '.' if numbered else "",
                                   autoAnchor=autoAnchor,
                                   anchor=anchor, level=level)
        else:
            # Must be <middle> or <back> element -- no title or index.
            count_str = ''
            numbered = True

        p_count = 1  # Paragraph counter
        for element in section:
            # Check for a PI
            if element.tag is etree.PI:
                pidict = self.parse_pi(element)
                if pidict and "needLines" in pidict:
                    self.needLines(pidict["needLines"])
            # Write elements in XML document order
            if element.tag == 't':
                anchor = element.attrib.get('anchor')
                if self.indexmode:
                    self._indexParagraph(count_str, p_count, anchor=anchor)
                autoAnchor = 'rfc.section.' + count_str + '.p.' + str(p_count)
                self.write_t_rec(element, autoAnchor=autoAnchor)
                p_count += 1
            elif element.tag == 'figure':
                self.write_figure(element)
            elif element.tag == 'texttable':
                self.write_table(element)
            elif element.tag == 'iref':
                self._add_iref_to_index(element)

        # Append a dot to separate sub counters
        if count_str:
            count_str += '.'

        # Recurse on sections
        for child_sec in section.findall('section'):
            if level == 0:
                if numbered:
                    numbered = self.is_numbered(child_sec)
                elif self.is_numbered(child_sec):
                    title = child_sec.attrib.get('title')
                    if not self.indexmode:
                        xml2rfc.log.warn('Numbered sections are not permitted after unnumbered sections: found section "%s" without attribute numbered="no"' % (title,))
                    numbered = False
                if emit_numbered=="only" and not numbered:
                    continue
                if emit_numbered=="no" and numbered:
                    continue
            if appendix == True and not count_str:
                if s_count == 1 and self.pis["rfcedstyle"] == "yes":
                   self.needLines(-1)
                # Use an alphabetic counter for first-level appendix
                self.write_section_rec(child_sec, self.numToAlpha(s_count),
                                        level=level + 1, appendix=True, numbered=numbered)
            else:
                # Use a numeric counter
                self.write_section_rec(child_sec, count_str + str(s_count), 
                                        level=level + 1, appendix=appendix, numbered=numbered)

            s_count += 1

        # Set the ending index number so we know where to begin references
        if count_str == '' and appendix == False:
            self.refs_start = s_count

        return s_count

    def write_status_section(self):
        """ Writes the 'Status of this Memo' section """

        self.write_heading('Status of This Memo', autoAnchor='rfc.status')
        if not self.draft:  #RFC
            # Status boilerplate is determined by category/submissionType/consensus
            category = self.r.attrib.get('category', 'none')
            stream = self.r.attrib.get('submissionType', 
                                       self.defaults['submissionType'])
            # Consensus is assumed 'yes' for Standards Track documents and BCPs
            consensus = category in ['std', 'bcp'] and 'yes' or \
                        self.r.attrib.get('consensus', self.defaults['consensus'])
            workgroup = ''
            wg_element = self.r.find('front/workgroup')
            if wg_element is not None and wg_element.text:
                workgroup = wg_element.text

            # Write first paragraph
            if category in self.boilerplate['status']:
                self.write_paragraph(self.boilerplate['status'][category].get('p1', ''))
            
            # Build second paragraph
            p2 = []
            if category in self.boilerplate['status']:
                p2.append(self.boilerplate['status'][category].get('p2', ''))
            if stream == 'IETF':
                if consensus == 'yes':
                    p2.append(self.boilerplate['status']['IETF_consensus'])
                else:
                    p2.append(self.boilerplate['status']['IETF'])
            elif stream == 'IRTF':
                p2.append(self.boilerplate['status']['IRTF'])
                if workgroup:
                    if consensus == 'yes':
                        p2.append(self.boilerplate['status']['IRTF_workgroup_consensus'] \
                                  % workgroup)
                    else:
                        p2.append(self.boilerplate['status']['IRTF_workgroup'] \
                                  % workgroup)
            elif stream == 'IAB':
                if consensus == 'yes':
                    p2.append(self.boilerplate['status']['IAB_consensus'])
                else:
                    p2.append(self.boilerplate['status']['IAB'])
            else:
                p2.append(self.boilerplate['status'].get(stream, ''))

            # Last sentence of p2
            if self.date < datetime.date(year=2016, month=6, day=1):
                status="status_5741"
            else:
                status="status"         # Current boilerplate
            if stream == 'IETF' and category == 'std':
                p2.append(self.boilerplate[status]['p2end_ietf_std'])
            elif stream == 'IETF' and category == 'bcp':
                p2.append(self.boilerplate[status]['p2end_ietf_bcp'])
            elif stream == 'IETF':
                p2.append(self.boilerplate[status]['p2end_ietf_other'])
            else:
                p2.append(self.boilerplate[status]['p2end_other'] \
                          % self.approvers.get(stream, ''))


            # Write second paragraph
            self.write_paragraph('  '.join(p2))
            
            # Write third paragraph
            key = 'p3' if self.date < self.boilerplate_https_date else 'p3_s'
            self.write_paragraph(self.boilerplate['status'][key] % self.rfcnumber)

        else:  # Draft
            # Start by checking for an ipr header
            ipr = self.r.attrib.get('ipr', self.defaults['ipr'])
            if '200902' in ipr:
                self.write_paragraph(self.boilerplate['ipr_200902_status'])
            elif '200811' in ipr:
                self.write_paragraph(self.boilerplate['ipr_200811_status'])

            # Write the standard draft status
            key = 'draft' if self.date < self.boilerplate_https_date else 'draft_s'
            for par in self.boilerplate['status'][key]:
                self.write_paragraph(par)

            # Write expiration string, if it was generated
            if self.expire_string:
                self.write_paragraph( \
                    self.boilerplate['draft_expire'] % self.expire_string)
    
    def write_copyright(self):
        """ Writes the 'Copyright' section """
        self.write_heading('Copyright Notice', autoAnchor='rfc.copyrightnotice')

        # Write header line with year
        date = self.r.find('front/date')
        year = ''
        if date is not None:
            year = date.attrib.get('year', self.date.year)
        self.write_paragraph(self.boilerplate['base_copyright_header'] % year)

        # Write next paragraph which may be modified by ipr
        ipr = self.r.attrib.get('ipr', self.defaults['ipr'])
        key = 'base_copyright_body' if self.date < self.boilerplate_https_date else 'base_copyright_body_s'
        body = self.boilerplate[key]
        if '200902' in ipr and self.r.attrib.get('submissionType', 
                                   self.defaults['submissionType']) == 'IETF':
            body += '  ' + self.boilerplate['ipr_200902_copyright_ietfbody']
        self.write_paragraph(body)
        
        # Write any additional paragraphs
        if 'noModification' in ipr:
            self.write_paragraph(self.boilerplate['ipr_noModification_copyright'])
        elif 'noDerivatives' in ipr:
            self.write_paragraph(self.boilerplate['ipr_noDerivatives_copyright'])
        elif ipr == 'pre5378Trust200902':
            self.write_paragraph(self.boilerplate['ipr_pre5378Trust200902_copyright'])

    def _build_index(self):
        self.indexmode = True
        # Reset document counters
        self.ref_start = 1              # Start of reference counters
        self.refs_start = 1             # Start of references sections
        self.figure_count = 0
        self.table_count = 0
        self.eref_count = 0
        self.pis = self.xmlrfc.getpis()

        # Abstract
        abstract = self.r.find('front/abstract')
        if abstract is not None:
            self.write_heading('Abstract', autoAnchor='rfc.abstract')
            for t in abstract.findall('t'):
                self.write_t_rec(t)

        # Authors
        count = 0
        authors = self.r.findall('front/author')
        for author in authors:
            count += 1
            autoName = full_author_name_expansion(author)
            self._indexAuthor(count, author.get('anchor'), autoName)

        # Optional notes
        for note in self.r.findall('front/note'):
            self.write_heading(note.attrib.get('title', 'Note'))
            for t in note.findall('t'):
                self.write_t_rec(t)

        # Middle sections
        middle = self.r.find('middle')
        if middle is not None:
            self.write_section_rec(middle, None)

        # References sections
        # Treat references as nested only if there is more than one
        ref_counter = 0
        refs_counter = str(self.refs_start)
        references = self.r.findall('back/references')
        # Write root level references header
        refs_title = self.pis['refparent']
        if len(references) == 1 and not self.eref_list:
            refs_title = references[0].attrib.get('title', refs_title)

        if len(references) > 0:
            self._indexReferences(refs_counter, title=refs_title)

        if len(references) > 1 or self.eref_list:
            for i, reference_list in enumerate(references):
                refs_newcounter = refs_counter + '.' + str(i + 1)
                refs_title = reference_list.attrib.get('title', self.pis["refparent"])
                self._indexReferences(refs_newcounter, title=refs_title, \
                                      subCounter=i+1, level=2)
            if self.eref_list:
                refs_newcounter = refs_counter + '.' + str(len(references)+1)
                self._indexReferences(refs_newcounter, title="URIs", level=2, subCounter=len(references)+1)


        for ref in self.r.xpath('.//references//reference'):
            if len(ref):
                ref_counter += 1
                title = ref.find("front/title")
                if title != None:
                    if 'anchor' in ref.attrib:
                        self._indexRef(ref_counter, title=title.text, anchor=ref.attrib["anchor"])
                    else:
                        raise RfcWriterError("Reference is missing an anchor: %s" % etree.tostring(ref))
                        
        # Appendix sections
        back = self.r.find('back')
        if back is not None:
            s_count = self.write_section_rec(back, None, appendix=True, emit_numbered="only")

        # Index section, disable if there are no irefs
        if len(self._iref_index) > 0:
            # Add explicitly to index
            title = 'Index'
            autoAnchor = 'rfc.index'
            item = _RfcItem(title, autoAnchor, title=title)
            self._index.append(item)

        if back is not None:
            self.write_section_rec(back, None, appendix=True, emit_numbered="no", s_count=s_count)

        # Authors addresses section

        if self.pis['authorship'] == 'yes':
            authors = self.r.findall('front/author')
            authors = [ a for a in authors if a.get('role') != 'contributor' ]
            autoAnchor = 'rfc.authors'
            if len(authors) > 1:
                title = "Authors' Addresses"
            else:
                title = "Author's Address"
            # Add explicitly to index
            item = _RfcItem(title, autoAnchor, title=title)
            self._index.append(item)

    def _build_document(self):
        self.indexmode = False
        # Reset document counters
        self.ref_start = 1              # Start of reference counters
        self.refs_start = 1             # Start of references sections
        self.figure_count = 0
        self.table_count = 0
        self.eref_count = 0
        self.pis = self.xmlrfc.getpis()

        # Block header
        topblock = self.pis['topblock']
        if topblock == 'yes':
            self.write_top(self._prepare_top_left(), \
                               self._prepare_top_right())

        # Title & Optional docname
        title = self.r.find('front/title')
        if title is not None:
            docName = self.r.attrib.get('docName', None)
            rfcnum = self.r.attrib.get('number', None)
            if (not docName or not docName.strip()) and not rfcnum:
                xml2rfc.log.warn("No (or empty) 'docName' attribute in the <rfc/> element -- can't insert draft name on first page.")
            if docName and '.' in docName:
                xml2rfc.log.warn("The 'docName' attribute of the <rfc/> element should not contain any filename extension: docName=\"draft-foo-bar-02\".")
            if docName and not rfcnum and not re.search(r'-\d\d$', docName):
                xml2rfc.log.warn("The 'docName' attribute of the <rfc/> element should have a revision number as the last component: docName=\"draft-foo-bar-02\".")
            self.write_title(title.text, docName, title.sourceline)

        # Abstract
        abstract = self.r.find('front/abstract')
        if abstract is not None:
            self.write_heading('Abstract', autoAnchor='rfc.abstract')
            for t in abstract.findall('t'):
                self.write_t_rec(t)

        # Optional notified boilerplate
        # Disabled. See issue #123, http://trac.tools.ietf.org/tools/xml2rfc/trac/ticket/123
        ## if self.pis['iprnotified'] == 'yes':
        ##    self.write_paragraph(BaseRfcWriter.boilerplate['iprnotified'])

        # Optional notes
        for note in self.r.findall('front/note'):
            self.write_heading(note.attrib.get('title', 'Note'))
            for t in note.findall('t'):
                self.write_t_rec(t)

        if not self.pis['private']:
            # Verify that 'ipr' attribute is valid before continuing
            self._validate_ipr()

            # "Status of this Memo" section
            self.write_status_section()

            # Copyright section
            self.write_copyright()

        # Insert the table of contents marker at this position
        toc_enabled = self.pis['toc']
        if toc_enabled == 'yes':
            self.insert_toc()

        # Middle sections
        middle = self.r.find('middle')
        if middle is not None:
            self.write_section_rec(middle, None)

        # References sections
        # Treat references as nested only if there is more than one
        refs_counter = str(self.refs_start)
        references = self.r.findall('back/references')
        # Write root level references header
        refs_title = self.pis['refparent']
        if len(references) == 1 and not self.eref_list:
            refs_title = references[0].attrib.get('title', refs_title)

        if len(references) > 0 or self.eref_list:
            self.write_heading(refs_title, bullet=refs_counter + '.', \
                               autoAnchor='rfc.references')
        if len(references) > 1:
            for i, reference_list in enumerate(references):
                refs_newcounter = refs_counter + '.' + str(i + 1)
                refs_title = reference_list.attrib.get('title', self.pis['refparent'])
                autoAnchor = 'rfc.references.' + str(i + 1)
                self.write_heading(refs_title, bullet=refs_newcounter + '.',\
                                   autoAnchor=autoAnchor, level=2)
                self.write_reference_list(reference_list)
        elif len(references) == 1:
            if self.eref_list:
                refs_newcounter = refs_counter + '.1'
                refs_title = references[0].attrib.get('title', self.pis['refparent'])
                autoAnchor = 'rfc.references.1'
                self.write_heading(refs_title, bullet=refs_newcounter + '.',\
                                   autoAnchor=autoAnchor, level=2)
            self.write_reference_list(references[0])

        if self.eref_list:
            self.write_erefs(refs_counter, len(references)+1)

        # Appendix sections
        back = self.r.find('back')
        if back is not None:
            s_count = self.write_section_rec(back, None, appendix=True, emit_numbered="only")

        # Index section, disable if there are no irefs
        if len(self._iref_index) > 0:
            self.insert_iref_index()

        if back is not None:
            self.write_section_rec(back, None, appendix=True, emit_numbered="no", s_count=s_count)

        self.write_crefs()

        # Authors addresses section
        if self.pis['authorship'] == 'yes':
            authors = self.r.findall('front/author')
            authors = [ a for a in authors if a.get('role') != 'contributor' ]
            autoAnchor = 'rfc.authors'
            if len(authors) > 1:
                title = "Authors' Addresses"
            else:
                title = "Author's Address"
            self.write_heading(title, autoAnchor=autoAnchor)
            for author in authors:
                self.write_address_card(author)

        self.check_for_unused_references()
        
    def write(self, filename, tmpfile=None):
        """ Public method to write the RFC document to a file. """
        # If the ascii flag is enabled, replace unicode with ascii in the tree
        if self.ascii:
            xml2rfc.utils.safeReplaceUnicode(self.r)

        # Protect any words with slashes that are on the preserve list
        xml2rfc.utils.safeTagSlashedWords(self.r)

        # Do any pre processing necessary, such as inserting metadata
        self.pre_indexing()
        # Make two passes over the document, the first pass we run in
        # 'index mode' to construct the internal index and other things, 
        # the second pass will assemble a buffer and render the actual text
        self._build_index()
        # Format the date properly
        self._format_date()
        # Do any pre-build processing necessary, such as inserting metadata
        self.pre_rendering()
        # Build the document
        self._build_document()
        # Primary buffer is finished -- apply any post processing
        self.post_rendering()

        # Finished processing, write to file
        # Override file with keyword argument if passed in, ignoring filename.
        # Warning -- make sure file is open and ready for writing!
        if not tmpfile:
            if self.ascii:
                file = open(filename, 'w')
            else:
                # Open as unicode
                file = codecs.open(filename, 'w', encoding='utf-8')
            self.write_to_file(file)
            file.close()
        else:
            self.write_to_file(tmpfile)

        if not self.options.quiet and filename:
            xml2rfc.log.write(' Created file', filename)

    def write_erefs(self, refs_counter, refs_subsection):
        """ Only text versions do this so provide a default that does nothing
        """
        pass

    def write_crefs(self):
        """ Only text versions do this so provide a default that does nothing
        """
        pass

    def check_for_unused_references(self):
        """ If this is a reference and it is not used - then warn me
        """
        if not self.indexmode:
            for item in self._index:
                if item.autoAnchor.startswith("rfc.ref.") and not item.used:
                    xml2rfc.log.warn("No <xref> in <rfc> targets <reference anchor='%s'>" % item.anchor)

    def needLines(self, count):
        """ Deal with the needLines PI """
        pass
                
    # -----------------------------------------
    # Base writer interface methods to override
    # -----------------------------------------

    def insert_toc(self):
        """ Marks the current buffer position to insert ToC at """
        raise NotImplementedError('insert_toc() needs to be overridden')
    
    def insert_iref_index(self):
        """ Marks the current buffer position to insert the index at """
        raise NotImplementedError('insert_iref_index() needs to be '
                                  'overridden')

    def write_raw(self, text, indent=3, align='left', blanklines=0,
                  delimiter=None, source_line=None):
        """ Writes a block of text that preserves all whitespace """
        raise NotImplementedError('write_raw() needs to be overridden')

    def write_label(self, text, type='figure', source_line=None):
        """ Writes a table or figure label """
        raise NotImplementedError('write_label() needs to be overridden')

    def write_title(self, title, docName=None, source_line=None):
        """ Writes the document title """
        raise NotImplementedError('write_title() needs to be overridden')

    def write_heading(self, text, bullet='', autoAnchor=None, anchor=None,
                      level=1, breakNeed=0):
        """ Writes a section heading """
        raise NotImplementedError('write_heading() needs to be overridden')

    def write_paragraph(self, text, align='left', autoAnchor=None):
        """ Writes a paragraph of text """
        raise NotImplementedError('write_paragraph() needs to be overridden')

    def write_t_rec(self, t, align='left', autoAnchor=None):
        """ Recursively writes <t> elements """
        raise NotImplementedError('write_t_rec() needs to be overridden')

    def write_top(self, left_header, right_header):
        """ Writes the main document header

            Takes two list arguments, one for each margin, and combines them
            so that they exist on the same lines of text
        """
        raise NotImplementedError('write_top() needs to be overridden')

    def write_address_card(self, author):
        """ Writes the address information for an <author> element """
        raise NotImplementedError('write_address_card() needs to be ' \
                                  'overridden')

    def write_reference_list(self, list):
        """ Writes a <references> element """
        raise NotImplementedError('write_reference_list() needs to be ' \
                                  'overridden')

    def insert_anchor(self, text):
        """ Inserts a document anchor for internal links """
        raise NotImplementedError('insert_anchor() needs to be overridden')

    def draw_table(self, table, table_num=None):
        """ Draws a formatted table from a <texttable> element

            For HTML nothing is really 'drawn' since we can use <table>
        """
        raise NotImplementedError('draw_table() needs to be overridden')

    def pre_indexing(self):
        """ First method that is called before traversing the XML RFC tree for indexing"""
        raise NotImplementedError('pre_indexing() needs to be overridden')

    def pre_rendering(self):
        """ First method that is called before traversing the XML RFC tree for rendering"""
        raise NotImplementedError('pre_rendering() needs to be overridden')

    def post_rendering(self):
        """ Last method that is called after traversing the XML RFC tree """
        raise NotImplementedError('post_rendering() needs to be overridden')

    def write_to_file(self, file):
        """ Writes the finished buffer to a file """
        raise NotImplementedError('write_to_file() needs to be overridden')

# --------------------------------------------------------------------------------------------------
# Sets of various kinds of tags in the v3 schema
        
deprecated_element_tags = set([
    'c',
    'facsimile',
    'format',
    'list',
    'postamble',
    'preamble',
    'relref',
    'spanx',
    'texttable',
    'ttcol',
    'vspace',
])

deprecated_attributes = [
    # element, attribute
    ('artwork', 'height'),
    ('artwork', 'width'),
    ('artwork', 'xml:space'),
    ('figure', 'align'),
    ('figure', 'alt'),
    ('figure', 'height'),
    ('figure', 'src'),
    ('figure', 'suppress-title'),
    ('figure', 'title'),
    ('figure', 'width'),
    ('note', 'title'),
    ('references', 'title'),
    ('section', 'title'),
    ('seriesInfo', 'status'),
    ('seriesInfo', 'stream'),
    ('t', 'hangText'),
    ('texttable', 'title'),
    ('xref', 'pageno'),
]


v3_rnc_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'v3.rnc')
v3_rng_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'v3.rng')
v3_schema = etree.ElementTree(file=v3_rng_file)

def get_element_tags():
    tags = set()
    elements = v3_schema.xpath("/x:grammar/x:define/x:element", namespaces=namespaces)
    for element in elements:
        name = element.get('name')
        if not name in tags:
            tags.add(name)
    return tags

def get_meta_tags():
    "Get tags that can have text content but don't occur in regular text"
    tags = set()
    for elem in ['author', 'address', 'front', 'postal', 'reference' ]:
        refs = v3_schema.xpath("/x:grammar/x:define[@name='%s']//x:ref"%elem, namespaces=namespaces)
        for r in refs:
            name = r.get('name')
            if not name in tags:
                tags.add(name)
    return tags

def get_text_tags():
    "Get tags that can have text content from the schema"
    tags = set()
    texts = v3_schema.xpath("/x:grammar/x:define/x:element//x:text", namespaces=namespaces)
    for t in texts:
        element = list(t.iterancestors('{*}element'))[0]
        name = element.get('name')
        if not name in tags:
            tags.add(name)
    return tags

def get_text_or_block_tags():
    "Get tags that can have either text or block contents from the schema"
    tags = set()
    texts = v3_schema.xpath("/x:grammar/x:define/x:element/x:choice/*/x:choice//x:text", namespaces=namespaces)
    for t in texts:
        element = list(t.iterancestors('{*}element'))[0]
        name = element.get('name')
        if not name in tags:
            tags.add(name)
    return tags

def get_inline_tags():
    "Get tags that can occur within text from the schema"
    tags = set()
    referenced = v3_schema.xpath("/x:grammar/x:define/x:element//x:ref", namespaces=namespaces)
    for ref in referenced:
        name = ref.get('name')
        if not name in tags:
            p = ref.getparent()
            text = p.find('x:text', namespaces=namespaces)
            if text != None:
                tags.add(name)
    return tags

def get_xref_tags():
    "Get tags that can occur as direct children of <xref>"
    tags = set()
    refs = v3_schema.xpath("/x:grammar/x:define/x:element[@name='xref']//x:ref", namespaces=namespaces)
    tags = set([ c.get('name') for c in refs ])
    return tags


element_tags= get_element_tags()
meta_tags   = get_meta_tags() - deprecated_element_tags
text_tags   = get_text_tags() - deprecated_element_tags
all_inline_tags = get_inline_tags()
inline_tags = all_inline_tags - deprecated_element_tags
block_tags  = element_tags - inline_tags - deprecated_element_tags - set(['t'])
mixed_tags  = get_text_or_block_tags() - deprecated_element_tags
xref_tags   = get_xref_tags()

# --------------------------------------------------------------------------------------------------

class BaseV3Writer(object):

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None):
        self.xmlrfc = xmlrfc
        self.tree = xmlrfc.tree if xmlrfc else None
        self.root = self.tree.getroot() if xmlrfc else None
        self.options = options
        self.date = date if date is not None else datetime.date.today()
        self.v3_rnc_file = v3_rnc_file
        self.v3_rng_file = v3_rng_file
        self.v3_rng = etree.RelaxNG(file=self.v3_rng_file)
        self.v3_schema = v3_schema
        self.schema = v3_schema
        self.index_items = []
        self.meta_tags = set(meta_tags)
        self.text_tags = set(text_tags)
        self.inline_tags = set(inline_tags)
        self.mixed_tags = set(mixed_tags)
        self.xref_tags = set(xref_tags)
        self.attribute_defaults = self.get_all_attribute_defaults()
        #
        #
        self.errors = []
#         if options.debug:
#             found_handlers = []
#             missing_handlers = []
#             for tag in (self.get_element_tags() - deprecated_element_tags):
#                 func_name = "render_%s" % (tag.lower(),)
#                 if getattr(self, func_name, False):
#                     found_handlers.append(func_name)
#                 else:
#                     missing_handlers.append(func_name)
#             debug.pprint('found_handlers')
#             debug.show('len(found_handlers)')
#             debug.pprint('missing_handlers')
#             debug.show('len(missing_handlers)')

    def log(self, msg):
        xml2rfc.log.write(msg)

    def msg(self, e, label, text):
        if e != None:
            lnum = getattr(e, 'sourceline', None)
            file = getattr(e, 'base', None)
            if lnum:
                msg = "%s(%s): %s %s" % (file or self.xmlrfc.source, lnum, label, text, )
            else:
                msg = "(No source line available): %s %s" % (label, text, )
        else:
            msg = "%s %s" % (label, text)
        return msg

    def get_relevant_pis(self, e):
        pis = []
        if e != None:
            # directly inside element
            for c in e.getchildren():
                if c.tag == etree.PI and c.target == xml2rfc.V3_PI_TARGET:
                    pis.append(c)
            # siblings before element
            for s in e.itersiblings(preceding=True):
                if s.tag == etree.PI and s.target == xml2rfc.V3_PI_TARGET:
                    pis.append(s)
            # ancestor's earlier siblings
            for a in e.iterancestors():
                for s in a.itersiblings(preceding=True):
                    if s.tag == etree.PI and s.target == xml2rfc.V3_PI_TARGET:
                        pis.append(s)
            # before root elements
            p = self.root.getprevious()
            while p != None:
                if p.tag == etree.PI and p.target == xml2rfc.V3_PI_TARGET:
                    pis.append(p)
                p = p.getprevious()
        return pis

    def get_relevant_pi(self, e, name):
        pis = self.get_relevant_pis(e)
        pi_list = list(filter(None, [ pi.get(name) for pi in pis ]))
        return pi_list[0] if pi_list else None

    def silenced(self, e, text):
        text = text.strip()
        pis = self.get_relevant_pis(e)
        silenced = filter(None, self.options.silence[:] + [ pi.get('silence') for pi in pis ])
        for s in silenced:
            for label in ['Note: ', 'Warning: ']:
                if s.startswith(label):
                    s = s[len(label):]
            if text.startswith(s):
                return True
            try:
                if re.match(s, text):
                    return True
            except re.error:
                pass
        return False

    def note(self, e, text, label='Note:'):
        if self.options.verbose:
            if not self.silenced(e, text):
                self.log(self.msg(e, label, text))

    def warn(self, e, text, label='Warning:'):
        if self.options.verbose or not (self.silenced(e, text) or self.options.quiet):
            self.log(self.msg(e, label, text))

    def err(self, e, text, trace=False):
        msg = self.msg(e, 'Error:', text)
        self.errors.append(msg)
        if trace or self.options.debug:
            raise RuntimeError(msg)
        else:
            self.log(msg)

    def die(self, e, text, trace=False):
        msg = self.msg(e, 'Error:', text)
        self.errors.append(msg)
        raise RfcWriterError(msg)

    def xinclude(self):
        ## From RFC7998:
        ##
        # 5.1.1.  XInclude Processing
        # 
        #    Process all <x:include> elements.  Note: XML <x:include> elements may
        #    include more <x:include> elements (with relative references resolved
        #    against the base URI potentially modified by a previously inserted
        #    xml:base attribute).  The tool may be configurable with a limit on
        #    the depth of recursion.
        try:
            self.check_includes()
            self.tree.xinclude()
        except etree.XIncludeError as e:
            self.die(None, "XInclude processing failed: %s" % e)

    def check_includes(self):
        # Check for <xi:include> elements with local filesystem references
        ns = {'xi':   b'http://www.w3.org/2001/XInclude'}
        xincludes = self.root.xpath('//xi:include', namespaces=ns)
        for xinclude in xincludes:
            href = urlparse(xinclude.get('href'))
            if not href.netloc or href.scheme == 'file':
                try:
                    can_access(self.options, self.xmlrfc.source, href.path)
                except FileAccessError as error:
                    self.die(None, error)

    def remove_dtd(self):
        # 
        # 5.1.2.  DTD Removal
        # 
        #    Fully process any Document Type Definitions (DTDs) in the input
        #    document, then remove the DTD.  At a minimum, this entails processing
        #    the entity references and includes for external files.

        ## Entities has been resolved as part of the initial parsing.  Remove
        ## docinfo and PIs outside the <rfc/> element by copying the root
        ## element and creating a new tree.
        root = copy.deepcopy(self.root)
        self.tree = root.getroottree()
        self.root = root

    def get_refname_mapping(self):
        reflist = self.root.xpath('.//references/reference|.//references/referencegroup')
        if self.root.get('symRefs', 'true') == 'true':
            refname_mapping = dict( (e.get('anchor'), e.get('anchor')) for e in reflist )
        else:
            refname_mapping = (dict( (e.get('anchor'), str(i+1)) for i,e in enumerate(reflist) ))
        refname_mapping.update(dict( (e.get('target'), e.get('to')) for e in self.root.xpath('.//displayreference') ))
        return refname_mapping

    def dispatch(self, selectors):
        """
        Process selectors, extracting an XPath selector and generating a method name
        from each entry in self.selectors, and calling the method with all elements
        matching the XPath expression, in order to process self.tree.
        """
        # Setup
        selector_visits = dict( (s, 0) for s in selectors)
        # Check for duplicate <displayreference> 'to' values:
        seen = {}
        for e in self.root.xpath('.//displayreference'):
            to = e.get('to')
            if to in set(seen.keys()):
                self.die(e, 'Found duplicate displayreference value: "%s" has already been used in %s' % (to, etree.tostring(seen[to]).strip()))
            else:
                seen[to] = e
        del seen
        ## Do remaining processing by xpath selectors (listed above)
        for s in selectors:
            slug = slugify(s.replace('self::', '').replace(' or ','_').replace(';','_'))
            if '@' in s:
                func_name = 'attribute_%s' % slug
            elif "()" in s:
                func_name = slug
            else:
                if not slug:
                    slug = 'rfc'
                func_name = 'element_%s' % slug
            # get rid of selector annotation
            ss = s.split(';')[0]
            func = getattr(self, func_name, None)
            if func:
                if self.options.debug:
                    self.note(None, "Calling %s()" % func_name)
                for e in self.tree.xpath(ss):
                    func(e, e.getparent())
                    selector_visits[s] += 1
            else:
                self.warn(None, "No handler %s() found" % (func_name, ))
        if self.options.debug:
            for s in selectors:
                if selector_visits[s] == 0:
                    self.note(None, "Selector '%s' has not matched" % (s))
        if self.errors:
            raise RfcWriterError("Not creating output file due to errors (see above)")
        return self.tree

    def get_all_attribute_defaults(self):
        defaults = {}
        elements = self.schema.xpath("/x:grammar/x:define/x:element", namespaces=namespaces)
        for tag in [ e.get('name') for e in elements ]:
            attr = self.schema.xpath("/x:grammar/x:define/x:element[@name='%s']//x:attribute" % tag, namespaces=namespaces)
            defaults[tag] = dict( (a.get('name'), a.get("{%s}defaultValue"%namespaces['a'], None)) for a in attr )
        return defaults

    def check_refs_numbered(self):
        # see if references should be numbered.  This is True unless the last
        # top-level section of <middle/> had numbered='false'.
        if not hasattr(self, '_refs_numbered'):
            last_middle_section = ([None, ] + list(self.root.find('middle').iterchildren('section')))[-1]
            self._refs_numbered = last_middle_section.get('numbered', 'true') == 'true'
        return self._refs_numbered

    # methods operating on the xml tree

    def get_element_from_id(self, id):
        for a in 'anchor', 'pn', 'slugifiedName':
            elem = self.root.find('.//*[@%s="%s"]'%(a, id, ))
            if elem != None:
                break
        return elem

    def get_element_page(self, e):
        page = getattr(e, 'page', None)
        if not page:
            for a in e.iterancestors():
                page = getattr(a, 'page', None)
                if page != None:
                    break
        return page

#     def get_valid_child_tags(self, tag):
#         refs = self.schema.xpath("/x:grammar/x:define/x:element[@name='%s']//x:ref" % tag, namespaces=utils.namespaces)
#         names = set([ r.get('name') for r in refs ])
#         return names

    def write(self, filename):
        raise NotImplementedError()

    # methods for use in setting up page headers and footers

    def page_top_left(self):
        if self.root.get('ipr') == 'none':
            return ''
        number = self.root.get('number')
        if number != None:
            return 'RFC %s' % number
        info = self.root.find('./front/seriesInfo[@name="RFC"]')
        if info != None:
            return 'RFC %s' % info.get('value')
        return 'Internet-Draft'

    def page_top_center(self):
        title = self.root.find('./front/title')
        text = title.get('abbrev') or ' '.join(title.itertext())
        if len(text) > 40:
            self.warn(title, "Expected a title or title abbreviation of not more than 40 character for the page header, found %s characters" % len(text))
        return text[:40]

    def full_page_top_center(self):
        title = self.root.find('./front/title')
        text = title.get('abbrev') or ' '.join(title.itertext())
        if len(text) > 80:
            self.note(title, "Found a title or title abbreviation of length %s; check that it fits the running page header." % len(text))
        return text

    def page_top_right(self):
        date = self.root.find('./front/date')
        year, month, day = extract_date(date, self.options.date)
        year, month, day = augment_date(year, month, day, self.options.date)
        text = format_date(year, month, None, legacy=True)
        return text

    def page_bottom_left(self):
        authors = self.root.findall('front/author')
        authors = [ a for a in authors if a.get('role') != 'contributor' ]
        surnames = [ n for n in [ short_author_ascii_name_parts(a)[1] for a in authors ] if n ]
        text = ''
        if len(surnames) == 1:
            text = surnames[0]
        elif len(surnames) == 2:
            text = '%s & %s' % (surnames[0], surnames[1])
        elif len(surnames) > 2:
            text = '%s, et al.' % surnames[0]
        return text

    def page_bottom_center(self):
        # Either expiry date or category
        if self.options.rfc or self.root.get('ipr') == 'none':
            cat = self.root.get('category')
            text = strings.category_name[cat]
        else:
            date = get_expiry_date(self.tree, self.options.date)
            parts = date.year, date.month, date.day
            text = 'Expires %s' % format_date(*parts, legacy=self.options.legacy_date_format)
        return text

    def pretty_print_prep(self, e, p):
        ind = self.options.indent
        ## The actual printing is done in self.write()
        def indent(e, i):
            if e.tag in (etree.CDATA, ):
                return
            if e.tag in (etree.Comment, etree.PI, ):
                if not e.tail:
                    if e.getnext() != None:
                        e.tail = '\n'+' '*i
                    else:
                        e.tail = '\n'+' '*(i-ind)
                return
            #
            if e.tag not in text_tags:
                if len(e) and (e.text is None or e.text.strip()==''):
                    e.text = '\n'+' '*(i+ind)
            elif e.tag in ['blockquote', 'li', 'dd', 'td', 'th' ]: # mixed content
                pass
                if len(e) and e[0] not in inline_tags and (e.text is None or e.text.strip()==''):
                    e.text = '\n'+' '*(i+ind)
            elif e.tag in ['artwork', 'sourcecode', ]:
                pass
            else:
                # inline tag
                if e.tail == '':
                    e.tail = None
                if len(e):
                    z = e[-1]
                    if z.tail and re.search(r'\n[ \t]+$', z.tail):
                        z.tail = re.sub(r'\n[ \t]+$', '\n'+' '*(i), z.tail)
                else:
                    if e.text and re.search(r'\n[ \t]+$', e.text):
                        e.text = re.sub(r'\n[ \t]+$', '\n'+' '*(i), e.text)

            for c in e:
                indent(c, i+ind)

            if e.tag not in all_inline_tags:
                if e.tail is None or e.tail.strip()=='':
                    if e.getnext() != None:
                        e.tail = '\n'+' '*i
                    else:
                        e.tail = '\n'+' '*(i-ind)
                elif not is_svg(e):
                    self.warn(e, 'Unexpected text content after block tag: <%s>%s' % (e.tag, e.tail))
            else:
                if e.tail != None and e.tail.strip()=='' and '\n' in e.tail:
                    if e.getnext() != None:
                        e.tail = '\n'+' '*i
                    else:
                        e.tail = '\n'+' '*(i-ind)
        indent(e, 0)
        e.tail = None

    def deadly_error(self, error):
        # errors that xml2rfc must not allow to continue

        if error.message in DEADLY_ERRORS:
            if self.options.verbose:
                msg = "%s(%s): Error: Can not continue further with error: %s" % (self.xmlrfc.source, error.line, error.message)
                self.log(msg)
            return True

    def validate(self, when='', warn=False):
        # Note: Our schema doesn't permit xi:include elements, so the document
        # must have had XInclude processing done before calling validate()

        # The lxml Relax NG validator checks that xsd:ID values are unique,
        # but unfortunately the error messages are completely unhelpful (lxml
        # 4.1.1, libxml 2.9.1): "Element li has extra content: t" when 't' has
        # a duplicate xsd:ID attribute.  So we check all attributes with
        # content specified as xsd:ID first, and give better messages:

        # Get the attributes we need to check
        if when and not when.startswith(' '):
            when = ' '+when
        dups = find_duplicate_ids(self.schema, self.tree)
        for attr, id, e in dups:
            self.warn(e, 'Duplicate xsd:ID attribute %s="%s" found.  This will cause validation failure.' % (attr, id, ))

        try:
            # Use a deepcopy to avoid any memory issues.
            tree = copy.deepcopy(self.tree)
            self.v3_rng.assertValid(tree)
            return True
        except Exception as e:
            deadly = False
            if hasattr(e, 'error_log'):
                for error in e.error_log:
                    path = getattr(error, 'path', '')
                    msg = "%s(%s): %s: %s, at %s" % (self.xmlrfc.source, error.line, error.level_name.title(), error.message, path)
                    self.log(msg)
                    if not deadly:
                        deadly = self.deadly_error(error)
                    if error.message.startswith("Did not expect text"):
                        items = self.tree.xpath(error.path + '/text()')
                        for item in items:
                            item = item.strip()
                            if item:
                                nl = '' if len(item) < 60 else '\n  '
                                self.log('  Unexpected text:%s "%s"' % (nl, item))

            else:
                log.warn('\nInvalid document: %s' % (e,))
            if warn and not deadly:
                self.warn(self.root, 'Invalid document%s.' % (when, ))
                return False
            else:
                self.die(self.root, 'Invalid document%s.' % (when, ))

    def validate_before(self, e, p):
        version = self.root.get('version', '3')
        if version not in ['3', ]:
            self.die(self.root, 'Expected <rfc> version="3", but found "%s"' % version)
        if not self.validate('before'):
            self.note(None, "Schema validation failed for input document")

        self.validate_draft_name()

    def validate_draft_name(self):
        if not self.root.attrib.get('number', False):
            docName = self.root.attrib.get('docName', None)
            info = self.root.find('./front/seriesInfo[@name="Internet-Draft"]')
            si_draft_name = info.get('value') if info != None else None

            if all([docName, si_draft_name]) and docName != si_draft_name:
                self.die(self.root, 'docName and value in <seriesInfo name="Internet-Draft" ..> must match.')

        return True

    def validate_after(self, e, p):
        # XXX: There is an issue with exponential increase in validation time
        # as a function of the number of attributes on the root element, on
        # the order of minutes for the full set of possible attribute values.
        # See https://bugzilla.gnome.org/show_bug.cgi?id=133736 .  In our
        # schema, there is no dependency in the underlying schema on the root
        # element attributes.  In order to avoid very long validation times, we
        # strip the root attributes before validation, and put them back
        # afterwards.
        attrib = copy.deepcopy(e.attrib)
        e.attrib.clear()
        #
        if not self.validate('after', warn=True):
            self.note(None, "Schema validation failed for input document")
        else:
            self.root.set('version', '3')
        #
        keys = list(attrib.keys())
        keys.sort()
        e.attrib.update(attrib)

    def remove(self, p, e):
        # Element.remove(child) removes both the child and its tail, so in
        # order not to loose text when removing comments or other elements,
        # we need to handle that case:
        if e.tail:
            s = e.getprevious()
            if s != None:
                s.tail = (s.tail or '') + e.tail
            else:
                p.text = (p.text or '') + e.tail
        p.remove(e)

    @staticmethod
    def split_pn(pn):
        """Split a pn into meaningful parts

        Returns a tuple (element_type, section_number, paragraph_number).
        If there is no paragraph number, it will be None.
        """
        parts = pn.split('-', 2)
        elt_type = parts[0]
        sect_num = parts[1]
        paragraph_num = parts[2] if len(parts) > 2 else None

        # see if section num needs special handling
        components = sect_num.split('.', 1)
        if components[0] in ['appendix', 'boilerplate', 'note', 'toc']:
            sect_num = components[1]  # these always have a second component
        return elt_type, sect_num, paragraph_num

    @staticmethod
    def level_of_section_num(num):
        """Determine hierarchy level of a section number

        Top level items have level 1. N.B., num is a string.
        """
        num_with_no_trailing_dot = num.rstrip('.')
        components = num_with_no_trailing_dot.split('.')
        if any([len(cpt) == 0 for cpt in components]):
            log.warn('Empty section number component in "{}"'.format(num))
        return len(components)

    @classmethod
    def is_top_level_section(cls, num):
        return cls.level_of_section_num(num) == 1

    appendix_pn_re = re.compile(r'^section-[a-z]\.|^section-appendix\.')
    @classmethod
    def is_appendix(cls, pn):
        """Is a section with this number an appendix?"""
        return cls.appendix_pn_re.match(pn) is not None
