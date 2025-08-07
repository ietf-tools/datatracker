# Copyright The IETF Trust 2017,2021 All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

# The following text entries, derived from RFC 7841, were taken from
# https://www.rfc-editor.org/materials/status-memos.txt on 01 Feb 2018
# and updated to match https://www.iab.org/documents/headers-boilerplate/

boilerplate_rfc_status_of_memo = {
    'IETF': {
        'std': {
            'true' : ["""<t>
            This is an Internet Standards Track document.
            </t>""",

            """<t>
            This document is a product of the Internet Engineering Task Force
            (IETF).  It represents the consensus of the IETF community.  It has
            received public review and has been approved for publication by
            the Internet Engineering Steering Group (IESG).  Further
            information on Internet Standards is available in Section 2 of 
            RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'bcp': {
            'true' : [ """<t>
            This memo documents an Internet Best Current Practice.
            </t>""",

            """<t>
            This document is a product of the Internet Engineering Task Force
            (IETF).  It represents the consensus of the IETF community.  It has
            received public review and has been approved for publication by
            the Internet Engineering Steering Group (IESG).  Further information
            on BCPs is available in Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'exp': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation.
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This document is a product of the Internet Engineering
            Task Force (IETF).  It represents the consensus of the IETF community.
            It has received public review and has been approved for publication
            by the Internet Engineering Steering Group (IESG).  Not all documents
            approved by the IESG are candidates for any level of Internet
            Standard; see Section 2 of RFC 7841. 
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation.
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This document is a product of the Internet Engineering
            Task Force (IETF).  It has been approved for publication by the
            Internet Engineering Steering Group (IESG).  Not all documents
            approved by the IESG are candidates for any level of Internet
            Standard; see Section 2 of RFC 7841. 
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'historic': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Engineering
            Task Force (IETF).  It represents the consensus of the IETF community.
            It has received public review and has been approved for publication by
            the Internet Engineering Steering Group (IESG).  Not all documents
            approved by the IESG are candidates for any level of Internet
            Standard; see Section 2 of RFC 7841. 
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Engineering Task Force
            (IETF).  It has been approved for publication by the Internet
            Engineering Steering Group (IESG).  Not all documents approved by the
            IESG are candidates for any level of Internet Standard; see Section 2
            of RFC 7841. 
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'info': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.  
            </t>""",

            """<t>
            This document is a product of the Internet Engineering Task Force
            (IETF).  It represents the consensus of the IETF community.  It has
            received public review and has been approved for publication by the
            Internet Engineering Steering Group (IESG).  Not all documents
            approved by the IESG are candidates for any level of Internet
            Standard; see Section 2 of RFC 7841. 
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.  
            </t>""",

            """<t>
            This document is a product of the Internet Engineering Task Force
            (IETF).  It has been approved for publication by the Internet
            Engineering Steering Group (IESG).  Not all documents approved by the
            IESG are candidates for any level of Internet Standard; see Section 2
            of RFC 7841.   
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
    },
    'IAB': {
        'historic': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Architecture
            Board (IAB) and represents information that the IAB has deemed
            valuable to provide for permanent record.  It represents the consensus of the
            Internet Architecture Board (IAB).  Documents approved for
            publication by the IAB are not candidates for any level of Internet
            Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Architecture
            Board (IAB) and represents information that the IAB has deemed
            valuable to provide for permanent record.  Documents approved for
            publication by the IAB are not candidates for any level of Internet
            Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'info': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.  
            </t>""",

            """<t>
            This document is a product of the Internet Architecture Board
            (IAB) and represents information that the IAB has deemed valuable
            to provide for permanent record.  It represents the consensus of the Internet
            Architecture Board (IAB).  Documents approved for publication
            by the IAB are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.
            </t>""",

            """<t>
            This document is a product of the Internet Architecture Board
            (IAB) and represents information that the IAB has deemed valuable
            to provide for permanent record.  Documents approved for publication
            by the IAB are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
    },
    'IRTF': {
        'exp': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation. 
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This document is a product of the Internet Research
            Task Force (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the consensus of the
            {group_name} Research Group of the Internet Research Task Force
            (IRTF).  Documents approved for publication by the IRSG are not
            candidates for any level of Internet Standard; see Section 2 of RFC
            7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation.
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This document is a product of the Internet Research Task
            Force (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the individual
            opinion(s) of one or more members of the {group_name} Research Group
            of the Internet Research Task Force (IRTF).  Documents approved for
            publication by the IRSG are not candidates for any level of Internet
            Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'n/a': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation.
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This document is a product of the Internet Research
            Task Force (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  Documents approved for publication by the
            IRSG are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'historic': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Research Task Force
            (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the consensus of
            the {group_name} Research Group of the Internet Research Task Force (IRTF).
            Documents approved for publication by the IRSG are not candidates for
            any level of Internet Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet community.
            This document is a product of the Internet Research Task Force
            (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the individual opinion(s) of one or more
            members of the {group_name} Research Group of the Internet
            Research Task Force (IRTF).  Documents approved for
            publication by the IRSG are not candidates for
            any level of Internet Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'n/a': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This document is a product of the Internet Research
            Task Force (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  Documents approved for publication by the
            IRSG are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
        'info': {
            'true' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.  
            </t>""",

            """<t>
            This document is a product of the Internet Research Task Force
            (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the consensus of the {group_name}
            Research Group of the Internet Research Task Force (IRTF).
            Documents approved for publication by the IRSG are not
            candidates for any level of Internet Standard; see Section 2 of RFC
            7841.   
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.  
            </t>""",

            """<t>
            This document is a product of the Internet Research Task Force
            (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  This RFC represents the individual opinion(s) of one or more
            members of the {group_name} Research Group of the Internet
            Research Task Force (IRTF).  Documents approved for publication by the IRSG are not
            candidates for any level of Internet Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'n/a': [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.
            </t>""",

            """<t>
            This document is a product of the Internet Research Task Force
            (IRTF).  The IRTF publishes the results of Internet-related
            research and development activities.  These results might not be
            suitable for deployment.  Documents approved for publication by the
            IRSG are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
    },
    'independent': {
        'exp': {
            'n/a' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for examination, experimental implementation, and
            evaluation.
            </t>""",

            """<t>
            This document defines an Experimental Protocol for the Internet
            community.  This is a contribution to the RFC Series,
            independently of any other RFC stream.  The RFC Editor has chosen to publish this
            document at its discretion and makes no statement about its value
            for implementation or deployment.  Documents approved for publication
            by the RFC Editor are not candidates for any level of Internet
            Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            </t>""",
            ],
        },
        'historic': {
            'n/a' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for the historical record.
            </t>""",

            """<t>
            This document defines a Historic Document for the Internet
            community.  This is a contribution to the RFC Series, independently of any
            other RFC stream.  The RFC Editor has chosen to publish this
            document at its discretion and makes no statement about its value
            for implementation or deployment.  Documents approved for
            publication by the RFC Editor are not candidates for any level of
            Internet Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
            'false': [ """<t>
            </t>""",
            ],
        },
        'info': {
            'n/a' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.
            </t>""",

            """<t>
            This is a contribution to the RFC Series, independently of any
            other RFC stream.  The RFC Editor has chosen to publish this
            document at its discretion and makes no statement about its value
            for implementation or deployment.  Documents approved for
            publication by the RFC Editor are not candidates for any level of
            Internet Standard; see Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any
            errata, and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
    },
    'editorial': {
        'info': {
            'n/a' : [ """<t>
            This document is not an Internet Standards Track specification; it is
            published for informational purposes.
            </t>""",

            """<t>
            This document is a product of the RFC Series Policy Definition
            Process.  It represents the consensus of the RFC Series Working
            Group approved by the RFC Series Approval Board.  Such documents
            are not candidates for any level of Internet Standard; see
            Section 2 of RFC 7841.
            </t>""",

            """<t>
            Information about the current status of this document, any errata,
            and how to provide feedback on it may be obtained at
            <eref target="{scheme}://www.rfc-editor.org/info/rfc{rfc_number}" />.
            </t>""",
            ],
        },
    },
}
