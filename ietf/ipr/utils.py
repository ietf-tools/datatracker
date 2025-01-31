# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from textwrap import dedent

from ietf.ipr.mail import process_response_email, UndeliverableIprResponseError

import debug                            # pyflakes:ignore

def get_genitive(name):
    """Return the genitive form of name"""
    return name + "'" if name.endswith('s') else name + "'s"

def get_ipr_summary(disclosure):
    """Return IPR related document names as a formatted string"""
    names = []
    for doc in disclosure.docs.all():
        if doc.name.startswith('rfc'):
            names.append('RFC {}'.format(doc.name[3:]))
        else:
            names.append(doc.name)
    
    if disclosure.other_designations:
        names.append(disclosure.other_designations)

    if not names:
        summary = ''
    elif len(names) == 1:
        summary = names[0]
    elif len(names) == 2:
        summary = " and ".join(names)
    elif len(names) > 2:
        summary = ", ".join(names[:-1]) + ", and " + names[-1]
    return summary if len(summary) <= 128 else summary[:125]+'...'


def iprs_from_docs(docs,**kwargs):
    """Returns a list of IPRs related to docs"""
    iprdocrels = []
    for document in docs:
        if document.ipr(**kwargs):
            iprdocrels += document.ipr(**kwargs)
    return list(set([i.disclosure for i in iprdocrels]))
    
def related_docs(doc, relationship=('replaces', 'obs'), reverse_relationship=("became_rfc",)):
    """Returns list of related documents"""

    results = [doc]

    rels = doc.all_relations_that_doc(relationship)

    for rel in rels:
        rel.target.related = rel
        rel.target.relation = rel.relationship.revname
    results += [x.target for x in rels]

    rev_rels = doc.all_relations_that(reverse_relationship)
    for rel in rev_rels:
        rel.source.related = rel
        rel.source.relation = rel.relationship.name
    results += [x.source for x in rev_rels]

    return list(set(results))


    
def ingest_response_email(message: bytes):
    from ietf.api.views import EmailIngestionError  # avoid circular import
    try:
        process_response_email(message)
    except UndeliverableIprResponseError:
        # Message was rejected due to some problem the sender can fix, so bounce but don't send
        # an email to the admins
        raise EmailIngestionError("IPR response rejected", email_body=None)
    except Exception as err:
        # Message was rejected due to an unhandled exception. This is likely something
        # the admins need to address, so send them a copy of the email.
        raise EmailIngestionError(
            "Datatracker IPR email ingestion error",
            email_body=dedent("""\
                An error occurred while ingesting IPR email into the Datatracker. The original message is attached.
                
                {error_summary}
                """),
            email_original_message=message,
            email_attach_traceback=True,
        ) from err
