# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import migrations

def get_email(person):
        e = person.email_set.filter(primary=True).first()
        if not e:
            e = person.email_set.filter(active=True).order_by("-time").first()
        return e

def add_group_community_lists(apps, schema_editor, group):
    DocAlias = apps.get_model("doc", "DocAlias")
    State = apps.get_model("doc", "State")
    CommunityList = apps.get_model("community", "CommunityList")
    SearchRule = apps.get_model("community", "SearchRule")

    active_state = State.objects.get(slug="active", type="draft")
    rfc_state = State.objects.get(slug="rfc", type="draft")

    draft_aliases = DocAlias.objects.filter(name__startswith="draft")

    clist = CommunityList.objects.create(group=group)
    SearchRule.objects.create(community_list=clist, rule_type="group", group=group, state=active_state)
    SearchRule.objects.create(community_list=clist, rule_type="group_rfc", group=group, state=rfc_state)
    r = SearchRule.objects.create(community_list=clist, rule_type="name_contains", text=r"^draft-[^-]+-%s-" % group.acronym, state=active_state)
    name_re = re.compile(r.text)
    r.name_contains_index = [ a.document_id for a in draft_aliases if name_re.match(a.name) ]

def addPrograms(apps, schema_editor):

    Group = apps.get_model('group','Group')
    Person = apps.get_model('person','Person')
    Email = apps.get_model('person','Email')

    for name,email in [ ('Francis Bond','bond@ieee.org'),
                        ('Christine Runnegar', 'runnegar@isoc.org'),
                        ('Sarmad Hussain', 'sarmad.hussain@icann.org'),
                      ]:
        if not Person.objects.filter(name=name).exists():
            p = Person.objects.create(name=name,ascii=name)
            p.email_set.create(address=email, primary=True, active=True)

    override_find_person = {
                            'Patrik Faltstrom' : 'paf@netnod.se',
                            'Yoshiro Yoneya' : 'yone@jprs.co.jp',
                           } 

    iab = Group.objects.get(acronym='iab')

    def build_group(acronym, name, description, lead, members, docs):

        if Group.objects.filter(acronym=acronym).exists():
            print "Warning - not creating %s: group already exists"%(acronym,)
            return

        g = Group.objects.create(acronym=acronym,
                                 name=name,
                                 state_id='active',
                                 type_id='program',
                                 parent = iab,
                                 description=description,
                            )

        add_group_community_lists(apps, schema_editor, g) 
        cl = g.communitylist_set.first()
        for doc in docs:
            cl.added_docs.add(doc)

        lead_person = Person.objects.get(name=lead)
        g.role_set.create(person=lead_person,name_id='lead',email=get_email(lead_person))
        for name in members:
            if name in override_find_person:
                p = Email.objects.get(address=override_find_person[name]).person
            else:
                p_qs = Person.objects.filter(name=name)
                if p_qs.count() == 0:
                    print "Warning: Couldn't find %s - not adding them to %s"%(name,g.acronym)
                    continue
                elif p_qs.count() > 1:
                    print "Warning: Found more than one %s - using the first one"%(name,)
                p = p_qs.first()
            g.role_set.create(person=p,name_id='member',email=get_email(p))

    build_group(acronym='stackevo',
                name='IP Stack Evolution',
                description="""
The IP Stack Evolution program covers various topics in the evolution of IPv4 and IPv6, the transport protocols running over IP, and the overall protocol stack architecture. The program addresses challenges that affect the stack in some way and where the IETF community requires architectural guidance, responding to community requests as well as actively monitoring work within IETF WGs which touch on relevant topics.

There is an observed trend of functionality moving “up the stack”: where the “waist” was once IP, now most applications run over TCP/IP, or even HTTP/TCP/IP; the stack has become increasingly ossified. This is in response both to reduced path transparency within the Internet — middleboxes that limit the protocols of the traffic that can pass through them — as well as insufficiently flexible interfaces for platform and application developers. The emergence of both new application requirements demanding more flexibility from the stack, especially at layer 4, as well as the increasing ubiquity of encryption to protect against pervasive surveillance, provides an opportunity to re-evaluate and reverse this trend.

This program aims to provide architectural guidance, and a point of coordination for work at the architectural level to improve the present situation of ossification in the Internet protocol stack. Where a working group relevant to a particular aspect of IP stack evolution exists, the program will facilitate cross-group and cross-area coordination. The program also produces documents on the IAB stream providing general guidance on and covering architectural aspects of stack evolution.

Current Active Work
-------------------

(1) Discussion of principles for making new protocols within the IP stack deployable, following in part on RFC 5218 “What Makes for a Successful Protocol”.

(2) Discussion of principles for the use of encapsulation at various layers within the protocol stack. UDP-based encapsulations are not only useful for evolution above the IP layer, but in many tunneling contexts as well. The probable commonalities among all these applications of encapsulation might be useful in simplifying their implementation, deployment, and use.

(3) Architectural guidance on the interoperability of protocol stacks for use in constrained devices, focusing on issues related to mutually incompatible interactions among application, transport, network, and link layer protocols.

Past Workshops, BoFs, etc.
--------------------------

The Program has organized several workshops, Birds of a Feather sessions, and proposed Research Groups on topics related to its areas of work:

* The IAB workshop on `Stack Evolution in a Middlebox`__ Internet (SEMI) in Zurich, January 2015. Read the Workshop Report, RFC 7663
* The `Substrate Protocol for User Datagrams`__ (SPUD) BoF at IETF 92 in Dallas, March 2015.
* The `Managing Radio Networks in an Encrypted World`__ (MaRNEW) Workshop in Atlanta, September 2015, together with GSMA.
* The Measurement and Analysis for Protocols (MAP) proposed Research Group has been meeting since IETF 93 in Prague (until IETF 94 in Yokohama as “How Ossified is the Protocol Stack?” (HOPS) proposed RG). Discussion is at <maprg@irtf.org>.

__ https://www.iab.org/activities/workshops/semi/
__ https://www.ietf.org/proceedings/92/spud.html
__ https://www.iab.org/activities/workshops/marnew/

Documents Published
-------------------

* `Technical Considerations for Internet Service Blocking and Filtering`__ (RFC 7754),

__ http://www.rfc-editor.org/rfc/rfc7754.txt

This program has itself evolved from the IP Evolution Program, which looked at general architectural issues in the evolution of IPv4 and IPv6 and the overall protocol stack architecture, and produced the following documents:

* `IAB Thoughts on IPv6 Network Address Translation`__ (RFC 5902)
* `Evolution of the IP Model`__ (RFC 6250)
* `Smart Objects Workshop Report`__ (RFC 6574)
* `Architectural Considerations of IP Anycast`__ (RFC 7094)
* `Report from the IAB Workshop on Internet Technology Adoption and Transition (ITAT)`__ (RFC 7305)

__ http://www.rfc-editor.org/rfc/rfc5902.txt
__ http://www.rfc-editor.org/rfc/rfc6250.txt
__ http://www.rfc-editor.org/rfc/rfc6574.txt
__ http://www.rfc-editor.org/rfc/rfc7094.txt
__ http://www.rfc-editor.org/rfc/rfc7305.txt

""",
                lead="Brian Trammell",
                members= ['Brian Trammell',
                           'Ralph Droms',
                           'Ted Hardie',
                           'Joe Hildebrand',
                           'Lee Howard',
                           'Erik Nordmark',
                           'Robert Sparks',
                           'Dave Thaler',
                           'Mary Barnes',
                           'Marc Blanchet',
                           'David L. Black',
                           'Spencer Dawkins',
                           'Lars Eggert',
                           'Aaron Falk',
                           'Janardhan Iyengar',
                           'Suresh Krishnan',
                           u'Mirja K\xfchlewind',
                           'Eliot Lear',
                           'Eric Rescorla',
                           'Natasha Rooney',
                           'Martin Stiemerling',
                           'Michael Welzl',
                          ],
                docs = [ 'draft-iab-protocol-transitions',
                         'rfc7754',
                       ],
               )

    build_group(acronym='rfcedprog',
                name='RFC Editor',
                description="""
The purpose of this program is to provide a focus for the IAB’s responsibility to manage the RFC Editor function, including the RSE.

The details of the RSE function, and the RSOC are document in RFC 6635.

The Program’s main focus is on:

* Oversight of the RFC Series
* Assisting the RSE in policy matters as needed
* Oversight of the RSE

The active membership of this program consists of the RFC Series Oversight Committee (RSOC), which is primarily charged with executing the IAB responsibility to oversee the RSE.

`Past RSOC members and chairs are listed here.`__

__ http://www.iab.org/activities/programs/rfc-editor-program/past-rsoc-members/

The `RSOC Proceedures are available online here.`__

__ http://www.iab.org/activities/programs/rfc-editor-program/rsoc-procedures/

Mailing lists
-------------

Public discussion: rsoc@ietf.org

Meeting Minutes
---------------

RSOC meeting minutes are `available to the public here`__.

__ https://www.iab.org/documents/rsocmins/

""",
                lead="Robert Sparks",
                members= ['Joe Hildebrand',
                           'Robert Sparks',
                           'Sarah Banks',
                           'Nevil Brownlee',
                           'Heather Flanagan',
                           'Joel M. Halpern',
                           'Tony Hansen',
                           'Robert M. Hinden',
                           'Ray Pelletier',
                           'Adam Roach',
                          ],
                docs = ['draft-iab-rfc5741bis',
                        'draft-iab-html-rfc',
                        'draft-iab-rfc-css',
                        'draft-iab-rfc-framework',
                        'draft-iab-rfc-nonascii',
                        'draft-iab-rfc-plaintext',
                        'draft-iab-rfc-use-of-pdf',
                        'draft-iab-rfcv3-preptool',
                        'draft-iab-svg-rfc',
                        'draft-iab-xml2rfc',
                        'draft-iab-styleguide',
                        'draft-iab-rfcformatreq',
                       ],
               )

    build_group(acronym='privsec',
                name='Privacy and Security',
                description="""
The IAB Privacy and Security Program is a successor to its previous Security and Privacy programs.  It provides a forum to develop, synthesize and promote security and privacy guidance within the Internet technical standards community.   While security and privacy have each been explicitly and implicitly considered during the design of Internet protocols, there are three major challenges which face the community:

* most Internet protocols are developed as building blocks and will be used in a variety of situations.  This means that the security and privacy protections each protocol provides may depend on adjacent protocols and substrates.  The resulting security and privacy protections depend, however, on the initial assumptions remaining true as adjacent systems change.  These assumptions and dependencies are commonly undocumented and may be ill-understood.
* many security approaches have presumed that attackers have resources on par with those available to those secure the system.  Pervasive monitoring, distributed networks of compromised machines, and the availability of cloud compute each challenge those assumptions.
* many systems breach the confidentiality of individuals’ communication or request more than the minimally appropriate data from that communication in order to simplify the delivery of services or meet other requirements.  When other design considerations contend with privacy considerations, privacy has historically lost.

This program seeks to consolidate, generalize, and expand understanding of Internet-scale system design considerations for privacy and security;  to raise broad awareness of the changing threat models and their impact on the properties of Internet protocols; and to champion the value of privacy to users of the Internet and, through that value, as a contributor to the network effect for the Internet.

Public comments can be sent to privsec-discuss@iab.org.


Volunteers should send a statement of interest to privsec-program@iab.org, specifying which focus area or areas are of interest.  

Areas of Focus
--------------

Confidentiality
===============

After helping develop initial text for the  IAB’s statement on Internet Confidentiality, the group described the threat models related to surveillance, published as RFC 7624.  The program is now working to describe the building blocks which may be used to mitigate pervasive surveillance and the impact of specific design patterns on information leakage.  It will also develop a systems engineering description of how to build a confidential application which flows across the open Internet.

Work products anticipated:

* Mitigations document
* One or more design pattern documents
* Systems engineering document

Trust
=====

The program’s work on trust is coordinated work with the relevant IETF and IRTF working groups.  Its first related work product, on cryptographic algorithm agility, was moved to the IETF for consideration as a best current practice and eventually published as BCP 201 (RFC 7696). The program is currently working on a document examining the current Web Trust model.  The program also plans to document  general considerations for managing protocol systems in which there are multiple sources of truth which may provide assurances related to identity, authorization, or repudiation.

Work products anticipated:

* Examination of the Web’s Trust model and implementation
* Considerations for designing protocols with multiple sources of truth.

""",
                lead='Ted Hardie',
                members=[
                         'Ted Hardie',
                         'Russ Housley',
                         'Martin Thomson',
                         'Brian Trammell',
                         'Suzanne Woolf',
                         'Mary Barnes',
                         'Richard Barnes',
                         'Alissa Cooper',
                         'Stephen Farrell',
                         'Joseph Lorenzo Hall',
                         'Christian Huitema',
                         'Eliot Lear',
                         'Xing Li',
                         'Lucy Lynch',
                         'Karen O\'Donoghue',
                         'Andrei Robachevsky',
                         'Christine Runnegar',
                         'Wendy Seltzer',
                         'Juan-Carlos Z\xfa\xf1iga',
                        ],
                docs = [ 'draft-iab-privsec-confidentiality-mitigations', ]
               )

    build_group(acronym='inip',
                name='Names and Identifiers',
                description="""
The Names and Identifiers Program covers various topics concerning naming and resolution. As RFC 6055 points out, the DNS is not the only way that naming and resolution happens. Identifiers — not just domain names, but all identifiers — and the resolution of them are important both to users and applications on the Internet. Further, as Internet infrastructure becomes more complex and ubiquitous, the need for powerful, flexible systems of identifiers gets more important. However, in many ways we’re limited by the success of the DNS: it’s used so widely and successfully, for so many things, that compatibility with it is essential, even as demands grow for namespace characteristics and protocol behavior that aren’t included in the DNS and may be fundamentally incompatible with it.

The IAB has worked on these issues before, but there are several things that have recently changed which make the topic worth revisiting. First, we’re pushing the limits of flexibility in the DNS in new ways: there are growing numbers of protocols and applications (some of them built outside the IETF) that are creating DNS-like naming systems, but that differ from naming rules, wire protocol, or operational restrictions implicit in DNS. We’ve particularly seen cases where these protocols and applications expect to be able to use “domain name slots” where domain names have traditionally appeared in protocols, and the potential for subtle incompatibilities among them provides an opportunity for various forms of surprising results, from unexpected comparison failures to name collisions. In addition, it may be that as a consequence of the vast expansion of the root zone, the intended hierarchical structure of the DNS namespace could be lost, which raises not only operational concerns but also architectural questions of what characteristics are necessary in naming systems for various uses.

At the same time as that is changing, pressures to provide facilities not previously imagined for the DNS (such as bidirectional aliasing, or better protection for privacy, or context information such as localization or administrative boundaries) require that naming systems for the internet will continue to evolve.

Beyond specific stresses provided by the practical need for compatibility with DNS and its limitations, there are questions about the implications of identifier resolution more widely. For example, various methods for treating different domain names as “the same” have implications for email addresses, and this might have implications for identifier use and comparison more generally, including for i18n. Perhaps more broadly yet, we see an impact on naming systems as we examine needs such as support for scaling in new environments (mobile, IoT) and new priorities such as supporting widespread encryption.

The program seeks to provide a useful framework for thinking about naming and resolution issues for the internet in general, and to deliver recommendations for future naming or resolution systems.

The scope of initial investigations is deliberately somewhat open, but could include:

(a) some basic terminology: what do we mean by “names,” “identifiers,” and “name resolution” in the internet? What attributes of naming systems and identifiers are important with regards to comparison, search, human accessibility, and other interactions?
(b) overview: where are naming protocols and infrastructure important to the work of the IETF (and perhaps elsewhere)? Where is the DNS being used (and perhaps stretched too far)? What other identifier systems are we coming up with, and how well are those efforts working? This area will include examination of some of the naming systems under development or in use elsewhere, such as NDN, as a way of informing our thinking.
(c) For protocols (inside the IETF or outside), what should protocol designers know about re-using existing naming systems or inventing their own? Are there guidelines we can usefully provide?

Mailing Lists
-------------

* Program List: inip@iab.org
* Public Discussion List: inip-discuss@iab.org

""", 
                lead='Suzanne Woolf',
                members=[
                         'Suzanne Woolf',
                         'Marc Blanchet',
                         'Ralph Droms',
                         'Ted Hardie',
                         'Joe Hildebrand',
                         'Erik Nordmark',
                         'Robert Sparks',
                         'Andrew Sullivan',
                         'Dave Thaler',
                         'Brian Trammell',
                         'Edward Lewis',
                         'Jon Peterson',
                         'Wendy Seltzer',
                         'Lixia Zhang',
                        ],
                docs = [ 'draft-lewis-domain-names', ],
               )

    build_group(acronym='i18n-program',
                name='Internationalization',
                description="""
Internationalization and Localization are two common aspects of user-facing systems which span locales.  Efforts in these two areas typically handle how to appropriately represent data in a specific context and how to carry it between contexts. This program currently focuses on a special case of this problem:  the set of systems which have no locale and how they interact with systems which rely on that context.  Work in this area involves complex tradeoffs along multiple dimensions, and there is rarely a single right answer.  Rather than attempting to force such an answer to emerge, the IAB will describe the problem, common patterns to analyse the trade-offs, and provide advice for managing specific instances of this issue.

This program will also maintain the IAB’s long term effort to maintain liaisons with relevant groups in this topic area. Among these are the Unicode Consortium, ICANN, and ISO/IEC JTC1 SC2.

Current work
------------

A number of Internet protocols and systems rely on matching a known item for operation; when these lack access to locale or the facilities to process locale, they may fail or produce surprising results in the presence of multiple character composition methods. User names, passwords, and domain labels can each present this problem.  One of the most pressing issues for the general problem space noted above is resolving how internationalized names stored in the domain name system can be understood without a locale or similar context.

Internationalized names are currently stored in an ASCII-compatible encoding derived from the Unicode Standard.  That standard, however, includes certain characters which are visually identical but may be composed in multiple ways, the choice of which is locale-specific.  This creates an uncertainty in how a specific DNS label might be understood by other systems which rely on the DNS.  This issue is not limited to the DNS, but also occurs in other systems where a known-item match is expected; username and password matching are examples.  As originally described in the `related IAB statement`__, this topic is currently blocking specific updates and is the program’s current priority.  

__ https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-identifiers-and-unicode-7-0-0/

Mailing list:
-------------

Public discussion: i18n-discuss@iab.org 

Past IAB Actions on I18N
------------------------

* Weider, C., Preston, C., Simonsen, K., Alvestrand, H., Atkinson, R., Crispin, M., and P. Svanberg, “The Report of the IAB Character Set Workshop held 29 February – 1 March, 1996″, `RFC 2130`__, April 1997.
* IAB and L. Daigle, Ed., “A Tangled Web: Issues of I18N, Domain Names, and the Other Internet protocols”, `RFC 2825`__, May 2000.
* IAB Response__ to Verisign GRS IDN Announcement, January 2003.
* IAB to ICANN – IAB comments__ on ICANN IDN Guidelines, 14 October 2005.
* IAB response__ to the Unicode Technical Consortium re:”Procedural Issues with the Liaison on Nextsteps”, 16 June 2006.
* Klensin, J., Faltstrom, P., Karp, C., and IAB, “Review and Recommendations for Internationalized Domain Names (IDNs)”, `RFC 4690`__, September 2006.
* IAB `liaison statement`__ to ITU-T SG17 on the Review and Recommendations for Internationalized Domain Names, 2 October 2006.
* IAB Technical Plenary on Internationalization at IETF 68 (minutes__), 22 March 2007.
* IAB Technical Plenary on Internationalization at IETF 76 (minutes__), 12 November 2009.
* Techchat on IDNA2008, Unicode, and UTR 46 (minutes__), 7 April 2010.
* IAB response__ to the IDNA appeal from JFC Morfin, 20 August 2010.
* Thaler, D., Klensin, J., and S. Cheshire, “IAB Thoughts on Encodings for Internationalized Domain Names”, `RFC 6055`__, February 2011.
* IAB Statement__ on “The interpretation of rules in the ICANN gTLD Applicant Guidebook,” 8 February 2012.
* Sullivan, A., Thaler, D., Klensin, J., and O. Kolkman, “Principles for Unicode Code Point Inclusion in Labels in the DNS”, `RFC 6912`__, April 2013.
* IAB `Statement on Identifiers and Unicode 7.0.0`__, 11 February 2015

__ https://datatracker.ietf.org/doc/rfc2130
__ https://datatracker.ietf.org/doc/rfc2825
__ http://iab.org/documents/docs/icann-vgrs-response.html
__ http://iab.org/documents/correspondence/2005-10-14-idn-guidelines.html
__ http://iab.org/documents/correspondence/2006-06-16-response-to-idn-liaison-issues.html
__ https://datatracker.ietf.org/doc/rfc4690
__ http://iab.org/documents/correspondence/2006-10-02-idn-to-sg17.html
__ http://www.ietf.org/proceedings/68/plenaryt.html
__ http://www.ietf.org/proceedings/76/plenaryt.html
__ http://www.ietf.org/proceedings/76/plenaryt.html
__ http://www.iab.org/appeals/2010-08-20-morfin-response.pdf
__ http://datatracker.ietf.org/doc/rfc6055
__ http://www.iab.org/documents/correspondence-reports-documents/2012-2/iab-statement-the-interpretation-of-rules-in-the-icann-gtld-applicant-guidebook/
__ http://datatracker.ietf.org/doc/rfc6912
__ https://www.iab.org/2015/01/27/iab-posts-statement-on-identifiers-and-unicode-7-0-0/

""",
                lead='Ted Hardie',
                members=[
                         'Ted Hardie',
                         'Joe Hildebrand',
                         'Andrew Sullivan',
                         'Dave Thaler',
                         'Marc Blanchet',
                         'Francis Bond',
                         'Stuart Cheshire',
                         'Patrik Faltstrom',
                         'Heather Flanagan',
                         'Sarmad Hussain',
                         'Dr. John C. Klensin',
                         'Olaf Kolkman',
                         'Barry Leiba',
                         'Xing Li',
                         'Pete Resnick',
                         'Peter Saint-Andre',
                         'Yoshiro Yoneya',
                        ],
                docs= [],
               )

    build_group(acronym='iproc',
                name='IETF Protocol Registries Oversight',
                description="""
The IETF Protocol Registries Oversight Committee (IPROC) is an IAB program, as well as subcommittee of the IETF Administrative Oversight Committee (IAOC).

The primary focus of the IPROC is oversight of operations related to processing IETF protocol parameter requests.  In addition, the IPROC reviews the service level agreement (SLA) between the IETF and ICANN, which is typically updated each year to reflect current expectations.

The IPROC advises the IAB and the IAOC.  The IAB is responsible for IANA oversight with respect to the protocol parameter registries.  The IAOC is ultimately responsible for the fiscal and administrative support for the IANA protocol parameter registries.

The IPROC is focused on operations of the protocol parameter registries, not all of the IANA-related activities for the global Internet.  For more information on IAB activities related to broader IANA topics, please see the IANA Evolution Program.

Work Items
----------

The IPROC routinely does the following:

1. Provides review and recommendations related to the annual updates to the SLA between the IETF and ICANN;
2. Oversees and reviews deliverables described in the annual SLA;
3. Reviews operational issues related to processing protocol parameter requests, IESG designated experts, and tools development; and
4. Responds to specific developments and information requests.

""",
                lead='Russ Housley',
                members=[
                         'Jari Arkko',
                         'Russ Housley',
                         'Andrew Sullivan',
                         'Bernard Aboba',
                         'Michelle S. Cotton',
                         'Leslie Daigle',
                         'Elise P. Gerich',
                         'Ray Pelletier',
                         'Jonne Soininen',
                        ],
                docs=[],
               )

    build_group(acronym='iana-evolution',
                name='IANA Evolution',
                description="""
The IANA evolution program’s primary focus is the stewardship over the IANA functions for the Internet in General and the IETF in particular.

Its main focus is on:

* the contractual relations between the US DoC and ICANN and the globalization__ thereof;
* the IANA MoU (RFC2860) and related agreements between stakeholders;
* the development of a vision with respect to the future of the IANA functions; and
* implementation and interpretation of the above.

__ http://www.ntia.doc.gov/press-release/2014/ntia-announces-intent-transition-key-internet-domain-name-functions

The program acts also as a think-tank and advises the IAB on strategic and liaison issues.

In some cases this group may provide guidance and insight on matters relating ICANN in general.

The group is not responsible for daily operational guidance, such as review of the SLA between the IETF and ICANN.  Those responsibilities are delegated to the `IETF Protocol Registries Oversight Committee (IPROC)`__.

__ http://www.ietf.org/iana/iproc.html

Work Items
----------

The group focuses on the following high-level work items and responsibilities:

* Identifying the desired strategic direction for the relationship of IETF, the IANA function, and other parties.
* Tracking the developments surrounding the DoC IANA function contract and its globalization
* Responding to specific developments and information requests on this topic

The group developed, maintains  and advises on the implementation of the principles guiding the `Evolution on the IANA Protocol Parameter Registries`__.

__ http://www.iab.org/documents/correspondence-reports-documents/2014-2/re-guiding-the-evolution-of-the-iana-protocol-parameter-registries/

Results and References
----------------------

* `IANA MoU`__
* `IAB response to the IANA NOI`__
* `Defining the Role and Function of IETF Protocol Parameter Registry Operator (RFC6220)`__
* `ICANN-IETF Service Level Agreements`__
* `ICANN performance evaluation`__
* `Information on IANA performance`__
* `IANA oversight statement by IETF Administrative Director`__
* `RFC 7500: Principles for Operation of Internet Assigned Numbers Authority (IANA) Registries`__
* `Comments on RDAP Operational Profile for gTLD Registries and Registrars`__
* `Comments on the CCWG-Accountability 3rd Draft Report`__
* `Comments on the CCWG-Accountability 2nd Draft Report`__
* `Comments on the ICG Proposal`__
* `Comments on the CCWG-Accountability 1st Draft Report`__
* `Statement on the NETmundial Initiative`__

__ http://www.rfc-editor.org/rfc/rfc2860
__ http://www.iab.org/documents/correspondence/2011-03-30-iab-iana-noi-response.pdf
__ http://www.rfc-editor.org/rfc/rfc6220
__ http://iaoc.ietf.org/contracts.html
__ http://www.iab.org/2012/05/24/iab-submits-updated-icann-performance-evaluation/
__ http://www.iana.org/about/performance/
__ http://www.iab.org/2012/04/03/summary-of-ietf-iana-oversight-process/
__ http://www.rfc-editor.org/rfc/rfc7500.txt
__ https://www.iab.org/documents/correspondence-reports-documents/2016-2/comments-from-the-internet-architecture-board-iab-on-registration-data-access-protocol-rdap-operational-profile-for-gtld-registries-and-registrars/
__ https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-the-ccwg-accountability-3d-draft-report/
__ https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-ccwg-accountability/
__ https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-icg-proposal/
__ https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-ccwg-accountability-draft-report/
__ https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-statement-on-the-netmundial-initiative/

Related material:

    `Press Announcement:  Internet Technical Leaders Welcome IANA Globalization Progress`__

__ https://www.iab.org/2014/03/15/internet-technical-leaders-welcome-iana-globalization-progress/


""",
                lead='Russ Housley',
                members=[
                         'Jari Arkko',
                         'Marc Blanchet',
                         'Ted Hardie',
                         'Russ Housley',
                         'Andrew Sullivan',
                         'Suzanne Woolf',
                         'Bernard Aboba',
                         'Kathy Brown',
                         'Alissa Cooper',
                         'Leslie Daigle',
                         'Dr. John C. Klensin',
                         'Olaf Kolkman',
                         'Eliot Lear',
                         'Barry Leiba',
                         'Dr. Thomas Narten',
                         'Andrei Robachevsky',
                         'Jonne Soininen',
                         'Lynn St.Amour',
                        ],
                docs=[ 'draft-iab-aina-mou', 'draft-iab-iana-principles' ],
               )

    build_group(acronym='plenary-planning',
                name='Plenary Planning',
                description="""
The Plenary Planning Program seeks out topics for IETF Technical Plenary meetings. Typically, a Tech Plenary will feature one to three speakers on a topic that is of interest to at least several IETF Areas, and informs our work. The Program is always looking for interesting speakers, and suggestions are always welcome at tech-plenary@iab.org.

Program Description
-------------------

The Plenary Planning Program will identify informative and entertaining programs for the Tech Plenary at each IETF meeting. Potential presenters will normally be invited to give a Tech Chat to the IAB, as a way to familiarize the IAB with their work and presentation style.

Ideas for potential presenters may come from anywhere, but should be topical, informative, and relate to multiple areas of IETF work.
""",
                lead = 'Lee Howard',
                members=[
                            'Lee Howard',
                            'Lars Eggert',
                            'Brian Trammell',
                            'Suzanne Woolf',
                            'Dirk Kutscher',
                            'Allison Mankin',
                            'Greg Wood',
                        ],
                docs=[],
                )

    build_group(acronym='liaison-oversight',
                name = 'Liaison Oversight',
                description="""
The IETF is best served if developments in other SDOs that may overlap, or conflict with, work in the IETF are noticed early and the leadership can make informed decisions about appropriate actions to further the IETF work in the context of developments within other SDOs. Equally, if work is being proposed in the IETF that may overlap with work in other SDOs, recognition and consideration of this by the IESG and IAB is necessary.

The Liaison Oversight Program focuses on the liaison relationships between the IETF and other SDOs, as well as IETF documents and processes relating to those liaison relationships. As with other Programs, the Liaison Oversight Program develops recommendations for consideration by the IAB, and the IAB retains its oversight responsibilities under RFC 2850.

Program Description
-------------------

The Liaison Oversight Program:
==============================

* Organizes reviews of the liaison relationships with specific SDOs;
* Develops the framework for IAB management of liaison relationships;
* Assists in the recruitment of liaison managers;
* Reviews the requirements for IT systems relating to the handling of liaison statements;
* Reviews the operational experience with documents relating to liaison management and recommends changes, where appropriate. Relevant documents include (but are not limited to) RFC 4052, 4053 and 4691.
* Reviews the state of internal and external communication as well as conformance to transparency requirements;
* Prepares specific recommendations at the request of the IAB.

The framework for IAB management of liaison relationships includes:
===================================================================

* Development of processes, procedures and guidelines for liaison management;
* Coordination of the handling of liaisons within the IETF/IAB;
* Development of mechanisms to prevent inadvertent duplication of effort between the IETF and other SDOs without obstructing organizations from pursuing their own mandates;
* Development of authoritative summaries of one organization’s dependencies on the other’s work.

Interaction with other Programs
-------------------------------

The Liaison Oversight Program does not handle the liaison tasks itself; this function is performed by the liaison manager. However, the Liaison Oversight Program may develop recommendations relating to the relationship with specific SDOs, in cooperation with the IAB liaison shepherd and the liaison manager. The Liaison Oversight Program also may provide consistent information to the IAB regarding the relationship with other SDOs (e.g. periodic reports), and may make recommendations to the IAB.

In cases where the level of interaction or its intensity are high a separate effort will be created to handle this. At the time of writing, there is a program dedicated to ITU-T topics, – ITU-T Coordination Program. In addition, the relationships with Unicode and ISO/IEC JTC1 SC2 are covered by the Internationalization Program, and the relationship with the W3C is covered by the HTTP/Web Evolution Initiative.

References
----------

* “Liaisons to National, Multi-National or Regional Organizations”, http://iab.org/documents/docs/2003-06-10-national-liaisons.html
* “IAB Processes for Management of IETF Liaison Relationships”, `RFC 4052`__
* “Procedures for Handling Liaison Statements to and from the IETF”, `RFC 4053`__
* “Guidelines for Acting as an IETF Liaison to Another Organization”, `RFC 4691`__

__ http:/www.rfc-editor.org/rfc/rfc4052
__ http:/www.rfc-editor.org/rfc/rfc4053
__ http:/www.rfc-editor.org/rfc/rfc4691

Other Links
-----------

    External liaison page: http://iab.org/liaisons/index.html

""",
                lead = 'Ralph Droms',
                members = [ 'Ralph Droms',
                            'Marc Blanchet',
                            'Russ Housley',
                            'Robert Sparks',
                            'Suzanne Woolf',
                            'Scott O. Bradner',
                            'Ross Callon',
                            'Adrian Farrel',
                            'Dan Romascanu',
                            'Gonzalo Camarillo',
                            'Spencer Dawkins',
                            'Eliot Lear',
                            'Scott Mansfield',
                            'Dr. Thomas Narten',
                          ],
                docs=[],
                )


def removePrograms(apps, schema_editor):
    Group = apps.get_model('group','Group')
    Group.objects.filter(acronym__in=(
                                       'stackevo',
                                        'rfcedprog',
                                        'privsec',
                                        'inip',
                                        'i18n-program',
                                        'iproc',
                                        'iana-evolution',
                                        'plenary-planning',
                                        'liaison-oversight',
                                      )
                        ).delete()
    # Intentionally not deleting the Person/Email objects that were added

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0009_auto_20150930_0758'),
        ('name', '0017_iab_programs'),
        ('person', '0014_auto_20160613_0751'),
        ('community','0004_cleanup_data'),
        ('review', '0010_auto_20161214_1537'),
    ]

    operations = [
        migrations.RunPython(addPrograms,removePrograms)
    ]
