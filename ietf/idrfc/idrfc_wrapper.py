# Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from ietf.idtracker.models import InternetDraft, Rfc, IDInternal, BallotInfo, IESGDiscuss, IESGComment, Position, IESGLogin
from ietf.idrfc.models import RfcIndex, RfcEditorQueue, DraftVersions
import re
from datetime import date, timedelta
from django.utils import simplejson
import types

BALLOT_ACTIVE_STATES = ['In Last Call',
                        'Waiting for Writeup',
                        'Waiting for AD Go-Ahead',
                        'IESG Evaluation',
                        'IESG Evaluation - Defer']

# A wrapper to make writing templates less painful
# Can represent either an Internet Draft, RFC, or combine both

class IdRfcWrapper:
    # avoid using these in templates
    draft = None
    idinternal = None
    rfc = None
    rfcIndex = None

    # Active, RFC, Expired, Replaced, etc.
    document_status = None
    draft_name = None
    draft_revision = None
    title = None
    rfc_number = None
    revision_date = None
    tracker_id = None
    rfc_maturity_level = None
    iesg_main_state = None
    iesg_state = None
    iesg_sub_state = None
    iesg_state_date = None
    
    # must give either draft or rfcIndex!
    def __init__(self, draft=None, rfc=None, rfcIndex=None, findRfc=False):
        if isinstance(draft, IDInternal):
            self.idinternal = draft
            self.draft = self.idinternal.draft
        elif draft:
            self.draft = draft
            if draft.idinternal:
                self.idinternal = draft.idinternal
        if findRfc:
            if self.draft and self.draft.rfc_number:
                try:
                    r = Rfc.objects.get(rfc_number=self.draft.rfc_number)
                    ri = RfcIndex.objects.get(rfc_number=self.draft.rfc_number)
                    self.rfc = r
                    self.rfcIndex = ri
                except Rfc.DoesNotExist:
                    pass
                except RfcIndex.DoesNotExist:
                    pass
            elif rfcIndex:
                try:
                    r = Rfc.objects.get(rfc_number=rfcIndex.rfc_number)
                    self.rfc = r
                except Rfc.DoesNotExist:
                    pass
    
        if rfcIndex:
            self.rfcIndex = rfcIndex
            if rfc:
                self.rfc = rfc
        self.init_basic_data()
        
    def __str__(self):
        return "IdRfcWrapper:"+self.debug_data()

    def init_basic_data(self):
        d = self.draft
        i = self.idinternal
        r = self.rfcIndex

        if r:
            self.document_status = "RFC"
        else:
            self.document_status = str(d.status)
        
        if d:
            self.draft_name = d.filename
            self.draft_revision = d.revision
            self.title = d.title
            self.revision_date = d.revision_date
            self.tracker_id = d.id_document_tag
            if d.rfc_number:
                self.rfc_number = d.rfc_number
            
        if i:
            self.iesg_main_state = str(i.cur_state)
            if i.cur_sub_state_id > 0:
                self.iesg_sub_state = str(i.cur_sub_state)
                self.iesg_state = self.iesg_main_state + "::" + self.iesg_sub_state
            else:
                self.iesg_sub_state = None
                self.iesg_state = self.iesg_main_state
            self.iesg_state_date = i.event_date

        if r:
            self.title = r.title
            self.revision_date = r.rfc_published_date
            self.rfc_number = r.rfc_number
            if not d:
                self.draft_name = r.draft
            self.rfc_maturity_level = r.current_status

        # Handle incorrect database entries
        if self.is_rfc() and not self.rfc_number:
            self.document_status = "Expired"
        # Handle missing data
        if self.is_rfc() and not self.rfc_maturity_level:
            self.rfc_maturity_level = "Unknown?"

    def is_rfc(self):
        return (self.document_status == "RFC")

    def in_iesg_tracker(self):
        return (self.idinternal != None)

    def ad_name(self):
        if self.idinternal:
            name = self.idinternal.token_name
            # Some old documents have token name as "Surname, Firstname";
            # newer ones have "Firstname Surname"
            m = re.match(r'^(\w+), (\w+)$', name)
            if m:
                return m.group(2)+" "+m.group(1)
            else:
                return name
        else:
            return None

    def draft_name_and_revision(self):
        if self.draft_name and self.draft_revision:
            return self.draft_name+"-"+self.draft_revision
        else:
            return None

    def rfc_editor_state(self):
        try:
            if self.draft:
                qs = self.draft.rfc_editor_queue_state
                return qs.state
        except RfcEditorQueue.DoesNotExist:
            pass
        return None

    def has_rfc_errata(self):
        return self.rfcIndex and (self.rfcIndex.has_errata > 0)

    def last_call_ends(self):
        if self.iesg_main_state == "In Last Call":
            return self.draft.lc_expiration_date
        else:
            return None
        
    def iesg_note(self):
        if self.idinternal and self.idinternal.note:
            n = self.idinternal.note
            # Hide unnecessary note of form "RFC 1234"
            if re.match("^RFC\s*\d+$", n):
                return None
            return n
        else:
            return None

    def iesg_ballot_approval_text(self):
        if self.has_iesg_ballot():
            return self.idinternal.ballot.approval_text
        else:
            return None
    def iesg_ballot_writeup(self):
        if self.has_iesg_ballot():
            return self.idinternal.ballot.ballot_writeup
        else:
            return None

    # TODO: Returning integers here isn't nice
    # 0=Unknown, 1=IETF, 2=IAB, 3=IRTF, 4=Independent
    def stream_id(self):
        if self.draft_name:
            if self.draft_name.startswith("draft-iab-"):
                return 2
            elif self.draft_name.startswith("draft-irtf-"):
                return 3
            elif self.idinternal:
                if self.idinternal.via_rfc_editor > 0:
                    return 4
                else:
                    return 1
        g = self.group_acronym()
        if g:
            return 1
        return 0

    # Ballot exists (may be old or active one)
    def has_iesg_ballot(self):
        try:
            if self.idinternal and self.idinternal.ballot.ballot_issued:
                return True
        except BallotInfo.DoesNotExist:
            pass
        return False

    # Ballot exists and balloting is ongoing
    def has_active_iesg_ballot(self):
        return self.idinternal and (self.iesg_main_state in BALLOT_ACTIVE_STATES) and self.has_iesg_ballot() and self.document_status == "Active"

    def iesg_ballot_id(self):
        if self.has_iesg_ballot():
            return self.idinternal.ballot_id
        else:
            return None

    # Don't call unless has_iesg_ballot() returns True
    def iesg_ballot_positions(self):
        return create_ballot_object(self.idinternal, self.has_active_iesg_ballot())

    def group_acronym(self):
        if self.draft and self.draft.group_id != 0 and self.draft.group != None and str(self.draft.group) != "none":
            return str(self.draft.group)
        else:
            if self.rfc and self.rfc.group_acronym and (self.rfc.group_acronym != 'none'):
                return str(self.rfc.group_acronym)
        return None
        
    def view_sort_group(self):
        if self.is_rfc():
            return 'RFC'
        elif self.document_status == "Active":
            return 'Active Internet-Draft'
        else:
            return 'Old Internet-Draft'
    def view_sort_key(self):
        if self.is_rfc():
            x = self.rfc_number
            y = self.debug_data()
            if self.draft:
                z = str(self.draft.status)
            return "2%04d" % self.rfc_number
        elif self.document_status == "Active":
            return "1"+self.draft_name
        else:
            return "3"+self.draft_name

    def friendly_state(self):
        if self.is_rfc():
            return "RFC - "+self.rfc_maturity_level
        elif self.document_status == "Active":
            if self.iesg_main_state and self.iesg_main_state != "Dead":
                return self.iesg_main_state
            else:
                return "I-D Exists"
        else:
            return self.document_status

    def draft_replaced_by(self):
        try:
            if self.draft and self.draft.replaced_by:
                return [self.draft.replaced_by.filename]
        except InternetDraft.DoesNotExist:
            pass
        return None
    def draft_replaces(self):
        if not self.draft:
            return None
        r = [str(r.filename) for r in self.draft.replaces_set.all()]
        if len(r) > 0:
            return r
        else:
            return None

    # TODO: return just a text string for now
    def rfc_obsoleted_by(self):
        if (not self.rfcIndex) or (not self.rfcIndex.obsoleted_by):
            return None
        else:
            return self.rfcIndex.obsoleted_by

    def rfc_updated_by(self):
        if (not self.rfcIndex) or (not self.rfcIndex.updated_by):
            return None
        else:
            return self.rfcIndex.updated_by

    def is_active_draft(self):
        return self.document_status == "Active"

    def file_types(self):
        if self.draft:
            return self.draft.file_type.split(",")
        else:
            # Not really correct, but the database doesn't
            # have this data for RFCs yet
            return [".txt"]
        
    def abstract(self):
        if self.draft:
            return self.draft.abstract
        else:
            return None

    def debug_data(self):
        s = ""
        if self.draft:
            s = s + "draft("+self.draft.filename+","+str(self.draft.id_document_tag)+","+str(self.draft.rfc_number)+")"
        if self.idinternal:
            s = s + ",idinternal()"
        if self.rfc:
            s = s + ",rfc("+str(self.rfc.rfc_number)+")"
        if self.rfcIndex:
            s = s + ",rfcIndex("+str(self.rfcIndex.rfc_number)+")"
        return s

    def to_json(self):
        result = {}
        for k in ['document_status', 'draft_name', 'draft_revision', 'title', 'rfc_number', 'revision_date', 'tracker_id', 'rfc_maturity_level', 'iesg_main_state', 'iesg_state', 'iesg_sub_state', 'iesg_state_date', 'is_rfc', 'in_iesg_tracker', 'ad_name', 'draft_name_and_revision','rfc_editor_state','has_rfc_errata','last_call_ends','iesg_note','iesg_ballot_approval_text', 'iesg_ballot_writeup', 'stream_id','has_iesg_ballot','has_active_iesg_ballot','iesg_ballot_id','group_acronym','friendly_state','file_types','debug_data','draft_replaced_by','draft_replaces']:
            if hasattr(self, k):
                v = getattr(self, k)
                if callable(v):
                    v = v()
                if v == None:
                    pass
                elif isinstance(v, (types.StringType, types.IntType, types.BooleanType, types.LongType, types.ListType)):
                    result[k] = v
                elif isinstance(v, date):
                    result[k] = str(v)
                else:
                    result[k] = 'Unknown type '+str(type(v))
        return simplejson.dumps(result, indent=2)
            
# def create_document_object(draft=None, rfc=None, rfcIndex=None, base=None):
#     if draft:
#         o['fileTypes'] = draft.file_type.split(",")
#         if draft.intended_status and str(draft.intended_status) != "None":
#             o['intendedStatus'] = str(draft.intended_status)
#         else:
#             o['intendedStatus'] = None
#
#     if idinternal:
#         o['stateChangeNoticeTo'] = idinternal.state_change_notice_to
#         if idinternal.returning_item > 0:
#             o['telechatReturningItem'] = True
#         if idinternal.telechat_date:
#             o['telechatDate'] = str(idinternal.telechat_date)
#             o['onTelechatAgenda'] = (idinternal.agenda > 0)
#
#     if rfc:
#         o['intendedStatus'] = None
#     if rfcIndex:
#         o['rfcUpdates'] = rfcIndex.updates
#         o['rfcObsoletes'] = rfcIndex.obsoletes
#         o['rfcAlso'] = rfcIndex.also
#         for k in ['rfcUpdates','rfcUpdatedBy','rfcObsoletes','rfcObsoletedBy','rfcAlso']:
#             if o[k]:
#                 o[k] = o[k].replace(",", ",  ")
#                 o[k] = re.sub("([A-Z])([0-9])", "\\1 \\2", o[k])
#     return o

class BallotWrapper:
    idinternal = None
    ballot = None
    ballot_active = False

    _positions = None

    position_values = ["Discuss", "Yes", "No Objection", "Abstain", "Recuse", "No Record"]

    def __init__(self, idinternal, ballot_active):
        self.idinternal = idinternal
        self.ballot = idinternal.ballot
        self.ballot_active = ballot_active

    def _init(self):
        try:
            ads = set()
        except NameError:
            # for Python 2.3 
            from sets import Set as set
            ads = set()

        positions = []
        for p in self.ballot.positions.all():
            po = create_position_object(self.ballot, p)
            #if not self.ballot_active:
            #    if 'is_old_ad' in po:
            #        del po['is_old_ad']
            ads.add(str(p.ad))
            positions.append(po)
        if self.ballot_active:
            for ad in IESGLogin.active_iesg():
                if str(ad) not in ads:
                    positions.append({"ad_name":str(ad), "position":"No Record"})
        self._positions = positions

    def position_list(self):
        if not self._positions:
            self._init()
        return self._positions

    def get(self, v):
        return [p for p in self.position_list() if p['position']==v]

    def get_discuss(self):
        return self.get("Discuss")
    def get_yes(self):
        return self.get("Yes")
    def get_no_objection(self):
        return self.get("No Objection")
    def get_abstain(self):
        return self.get("Abstain")
    def get_recuse(self):
        return self.get("Recuse")
    def get_no_record(self):
        return self.get("No Record")

    def get_texts(self):
        return [p for p in self.position_list() if ('has_text' in p) and p['has_text']]

def position_to_string(position):
    positions = {"yes":"Yes",
                 "noobj":"No Objection",
                 "discuss":"Discuss",
                 "abstain":"Abstain",
                 "recuse":"Recuse"}
    if not position:
        return "No Record"
    p = None
    for k,v in positions.iteritems():
        if position.__dict__[k] > 0:
            p = v
    if not p:
        p = "No Record"
    return p

def create_position_object(ballot, position):
    positions = {"yes":"Yes",
                 "noobj":"No Objection",
                 "discuss":"Discuss",
                 "abstain":"Abstain",
                 "recuse":"Recuse"}
    p = None
    for k,v in positions.iteritems():
        if position.__dict__[k] > 0:
            p = v
    if not p:
        p = "No Record"
    r = {"ad_name":str(position.ad), "position":p}
    if not position.ad.is_current_ad():
        r['is_old_ad'] = True
        
    was = [v for k,v in positions.iteritems() if position.__dict__[k] < 0]
    if len(was) > 0:
        r['old_positions'] = was

    try:
        comment = ballot.comments.get(ad=position.ad)
        if comment and comment.text: 
            r['has_text'] =  True
            r['comment_text'] = comment.text
            r['comment_date'] = comment.date
            r['comment_revision'] = str(comment.revision)
    except IESGComment.DoesNotExist:
        pass

    if p == "Discuss":
        try:
            discuss = ballot.discusses.get(ad=position.ad)
            if discuss.text:
                r['discuss_text'] = discuss.text
            else:
                r['discuss_text'] = '(empty)'
            r['discuss_revision'] = str(discuss.revision)
            r['discuss_date'] = discuss.date
        except IESGDiscuss.DoesNotExist:
            # this should never happen, but unfortunately it does
            # fill in something to keep other parts of the code happy
            r['discuss_text'] = "(error: discuss text not found)"
            r['discuss_revision'] = "00"
            r['discuss_date'] = date(2000, 1,1)
        r['has_text'] = True
    return r

