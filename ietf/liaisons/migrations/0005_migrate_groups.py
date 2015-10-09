# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def create_new_groups(apps, schema_editor):
    Group = apps.get_model("group","Group")
    for group in NEW_GROUPS:
        if group[2]:
            #print "Get parent: {}".format(group[2])
            parent = Group.objects.get(acronym=group[2])
        else:
            parent = None
        Group.objects.create(
            acronym=group[0],
            name=group[1],
            parent=parent,
            type_id='sdo',
            state_id=group[3])

def change_acronyms(apps, schema_editor):
    '''Modify some existing groups'''
    Group = apps.get_model("group","Group")
    for old,new in CHANGE_ACRONYM:
        group = Group.objects.get(acronym=old)
        group.acronym = new
        group.save()

def set_parents(apps, schema_editor):
    '''Modify some existing groups'''
    Group = apps.get_model("group","Group")
    for child_acronym,parent_acronym in SET_PARENT:
        #print "Setting parent {}:{}".format(child_acronym,parent_acronym)
        child = Group.objects.get(acronym=child_acronym)
        parent = Group.objects.get(acronym=parent_acronym)
        child.parent = parent
        child.save()

def reassign_groups(apps,schema_editor):
    '''For Statements that have a multi to_group assignment, remove the group
    assignment and populate the to_name field for conversion to multiple groups
    in later function'''
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    for acronym,name in MULTI_TO_GROUPS:
        for stmt in LiaisonStatement.objects.filter(to_group__acronym=acronym):
            stmt.to_name=name
            stmt.to_group=None
            stmt.save()

def cleanup_groups(apps, schema_editor):
    Group = apps.get_model("group","Group")
    for group,x in MULTI_TO_GROUPS:
        Group.objects.get(acronym=group).delete()

def copy_to_group(apps, schema_editor):
    '''For this migration we are favoring the value in to_name over to_group.  Based
    on observation there are statements with multiple groups in the to_name but
    restricted to one to_group.'''
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    Group = apps.get_model("group","Group")
    for s in LiaisonStatement.objects.all():
        if s.to_name and s.to_name in TO_NAME_MAPPING:
            if TO_NAME_MAPPING[s.to_name]:
                got_exception = False
                for acronym in TO_NAME_MAPPING[s.to_name]:
                    try:
                        s.to_groups.add(Group.objects.get(acronym=acronym))
                    except Group.DoesNotExist:
                        print "Group Does Not Exist: {},{},{}".format(s.pk,s.to_name,acronym)
                        got_exception = True
                if not got_exception:
                    s.to_name = ''
                    s.save()
            else:
                print "{}:{} empty to_group mapping".format(s.pk,s.to_name)

        elif s.to_group:
            s.to_groups.add(s.to_group)
            s.to_name = ''
            s.save()

def copy_from_group(apps, schema_editor):
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    Group = apps.get_model("group","Group")
    for s in LiaisonStatement.objects.all():
        if s.from_name and s.from_name in FROM_NAME_MAPPING:
            if FROM_NAME_MAPPING[s.from_name]:
                got_exception = False
                for acronym in FROM_NAME_MAPPING[s.from_name]:
                    try:
                        s.from_groups.add(Group.objects.get(acronym=acronym))
                    except Group.DoesNotExist:
                        print "Group Does Not Exist: {}".format(acronym)
                        got_exception = True
                if not got_exception:
                    s.from_name = ''
                    s.save()
            else:
                print "{}:{} empty from_group mapping".format(s.pk,s.from_name)
        elif s.from_group:
            s.from_groups.add(s.from_group)
            s.from_name = ''
            s.save()
        else:
            print "from_name not mapped and no from_group {}".format(s.pk)
        
        # set from_contact
        #if s.from_contact:
        #    for fg in s.fromgroup_set.all():
        #        fg.contact = s.from_contact
        #        fg.save()

def set_default_poc(apps, schema_editor):
    """Set default group POC if there is only one unique value"""
    LiaisonStatementGroupContacts = apps.get_model("liaisons", "LiaisonStatementGroupContacts")
    Group = apps.get_model("group", "Group")
    for group in Group.objects.filter(liaisonstatement_to_set__isnull=False).distinct():
        contacts = set()
        for stmt in group.liaisonstatement_to_set.all():
            if stmt.to_contacts:
                contacts.add(stmt.to_contacts)
        if len(contacts) == 1:
            LiaisonStatementGroupContacts.objects.create(group=group,contacts=contacts.pop())
    
    # do explicit mappings
    for acronym,contacts in DEFAULT_POC.items():
        group = Group.objects.get(acronym=acronym)
        try:
            lsgc = LiaisonStatementGroupContacts.objects.get(group=group)
            lsgc.contacts = contacts
            lsgc.save()
        except LiaisonStatementGroupContacts.DoesNotExist:
            LiaisonStatementGroupContacts.objects.create(group=group,contacts=contacts)


def set_cc_contacts(apps, schema_editor):
    """Set initial LiaisonStatementGroupContacts.cc_contacts"""
    LiaisonStatementGroupContacts = apps.get_model("liaisons", "LiaisonStatementGroupContacts")
    Group = apps.get_model("group", "Group")
    cc_contacts = 'itu-t-liaison@iab.org'
    for group in Group.objects.filter(acronym__startswith='itu'):
        lsgc = group.liaisonstatementgroupcontacts_set.first()
        if lsgc:
            lsgc.cc_contacts = cc_contacts
            lsgc.save()
        else:
            LiaisonStatementGroupContacts.objects.create(group=group,cc_contacts=cc_contacts)

def explicit_mappings(apps, schema_editor):
    """In some cases the to_name cannot be mapped one-to-one with a group.  The
    following liaison statements are modified individually
    """
    #LiaisonStatementFromGroup = apps.get_model("liaisons", "LiaisonStatmentFromGroup")
    LiaisonStatement = apps.get_model("liaisons", "LiaisonStatement")
    Group = apps.get_model("group", "Group")
    
    def _setgroup(to=None,frm=None,pks=None):
        for pk in pks:
            s = LiaisonStatement.objects.get(pk=pk)
            if to:
                s.to_groups.add(*Group.objects.filter(acronym__in=to))
                s.to_name = ''
            if frm:
                #for acronym in frm:
                #    LiaisonStatementFromGroup.objects.create(statement=s,group=Group.objects.get(acronym=acronym))
                s.from_groups.add(*Group.objects.filter(acronym__in=frm))
                s.from_name = ''
            s.save()
    
    _setgroup(to=['ietf'],pks=[116,782,796,797,823,835,836,837,840])
    _setgroup(to=['sipping'],pks=[809])
    _setgroup(to=['ieprep'],pks=[810])
    _setgroup(to=['atm-forum'],frm=['megaco'],pks=[816])
    _setgroup(to=['ccamp'],pks=[827,829])
    _setgroup(to=['sub','tsv'],pks=[828])
    _setgroup(to=['sigtran'],pks=[830])
    _setgroup(to=['irtf'],pks=[831,832,833,834])
    _setgroup(to=['rmt'],pks=[838,839])
    _setgroup(to=['ietf','iana'],pks=[841])
    _setgroup(to=['isoc','iana'],pks=[842])
    _setgroup(to=['ietf','avt'],pks=[811,812])
    _setgroup(to=['avt'],pks=[822])
    # 821 / 824
    
class Migration(migrations.Migration):

    dependencies = [
        ('liaisons', '0004_migrate_attachments'),
    ]

    operations = [
        migrations.RunPython(change_acronyms),
        migrations.RunPython(create_new_groups),
        migrations.RunPython(set_parents),
        migrations.RunPython(reassign_groups),
        migrations.RunPython(copy_to_group),
        migrations.RunPython(copy_from_group),
        migrations.RunPython(set_default_poc),
        migrations.RunPython(set_cc_contacts),
        migrations.RunPython(cleanup_groups),
        migrations.RunPython(explicit_mappings),
    ]

# ----------------------------------------------------------
# x_name to group mappings
# -----------------------------------------------------------
NEW_GROUPS = [
    ('3gpp-tsgsa','SGPP TSG SA','3gpp','active'),
    ('3gpp-tsgsa-sa2','3GPP TSG SA WG2','3gpp-tsgsa','active'),
    ('3gpp-tsgsa-sa3','3GPP TSG SA WG3','3gpp-tsgsa','active'),
    ('3gpp-tsgct','SGPP TSG CT','3gpp','active'),
    ('3gpp-tsgct-ct1','3GPP TSG CT WG1','3gpp-tsgct','active'),
    ('3gpp-tsgct-ct4','3GPP TSG CT WG4','3gpp-tsgct','active'),
    ('3gpp-tsgran','SGPP TSG RAN','3gpp','active'),
    ('3gpp-tsgran-ran2','3GPP TSG RAN WG2','3gpp-tsgran','active'),
    ('3gpp-tsgt-wg2','3GPP-TSGT-WG2','3gpp','active'),
    ('acif','Australian Communications Industry Forum',None,'active'),
    ('arib','Association of Radio Industries and Business',None,'active'),
    ('ashrae','American Society of Heating, Refrigerating, and Air-Conditioning Engineers',None,'active'),
    ('atis','ATIS',None,'active'),
    ('atm-forum','ATM Forum',None,'active'),
    ('ccsa','China Communications Standards Association',None,'active'),
    ('dlna','Digital Living Network Alliance',None,'active'),
    ('dsl-forum','DSL Forum',None,'active'),
    ('dsl-forum-twg','DSL Forum Architecture & Transport Working Group','dsl-forum','active'),
    ('dvb-tm-ipi','DVB TM-IPI',None,'active'),
    ('epcglobal','EPCGlobal',None,'active'),
    ('etsi','ETSI',None,'active'),
    ('etsi-at-digital','ETSI AT Digital','etsi','active'),
    ('etsi-bran','ETSI BRAN','etsi','active'),
    ('etsi-dect','ETSI DECT','etsi','active'),
    ('etsi-emtel','ETSI EMTEL','etsi','active'),
    ('etsi-tc-hf','ETSI TC HF','etsi','active'),
    ('etsi-tispan','ETSI TISPAN','etsi','active'),
    ('etsi-tispan-wg4','ETSI TISPAN WG4','etsi-tispan','active'),
    ('etsi-tispan-wg5','ETSI TISPAN WG5','etsi-tispan','active'),
    ('femto-forum','Femto Forum',None,'active'),
    ('gsma','GSMA',None,'active'),
    ('gsma-wlan','GSMA WLAN','gsma','active'),
    ('incits-t11-5','INCITS T11.5',None,'active'),
    ('isma','Internet Streaming Media Alliance',None,'active'),
    ('itu','ITU',None,'active'),
    ('itu-r-wp5a','ITU-R-WP5A','itu-r','active'),
    ('itu-r-wp5d','ITU-R-WP5D','itu-r','active'),
    ('itu-r-wp8a','ITU-R-WP8A','itu-r','active'),
    ('itu-r-wp8f','ITU-R-WP8F','itu-r','active'),
    ('itu-t-ipv6-group','ITU-T-IPV6-GROUP','itu-t','active'),
    ('itu-t-fg-cloud','ITU-T-FG-CLOUD','itu-t','conclude'),
    ('itu-t-fg-iptv','ITU-T-FG-IPTV','itu-t','conclude'),
    ('itu-t-fg-ngnm','ITU-T-FG-NGNM','itu-t','conclude'),
    ('itu-t-jca-idm','ITU-T-JCA-IDM','itu-t','active'),
    ('itu-t-ngnmfg','ITU-T-NGNMFG','itu-t','active'),
    ('itu-t-sg-4','ITU-T-SG-4','itu-t','conclude'),
    ('itu-t-sg-6','ITU-T-SG-6','itu-t','conclude'),
    ('itu-t-sg-7','ITU-T-SG-7','itu-t','conclude'),
    ('itu-t-sg-8','ITU-T-SG-8','itu-t','conclude'),
    ('itu-t-sg-9','ITU-T-SG-9','itu-t','active'),
    ('itu-t-sg-2-q1','ITU-T-SG-2-Q1','itu-t-sg-2','active'),
    ('itu-t-sg-11-q5','ITU-T-SG-11-Q5','itu-t-sg-11','active'),
    ('itu-t-sg-11-wp2','ITU-T-SG-11-WP2','itu-t-sg-11','active'),
    ('itu-t-sg-12-q12','ITU-T-SG-12-Q12','itu-t-sg-12','active'),
    ('itu-t-sg-12-q17','ITU-T-SG-12-Q17','itu-t-sg-12','active'),
    ('itu-t-sg-13-q3','ITU-T-SG-13-Q3','itu-t-sg-13','active'),
    ('itu-t-sg-13-q5','ITU-T-SG-13-Q5','itu-t-sg-13','active'),
    ('itu-t-sg-13-q7','ITU-T-SG-13-Q7','itu-t-sg-13','active'),
    ('itu-t-sg-13-q9','ITU-T-SG-13-Q9','itu-t-sg-13','active'),
    ('itu-t-sg-13-q11','ITU-T-SG-13-Q11','itu-t-sg-13','active'),
    ('itu-t-sg-13-wp3','ITU-T-SG-13-WP3','itu-t-sg-13','conclude'),
    ('itu-t-sg-13-wp4','ITU-T-SG-13-WP4','itu-t-sg-13','conclude'),
    ('itu-t-sg-13-wp5','ITU-T-SG-13-WP5','itu-t-sg-13','conclude'),
    ('itu-t-sg-14','ITU-T-SG-14','itu-t','active'),
    ('itu-t-sg-15-q1','ITU-T-SG-15-Q1','itu-t-sg-15','active'),
    ('itu-t-sg-15-q3','ITU-T-SG-15-Q3','itu-t-sg-15','active'),
    ('itu-t-sg-15-q4','ITU-T-SG-15-Q4','itu-t-sg-15','active'),
    ('itu-t-sg-15-q6','ITU-T-SG-15-Q6','itu-t-sg-15','active'),
    ('itu-t-sg-15-q9','ITU-T-SG-15-Q9','itu-t-sg-15','active'),
    ('itu-t-sg-15-q10','ITU-T-SG-15-Q10','itu-t-sg-15','active'),
    ('itu-t-sg-15-q11','ITU-T-SG-15-Q11','itu-t-sg-15','active'),
    ('itu-t-sg-15-q12','ITU-T-SG-15-Q12','itu-t-sg-15','active'),
    ('itu-t-sg-15-q14','ITU-T-SG-15-Q14','itu-t-sg-15','active'),
    ('itu-t-sg-15-q15','ITU-T-SG-15-Q15','itu-t-sg-15','active'),
    ('itu-t-sg-15-wp1','ITU-T-SG-15-WP1','itu-t-sg-15','active'),
    ('itu-t-sg-15-wp3','ITU-T-SG-15-WP3','itu-t-sg-15','active'),
    ('itu-t-sg-16-q8','ITU-T-SG-16-Q8','itu-t-sg-16','active'),
    ('itu-t-sg-16-q9','ITU-T-SG-16-Q9','itu-t-sg-16','active'),
    ('itu-t-sg-16-q10','ITU-T-SG-16-Q10','itu-t-sg-16','active'),
    #('itu-t-sg-17-tsb','ITU-T-SG-17-TSB','itu-t-sg-17','active'),
    ('itu-t-sg-17-q2','ITU-T-SG-17-Q2','itu-t-sg-17','active'),
    #('itu-t-sg-17-q4','ITU-T-SG-17-Q4','itu-t-sg-17','active'),
    ('itu-t-sg-20','ITU-T-SG-20','itu-t','active'),
    ('ieee','IEEE',None,'active'),
    ('ieee-802','IEEE 802','ieee','active'),
    ('ieee-802-ec','IEEE 802 Executive Committee','ieee','active'),
    ('ieee-802-21','IEEE 802.21','ieee-802','active'),
    ('ieee-sa-ngson','IEEE SA NGSON','ieee-sa','active'),
    ('iso-iec-jtc1','ISO/IEC JTC1',None,'active'),
    ('iso-iec-jtc1-sc29-wg1','ISO/IEC JTC1 SC29 WG1','iso-iec-jtc1-sc29','active'),
    ('iso-iec-jtc1-sc31','ISO/IEC JTC1 SC31','iso-iec-jtc1','active'),
    ('iso-iec-jtc1-sc31-wg4','ISO/IEC JTC1 SC31 WG4','iso-iec-jtc1-sc31','active'),
    ('iso-iec-jtc1-sgsn','ISO/IEC JTC1 SGSN','iso-iec-jtc1','active'),
    ('iso-iec-jtc1-wg7','ISO/IEC JTC1 WG7','iso-iec-jtc1','active'),
    ('mead','IETF MEAD Team','rtg','active'),
    ('mfa-forum','MFA Forum',None,'active'),
    ('mpeg','MPEG',None,'active'),
    ('mpls-forum','MPLS Forum',None,'active'),
    ('mfa','MPLS and Frame Relay Alliance',None,'active'),
    ('nanc-lnpa-wg','NANC LNPA WG',None,'active'),
    ('nmnro','National, Multi-National or Regional Organizations',None,'active'),
    ('oma','OMA',None,'active'),
    ('oma-bcast','OMA BCAST','oma','active'),
    ('oma-com-cab','OMA COM CAB','oma','active'),
    ('oma-com-cpm','OMA COM CPM','oma','active'),
    ('oma-mwg','OMA MWG','oma','active'),
    ('oma-mwg-mem','OMA MWG-MEM','oma-mwg','active'),
    ('oma-pag-wg','OMA PAG WG','oma','active'),
    ('oma-tp','OMA TP','oma','active'),
    ('opif','Open IPTV Forum',None,'active'),
    ('t1m1','T1M1',None,'active'),
    ('t1s1','T1S1',None,'active'),
    ('t1x1','T1X1',None,'active'),
    ('tia','TIA',None,'active'),
    ('tmoc','TMOC',None,'active'),
    ('w3c-geolocation-wg','W3C Geolocation WG','w3c','active'),
    ('w3c-mmi','W3C MMI','w3c','active'),
    ('wifi-alliance','Wifi Alliance',None,'active'),
    ('wig','WIG',None,'active'),
]

CHANGE_ACRONYM = [
    ('ieee-8021','ieee-802-1'),
    ('ieee-8023','ieee-802-3'),
    ('ieee-80211','ieee-802-11'),
    ('ieee-80216','ieee-802-16'),
    ('ieee-80223','ieee-802-23'),
    ('isoiec-jtc1-sc2','iso-iec-jtc1-sc2'),
    ('isoiec-jtc1-sc6','iso-iec-jtc1-sc6'),
    ('isoiec-jtc1-sc29','iso-iec-jtc1-sc29'),
    ('isoiec-jtc-1sc-29wg-11','iso-iec-jtc1-sc29-wg11'),
    ('itu-t-fgd','itu-t-fg-dist'),
    ('itu-t-sg17-q4','itu-t-sg-17-q4'),
    ('itu-t-sg17-tsb','itu-t-sg-17-tsb'),
    ('ITU-T-SG5','itu-t-sg-5'),
    ('3GPP-TSG-SA-WG4','3gpp-tsgsa-sa4'),
    ('IEEE-802-OmniRAN','ieee-802-ec-omniran'),
]
    
SET_PARENT = [
    ('itu-t','itu'),
    ('itu-r','itu'),
    ('itu-t-jca-cloud','itu-t'),
    ('itu-t-jca-cop','itu-t'),
    ('itu-t-jca-sdn','itu-t'),
    ('itu-t-mpls','itu-t'),
    ('itu-t-sg-2','itu-t'),
    ('itu-t-sg-3','itu-t'),
    ('itu-t-sg-11','itu-t'),
    ('itu-t-sg-12','itu-t'),
    ('itu-t-sg-13','itu-t'),
    ('itu-t-sg-15','itu-t'),
    ('itu-t-sg-16','itu-t'),
    ('itu-t-sg-17','itu-t'),
    ('itu-t-tsag','itu-t'),
    ('ieee-sa','ieee'),
    ('ieee-802-1','ieee-802'),
    ('ieee-802-3','ieee-802'),
    ('ieee-802-11','ieee-802'),
    ('ieee-802-16','ieee-802'),
    ('ieee-802-23','ieee-802'),
    ('ieee-802-ec-omniran','ieee-802-ec'),
    ('iso-iec-jtc1-sc2','iso-iec-jtc1'),
    ('iso-iec-jtc1-sc6','iso-iec-jtc1'),
    ('iso-iec-jtc1-sc7','iso-iec-jtc1'),
    ('iso-iec-jtc1-sc27','iso-iec-jtc1'),
    ('iso-iec-jtc1-sc29','iso-iec-jtc1'),
    ('iso-iec-jtc1-sc29-wg11','iso-iec-jtc1-sc29'),
]

MULTI_TO_GROUPS = [
    ('itu-t-sg15-q9-q10-q12-and-q14','ITU-T SG 15 Q9, Q10, Q12 and Q14'),
    ('itu-t-sg12-q-12-17','ITU-T SG 12, Q12, Q17'),
]

TO_NAME_MAPPING = {
    u'(bwijnen@lucent.com) Bert Wijnen': [u'sming'],
    u'(lyong@ciena.com)Lyndon Ong': [u'itu-t-sg-15'],
    #u'(sob@harvard.edu) Scott Bradner': None,   # this is a bunch (explicit)
    u'(sob@harvard.edu)Scott Bradner': ['irtf'],    # this is 833
    u'3GPP SA WG4': [u'3gpp-tsgsa-sa4'],
    u'3GPP SA2': [u'3gpp-tsgsa-sa2'],
    u'3GPP TSG CT WG4': [u'3gpp-tsgct-ct4'],
    u'3GPP TSG RAN WG2': [u'3gpp-tsgran-ran2'],
    u'3GPP TSG SA WG4': [u'3gpp-tsgsa-sa4'],
    u'3GPP, 3GPP2, ARIB, ATIS, CCSA, ETSI, ETSI-DECT, ETSI-BRAN, IEEE, IETF,': [u'ietf'],
    u'3GPP/IETF and 3GPP/ITU-T Co-ordinator': ['3gpp-tsgct-ct1'],
    u'ACIF, ARIB, ATIS, CCSA, ETSI, IEEE, IETF, ISACC, TIA, TTA, TTC': ['ietf'],
    u'ASON-related Work': ['ccamp'],
    u'ATIS': ['atis'],
    u'American Society of Heating, Refrigerating, and Air-Conditioning Engineers': ['ashrae'],
    u'BBF': ['broadband-forum'],
    u'BMWG': [u'bmwg'],
    u'Bert Wijnen and the IETF O & M Area': [u'ops'],
    u'Bert Wijnen, Bernard Aboba and the IETF': [u'ietf'],
    u'CCAMP WG co-chairs and IEEE-IETF': ['ccamp'],
    u'CCAMP WG co-chairs and IEEE-IETF liaisons': ['ccamp'],
    u'Completes action above Scott Bradner, Area co-Director (sob@harvard.edu)': ['tsv'],
    u'DLNA': ['dlna'],
    #u'DONE': None,   # this one is explicitly mapped
    u'DSL Forum': [u'dsl-forum'],
    u'DSL Forum Architecture & Transport Working Group': ['dsl-forum-twg'],
    u'DVB IPI': ['dvb-tm-ipi'],
    u'DVB TM-IPI, ETSI TISPAN, ATIS IIF, IETF RMT, IETF FECFRAME': ['fecframe','rmt'],
    u'EAP Method Update Working Group': ['emu'],
    u'ETSI AT working group Digital': ['etsi-at-digital'],
    u'ETSI TC HF': ['etsi-tc-hf'],
    u'ETSI TISPAN': ['etsi-tispan'],
    u'G.7712 Editor, ITU-T SG15Q14 Rapporteur, ITU-T SG15': ['itu-t-sg-15'],
    u'Generic EAP Encapsulation': ['int'],
    u'Harald Alvestrand': ['avt'],      # placeholder for explicit (2)
    u'IAB and IETF Routing Area Directors': [u'iab', 'rtg'],
    u'IAB, IESG': [u'iab', 'iesg'],
    u'IANA': [u'iana'],
    u'ICANN, IETF/IAB, NRO and ACSIS': ['ietf','iab'],
    u'IEEE 802': [u'ieee-802'],
    u'IEEE NGSON Study Group': ['ieee-sa-ngson'],
    u'IEEE802.1': [u'ieee-802-1'],
    u'IESG members, IAB members': [u'iesg', u'iab'],
    u'IESG, IAB, IETF MPLS WG': ['iesg','iab','mpls'],
    u'IESG, IETF-RAI': [u'iesg', u'rai'],
    u'IESG/IAB Chair': [u'iesg', u'iab'],
    u'IETF  PWE3 and TICTOC': [u'pwe3', u'tictoc'],
    u'IETF (CCAMP, PCE and MPLS WGs)': [u'ccamp', u'pce', u'mpls'],
    u'IETF (Management)': ['iesg'],
    u'IETF (SAVI and V6OPS WGS, OPS Area and INT Area)': [u'savi', u'v6ops', u'ops', u'int'],
    u'IETF (Sub-IP & Transport Areas)': [u'sub', u'tsv'],
    u'IETF (and others)': [u'ietf'],
    u'IETF (ccamp, pce and mpls WGs)': [u'ccamp', u'pce', u'mpls'],
    u'IETF 6MAN WG, IETF Internet Area': [u'6man', u'int'],
    u'IETF AVT WG, ITU-T SG11': [u'avt', u'itu-t-sg-11'],
    #u'IETF CCAMP WG and Routing Area Directors': [u'ccamp', u'rtg'],
    #u'IETF CCAMP WG and Sub IP Directors': [u'ccamp','sub'],
    #u'IETF CCAMP WG and Sub-IP Area Directors': [u'ccamp','sub'],
    u'IETF CCAMP WG, CC: IETF OSPF WG': [u'ospf','ccamp'],
    u'IETF CCAMP WG, Routing Area Directors': [u'ccamp', u'rtg'],
    u'IETF CCAMP and MPLS WGs': [u'ccamp', u'mpls'],
    u'IETF CCAMP and MPLS WGs and the Routing Area Directors of the IETF': [u'ccamp', u'mpls', u'rtg'],
    u'IETF CCAMP and PCE WGs': [u'ccamp', u'pce'],
    u'IETF CCAMP, IETF Routing Area Directors': [u'ccamp', u'rtg'],
    u'IETF CCAMP, PCE and MPLS WGs': [u'ccamp', u'pce', u'mpls'],
    u'IETF Charter group on Authority to Citizen Alert (ATOCA)': [u'atoca'],
    u'IETF DNSOP WG, SAAG, IAB': [u'dnsop', u'saag', u'iab'],
    u'IETF IAB, IETF IESG': [u'iab', u'ietf', u'iesg'],
    u'IETF IESG, IAB, PWE3 WG, MPLS WG, routing and internet Area Directors': [u'iesg', u'iab', u'pwe3', u'mpls', u'rtg', u'int'],
    u'IETF IESG, IETF MPLS WG': [u'mpls','iesg'],
    #u'IETF ISIS WG and Routing Area Directors': [u'isis','rtg'],
    u'IETF IPPM, IETF AVT': [u'ippm', u'avt'],
    u'IETF Internet Area; IETF MIF WG; IETF v6ops WG; IETF 6man WG; IETF softwire WG;  IETF Operations and Management Area': [u'int', u'mif', u'v6ops', u'6man', u'softwire', u'ops'],
    u'IETF Liaison to the ITU on MPLS and PWE3 WG Co-Chair': [u'itu-t-mpls', u'pwe3'],
    u'IETF MEAD Team': [u'mead'],
    u'IETF MEAD team': [u'mead'],
    u'IETF MEXT WG': ['mext'],
    u'IETF MIPSHOP-WG': [u'mipshop'],
    u'IETF MMUSIC WG,IETF SIPPING WG': [u'sipping','mmusic'],
    u'IETF MPLS & PWE3': [u'mpls', u'pwe3'],
    u'IETF MPLS WG, CC: IETF CCAMP and PWE3  WGs': [u'mpls', u'ccamp', u'pwe3'],
    u'IETF MPLS WG, CC: MFA Forum': ['mpls','mfa-forum'],
    u'IETF MPLS WG, IAB, IESG': [u'mpls', u'iab', u'iesg'],
    u'IETF MPLS WG, IETF IAB and IESG': [u'mpls', u'iab', u'iesg'],
    u'IETF MPLS WG, IETF PWE3 WG, Broadband Forum': [u'mpls', u'pwe3', u'broadband-forum'],
    u'IETF MPLS WG Co Chairs (Info: CCAMP WG Co Chairs, MEAD team)': [u'mpls','ccamp','mead'],
    u'IETF MPLS WG Co-Chairs, CC: IETF MEAD team': [u'mpls','mead'],
    u'IETF MPLS WG and OPSA WG': [u'mpls','opsawg'],
    u'IETF MPLS WG and PEW3 WG': [u'mpls','pwe3'],
    u'IETF MPLS WG, PWE3 WG': [u'pwe3','mpls'],
    u'IETF MPLS and GMPLS': ['mpls'],
    u'IETF MPLS and PWE3 WG, MFA Forum, ITU-T Q7/13': ['mpls','pwe3','mfa-forum','itu-t-sg-13-q7'],
    u'IETF MPLS liaison representative': [u'mpls'],
    u'IETF MPLS, CCAMP and PWE3  WGs': [u'mpls', u'ccamp', u'pwe3'],
    u'IETF MPLS, CCAMP, PWE3 and L2VPN': [u'mpls', u'ccamp', u'pwe3', u'l2vpn'],
    u'IETF MPLS, PWE WGs (Info: IETF MEAD team)': ['mpls','pwe3','mead'],
    u'IETF Mead Team': [u'mead'],
    u'IETF NSIS WG Chairs, IETF TSV Area Directors, IESG members, IAB members': [u'nsis', u'tsv', u'iesg', u'iab'],
    u'IETF PWE3 and L2VPN': [u'pwe3', u'l2vpn'],
    u'IETF PWE3 and L2VPN Working Groups': [u'pwe3', u'l2vpn'],
    u'IETF PWE3 and MPLS WG': [u'mpls',u'pwe3'],
    u'IETF PWE3 and MPLS WGs': [u'pwe3', u'mpls'],
    u'IETF PWE3 and MPLS Working Groups': [u'pwe3', u'mpls'],
    u'IETF PWE3, IETF L2VPN WG': ['pwe3',u'l2vpn'],
    u'IETF PWE3, MPLS working groups': [u'pwe3', u'mpls'],
    u'IETF RAI and IESG': [u'rai', 'iesg'],
    u'IETF Real-time Applications and Infrastructure Area Director': [u'rai'],
    u'IETF Routing Area, the MPLS and CCAMP working groups': [u'rtg', u'mpls', u'ccamp'],
    u'IETF Routing Area (CCAMP WG) and Internet Area (L2VPN WG and L3VPN WG)': ['ccamp','l2vpn','l3vpn'],
    u'IETF Routing Area Directors and IAB  (CC: CCAMP WG)': ['ccamp',u'rtg','iab'],
    u'IETF Routing Area Directors and IS-IS WG': ['isis'],
    u'IETF Routing and Transport areas': [u'rtg', u'tsv'],
    u'IETF Security Area Directors, CC: IETF CCAMP WG': [u'sec','ccamp'],
    u'IETF SIP related Working Groups and IESG': ['iesg','rai'],
    u'IETF Transport and Internat Areas': [u'tsv', u'int'],
    u'IETF Transport Area Directors, PCN Working Group Chairs': [u'pcn'],
    u'IETF WG MPLS': [u'mpls'],
    u'IETF Working Groups IEPREP, TSV, NSIS': [u'ieprep', u'tsv', u'nsis'],
    u'IETF and Harald Alvestrand': ['ietf'],
    u'IETF and IAB': [u'ietf', u'iab'],
    u'IETF avt and mmusic WG': [u'mmusic','avt'],
    u'IETF ccamp and pce WG': ['ccamp',u'pce'],
    u'IETF mobileip WG and mpls WG': [u'mobileip','mpls'],
    u'IETF mpls WG, CC: IETF pwe3 WG': ['mpls',u'pwe3'],
    u'IETF mpls and ccamp WG': ['mpls',u'ccamp'],
    u'IETF pwe3 WG, CC: mpls WG': [u'mpls','pwe3'],
    u'IETF pwe3, mpls WGs': [u'pwe3', u'mpls'],
    u'IETF pwe3 and mpls WG': [u'mpls','pwe3'],
    u'IETF re RoHC': [u'rohc'],
    u'IETF \u2013 Internet Area Directors, Internet Area Working Groups': [u'int'],
    u'IETF: Transport Area Directors, PCN Working Group Chairs': [u'pcn'],
    u'IETF, IAB': [u'ietf', u'iab'],
    u'IETF/IAB': [u'ietf', u'iab'],
    u'IETF/IAB, NRO, ICANN and ACSIS': ['ietf','iab'],
    u'IETF/IAB/IESG': [u'ietf', u'iab', u'iesg'],
    u'IETF/PWE3 and L2VPN WGs': [u'pwe3', u'l2vpn'],
    u'ISIS': [u'isis'],
    u'ISMA': ['isma'],
    u'ISO/IEC JTC': [u'iso-iec-jtc1'],
    u'ISO/IEC JTC 1/SC 29/WG 1': [u'iso-iec-jtc1-sc29-wg1'],
    u'ISOC': [u'isoc'],
    u'ISOC/IAB Liaison': [u'isoc', 'iab'],
    u'ITU': [u'itu'],
    u'ITU IPv6 Group': [u'itu-t-ipv6-group'],
    u'ITU Q12/15 and Q14/15': [u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU SG 16 Q8, 9, 10/16': [u'itu-t-sg-16-q8',u'itu-t-sg-16-q9',u'itu-t-sg-16-q10'],
    u'ITU SG13': [u'itu-t-sg-13'],
    u'ITU SG15': [u'itu-t-sg-15'],
    u'ITU-R': [u'itu-r'],
    u'ITU-R WP8F & IETF': [u'itu-r-wp8f',u'ietf'],
    u'ITU-SG15': [u'itu-t-sg-15'],
    u'ITU-SG2': [u'itu-t-sg-2'],
    u'ITU-T JCA-IdM': [u'itu-t-jca-idm'],
    u'ITU-T Q1/SG15': [u'itu-t-sg-15-q1'],
    u'ITU-T Q10/15': [u'itu-t-sg-15-q10'],
    u'ITU-T Q12/15 and Q14/15': [u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T Q14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T Q14/15 - Mr. Kam Lam, Rapporteur': [u'itu-t-sg-15-q14'],
    u'ITU-T Q14/15, ITU-T Q11/15': [u'itu-t-sg-15-q11',u'itu-t-sg-15-q14'],
    u'ITU-T Q3/15': [u'itu-t-sg-15-q3'],
    u'ITU-T Q5/13 (recently renamed ITU-T Q7/13)': [u'itu-t-sg-13-q7'],
    u'ITU-T Q7/SG13': [u'itu-t-sg-13-q7'],
    u'ITU-T Question 14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T Question 3/15': [u'itu-t-sg-15-q3'],
    u'ITU-T SG 11 and ITU-T TSAG': [u'itu-t-sg-11',u'itu-t-tsag'],
    u'ITU-T SG 11, ITU-T Q.5/11, ITU-T WP 2/11': [u'itu-t-sg-11',u'itu-t-sg-11-q5',u'itu-t-sg-11-wp2'],
    u'ITU-T SG 12, Q12, Q17': [u'itu-t-sg12-q-12-17'],
    u'ITU-T SG 13 (ITU-T SG 11 and SG 12 for information)': [u'itu-t-sg-13',u'itu-t-sg-12',u'itu-t-sg-12'],
    u'ITU-T SG 13 (ITU-T SG 11 for information)': [u'itu-t-sg-13',u'itu-t-sg-11'],
    u'ITU-T SG 13, SG 15': [u'itu-t-sg-13', u'itu-t-sg-15'],
    u'ITU-T SG 15 <tsbsg15@itu.int, greg.jones@itu.int>': [u'itu-t-sg-15'],
    u'ITU-T SG 15 Q9, Q10, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG 15, Q.14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T SG 15, Q9, Q11, Q12, Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG 17 Q.2/17': [u'itu-t-sg-17-q2'],
    u'ITU-T SG 4': [u'itu-t-sg-4'],
    u'ITU-T SG 4, 9, 11, 13, 16 and IETF': [u'itu-t-sg-4',u'itu-t-sg-9',u'itu-t-sg-11',u'itu-t-sg-13',u'itu-t-sg-16',u'ietf'],
    u'ITU-T SG-15': [u'itu-t-sg-15'],
    u'ITU-T SG-2': [u'itu-t-sg-2'],
    u'ITU-T SG11': [u'itu-t-sg-11'],
    u'ITU-T SG12, SG13, ATIS, TIA, IEC, IETF ccamp WG, IEEE 802.1, 802.3, OIF, Metro Ethernet Forum, ATM Forum': ['ccamp'],
    u'ITU-T SG13': [u'itu-t-sg-13'],
    u'ITU-T SG13 and SG15': [u'itu-t-sg-13', u'itu-t-sg-15'],
    u'ITU-T SG15': [u'itu-t-sg-15'],
    u'ITU-T SG15 (Optical Control Plane)': [u'itu-t-sg-15'],
    u'ITU-T SG15 Q10': [u'itu-t-sg-15-q10'],
    u'ITU-T SG15 Q10, Q12': [u'itu-t-sg-15-q10',u'itu-t-sg-15-q12'],
    u'ITU-T SG15 Q12': [u'itu-t-sg-15-q12'],
    u'ITU-T SG15 Q14': [u'itu-t-sg-15-q14'],
    u'ITU-T SG15 Q6': [u'itu-t-sg-15-q6'],
    u'ITU-T SG15 Q9, Q10, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15 Q9, Q11, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q11',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15 Question 12': [u'itu-t-sg-15-q12'],
    u'ITU-T SG15 Question 3': [u'itu-t-sg-15-q3'],
    u'ITU-T SG15 Question 6': [u'itu-t-sg-15-q6'],
    u'ITU-T SG15 Question 6, Question 12, and Question 14': [u'itu-t-sg-15-q6',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15 Question 9': [u'itu-t-sg-15-q9'],
    u'ITU-T SG15 Questions 12 and 14': [u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15 and Q14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T SG15, Q 9/15, Q 10/15, Q 12/15 and Q 14/15': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15, Q 9/15, Q10/15, Q12/15 and Q14/15': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG15, Q9, Q11, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q11',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'ITU-T SG16': [u'itu-t-sg-16'],
    u'ITU-T SG17': [u'itu-t-sg-17'],
    u'ITU-T SG17 TSB': [u'itu-t-sg-17-tsb'],
    u'ITU-T SG2': [u'itu-t-sg-2'],
    u'ITU-T SG2 <tsbsg2@itu.int>': [u'itu-t-sg-2'],
    u'ITU-T SG2 Q 1/2': [u'itu-t-sg-2-q1'],
    u'ITU-T SG4': [u'itu-t-sg-4'],
    u'ITU-T SG4, ITU-T SG15, ITU-T NGNM Focus group, 3GPP SA5, 3GPP2, ATIS/TMOC, TMF, IETF Management, ETSI BRAN': ['iesg'],
    u'ITU-T SGs, ITU-R WGs, ITU-D SG2 and the IETF': ['ietf'],
    u'ITU-T SGs: 2 (info), 4, 9, 11, 12, 13, 17, 19; ITU-R SGs: 1, 4, 5, 6; ITU-D SG 2; Focus Group on \u2018From/In/To Cars II\u2019 (ITU-T SG 12); ISO TC 22 SC3 and TC 204 ; IEEE 802, 802.11 (WiFi), 802.15.1 (Bluetooth); AUTOSAR WPII-1.1, OSGi VEG, IrDA and JSR298 Tele': ['ietf'],
    u'ITU-T SQ15 Question 14': [u'itu-t-sg-15-q14'],
    u'ITU-T Study Group 11': [u'itu-t-sg-11'],
    u'ITU-T Study Group 11 <tsg11gen@itu.int>': [u'itu-t-sg-11'],
    u'ITU-T Study Group 13': [u'itu-t-sg-13'],
    u'ITU-T Study Group 15': [u'itu-t-sg-15'],
    u'ITU-T Study Group 15 <greg.jones@itu.int>': [u'itu-t-sg-15'],
    u'ITU-T Study Group 15 Q4 <rlstuart@ieee.org>': [u'itu-t-sg-15-q4'],
    u'ITU-T Study Group 15 Question 14': [u'itu-t-sg-15-q14'],
    u'ITU-T Study Group 15 Question 3': [u'itu-t-sg-15-q3'],
    u'ITU-T Study Group 15 Question 6': [u'itu-t-sg-15-q6'],
    u'ITU-T TSAG External Relations Group': [u'itu-t-tsag'],
    u'ITU-T Working Party 3/13 and ITU-T Question 11/13': [u'itu-t-sg-13-wp3',u'itu-t-sg-13-q11'],
    u'ITU-T and ITU-T Study Group 13': [u'itu-t', u'itu-t-sg-13'],
    u'ITU-T, ITU SG13': [u'itu-t', u'itu-t-sg-13'],
    u'ITU-T-SG13': [u'itu-t-sg-13'],
    u'ITU-T/FG Cloud': ['itu-t-fg-cloud'],
    u'ITU-T/SG11': [u'itu-t-sg-11'],
    u'ITU-T/Study Group 11': [u'itu-t-sg-11'],
    u'Kam Lam, Rapporteur for Question 14 of ITU-T SG15': [u'itu-t-sg-15-q14'],
    u'Kam Lam, Rapporteur for Question 14 of ITU-T Study Group 15': [u'itu-t-sg-15-q14'],
    u'Lyndon Ong (lyong@ciena.com)': [u'sigtran'],
    u'MFA Forum': ['mfa-forum'],
    u'MPLS and Frame Relay Alliance': ['mfa'],
    u'Mr. Kam Lam, Rapporteur for Question 14 of ITU-T Study Group 15': [u'itu-t-sg-15-q14'],
    u'National, Multi-National or Regional Organizations': ['nmnro'],
    u'OMA': [u'oma'],
    u'OMA MEM': [u'oma-mwg-mem'],
    u'OMA MWG': [u'oma-mwg'],
    u'OMA MWG MEM Sub Working Group': [u'oma-mwg-mem'],
    u'OMA TP': [u'oma-tp'],
    u'OPS ADs (Randy Bush and Bert Wijnen)': [u'ops'],
    u'OPS Area Director Bert Wijnen': [u'ops'],
    u'Open IPTV Forum': ['opif'],
    u'Open Mobile Alliance Broadcasting  Working Group': [u'oma-bcast'],
    u'Open Mobile Alliance, PAG Working Group': [u'oma-pag-wg'],
    u'PDNR ITU-R M.[IP CHAR]': ['ietf'], # pending robert
    u'PWE WG': ['pwe3'],
    u'Phase 1 report to SG 4': ['ops'],
    u'Q7/13': [u'itu-t-sg-13-q7'],
    u'Rao Cherukuri, Chair MPLS and Frame Relay Alliance Technical Committee': ['mfa'],
    u'Rao Cherukuri, Chairman, MPLS and Frame Relay Alliance Technical Committee': ['mfa'],
    u'SA2, T2, OMA TP, S3': ['3gpp-tsgsa-sa2','3gpp-tsgt-wg2',u'oma-tp','3gpp-tsgsa-sa3'],
    u'SAVI WG, V6OPS WG, OPS AREA,  INT AREA': [u'savi', u'v6ops', u'ops', u'int'],
    u'SC 29/WG11': [u'iso-iec-jtc1-sc29-wg11'],
    u'SC29/WG11': [u'iso-iec-jtc1-sc29-wg11'],
    u'SG 15,Questions 3,9, 11,12, 14 and WP 3/15': [u'itu-t-sg-15-q3',u'itu-t-sg-15-q9',u'itu-t-sg-15-q11',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14',u'itu-t-sg-15-wp3'],
    u'SG-13, Q.3/13, Q.9/13 and TSAG': [u'itu-t-sg-13-q3',u'itu-t-sg-13-q9',u'itu-t-tsag'],
    u'SG13, SG13 WP4': [u'itu-t-sg-13',u'itu-t-sg-13-wp4'],
    u'SG15 Q9': [u'itu-t-sg-15-q9'],
    u'SG15, Q9, Q10, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'SG15, Q9, Q10, Q12, Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'SG15, Q9, Q10, Q12, and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q10',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'SG15, Q9, Q11, Q12 and Q14': [u'itu-t-sg-15-q9',u'itu-t-sg-15-q11',u'itu-t-sg-15-q12',u'itu-t-sg-15-q14'],
    u'SG17, SG13, SG11, JCA-NID, ETSI TISPAN WG4, 3GPP TSG CT4, IESG': ['iesg'],
    u'SG4': [u'itu-t-sg-4'],
    u'SIP aand SIPPING WGs': [u'sip', u'sipping'],
    u'SIP, SIPPING, SIMPLE WGs': [u'sip', u'sipping', u'simple'],
    u'SUB-IP and Transport Areas': [u'sub', u'tsv'],
    u'Scott Bradner': ['ccamp','isis','sigtran'],
    u'Scott Bradner (sob@harvard.edu)': ['iesg'],  # placeholder for explicit mappings
    u'Scott Bradner (sob@harvard.edu) Done': ['mpls'],
    u'SubIP ADs (sob@harvard.edu,bwijnen@lucent.com)': [u'sub'],
    u'TEWG, MPLS, CCAMP WGs': [u'tewg', u'mpls', u'ccamp'],
    u'TRILL WG co-chairs and IEEE-IETF liaisons': ['trill'],
    u'TRILL WG co-chairs, ADs, and IEEE-IETF liaisons': ['trill'],
    u'TSG-X Corr to IETF re MIP6 Bootstrapping': ['int'],
    u'The IAB': [u'iab'],
    u'The IESG': [u'iesg'],
    u'The IESG and the IAB': [u'iesg', u'iab'],
    u'The IETF': [u'ietf'],
    u'Tom Taylor (taylor@nortelnetworks.com), Megaco WG Chair': [u'megaco'],
    u'Transport ADs (Allison Mankin and Scott Bradner)': [u'tsv'],
    u'Transport Area Directors': [u'tsv'],
    u'Unicode Consortium': ['unicode'],
    u'Unicode Technical Committee': ['unicode'],
    u'Various IETF WGs': ['mobileip','pppext','avt'],
    u'W3C Geolocation WG': ['w3c-geolocation-wg'],
    u'W3C Geolocation Working Group': ['w3c-geolocation-wg'],
    u'W3C Multimedia Interaction Work Group': ['w3c-mmi'],
    u'WiFi Alliance and Wireless Broadband Alliance': ['wifi-alliance','wba'],
    u'chair@ietf.org': [u'ietf'],
    u'gonzalo.camarillo@ericsson.com': ['ietf'],
    u'tsbdir@itu.int': ['itu-t']
}

FROM_NAME_MAPPING = {
    u'3GPP TSG RAN WG2': ['3gpp-tsgran-ran2'],
    u'<unknown body 0>': ['itu-t-sg-13'],
    u'ATIS': ['atis'],
    u'ATM Forum': [u'atm-forum'],
    u'ATM Forum AIC WG': [u'afic'],
    u'BBF': [u'broadband-forum'],
    u'DSL Forum': [u'dsl-forum'],
    u'EPCGlobal': [u'epcglobal'],
    u'ETSI': ['etsi'],
    u'ETSI EMTEL': ['etsi-emtel'],
    u'ETSI TC HF': ['etsi-tc-hf'],
    u'ETSI TISPAN': ['etsi-tispan'],
    u'ETSI TISPAN WG5': ['etsi-tispan-wg5'],
    u'Femto Forum': ['femto-forum'],
    u'GSMA WLAN': ['gsma-wlan'],
    u'IEEE 802': [u'ieee-802'],
    u'IEEE 802.11': [u'ieee-802-11'],
    u'IEEE 802.21': [u'ieee-802-21'],
    u'IETF ADSL MIB': [u'adslmib'],
    u'IETF MEAD Team': [u'mead'],
    u'IETF Mead Team': [u'mead'],
    u'IETF liaison on MPLS': [u'mpls'],
    u'INCITS T11.5': ['incits-t11-5'],
    u'ISO/IEC JTC 1 SC 29/WG 11': [u'iso-iec-jtc1-sc29-wg11'],
    u'ISO/IEC JTC 1 SGSN': ['iso-iec-jtc1-sgsn'],
    u'ISO/IEC JTC 1/SC31/WG 4/SG 1': ['iso-iec-jtc1-sc31-wg4'],
    u'ISO/IEC JTC 1/WG 7': [u'iso-iec-jtc1-wg7'],
    u'ISO/IEC JTC SC 29/WG1': [u'iso-iec-jtc1-sc29-wg1'],
    u'ISO/IEC JTC SC 29/WG11': [u'iso-iec-jtc1-sc29-wg11'],
    u'ISO/IEC JTC1/SC29/WG11': [u'iso-iec-jtc1-sc29-wg11'],
    u'ISO/IEC JTC1/SC6': [u'iso-iec-jtc1-sc6'],
    u'ITU': [u'itu'],
    u'ITU IPv6 Group': [u'itu-t-ipv6-group'],
    u'ITU-Q.14/15': [u'itu-t-sg-15-q14'],
    u'ITU-R WP 5A': [u'itu-r-wp5a'],
    u'ITU-R WP 5D': [u'itu-r-wp5d'],
    u'ITU-R WP8A': [u'itu-r-wp8a'],
    u'ITU-R WP8F': [u'itu-r-wp8f'],
    u'ITU-SC29': ['iso-iec-jtc1-sc29-wg1'],
    u'ITU-SG 15': [u'itu-t-sg-15'],
    u'ITU-SG 7': [u'itu-t-sg-7'],
    u'ITU-SG 8': [u'itu-t-sg-8'],
    u'ITU-T FG Cloud': [u'itu-t-fg-cloud'],
    u'ITU-T FG IPTV': [u'itu-t-fg-iptv'],
    u'ITU-T Q.5/13': [u'itu-t-sg-13-q5'],
    u'ITU-T SG 15 Q14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T SG 15 WP 1': [u'itu-t-sg-15-wp1'],
    u'ITU-T SG 15, Q.11': [u'itu-t-sg-15-q11'],
    u'ITU-T SG 15, Q.14/15': [u'itu-t-sg-15-q14'],
    u'ITU-T SG 4': [u'itu-t-sg-4'],
    u'ITU-T SG 6': [u'itu-t-sg-6'],
    u'ITU-T SG 7': [u'itu-t-sg-7'],
    u'ITU-T SG 9': [u'itu-t-sg-9'],
    u'ITUT-T SG 16': [u'itu-t-sg-16'],
    u'JCA-IdM': [u'itu-t-jca-idm'],
    u'MFA Forum': ['mfa-forum'],
    u'MPEG': ['mpeg'],
    u'MPLS Forum': ['mpls-forum'],
    u'MPLS and FR Alliance': ['mfa'],
    u'MPLS and Frame Relay Alliance': ['mfa'],
    u'NANP LNPA WG': ['nanc-lnpa-wg'],
    u'NGN Management Focus Group': ['itu-t-ngnmfg'],
    u'OMA': [u'oma'],
    u'OMA COM-CAB SWG': [u'oma-com-cab'],
    u'OMA COM-CPM Group': [u'oma-com-cpm'],
    u'Open IPTV Forum': ['opif'],
    u'SC 29/WG 1': [u'iso-iec-jtc1-sc29-wg1'],
    u'SC 29/WG 11': [u'iso-iec-jtc1-sc29-wg11'],
    u'SC29 4559': [u'iso-iec-jtc1-sc29-wg11'],
    u'SC29 4561': [u'iso-iec-jtc1-sc29-wg11'],
    u'SIP, SIPPING, SIMPLE WGs': [u'sip', u'sipping', u'simple'],
    u'T1M1': ['t1m1'],
    u'T1S1': ['t1s1'],
    u'T1X1 cc: ITU-T Q. 14/15 (for info)': ['t1x1','itu-t-sg-15-q14'],
    u'TIA': ['tia'],
    u'TMOC': ['tmoc'],
    u'The IAB': [u'iab'],
    u'The IESG': [u'iesg'],
    u'The IESG and the IAB': [u'iesg', u'iab'],
    u'The IETF': [u'ietf'],
    u'W3C Geolocation WG': ['w3c-geolocation-wg'],
    u'WIG': ['wig']
}

DEFAULT_POC = {
    '3gpp':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgct':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgct-ct1':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgct-ct4':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgran':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgran-ran2':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgsa':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgsa-sa2':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgsa-sa3':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgsa-sa4':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    '3gpp-tsgt-wg2':'georg.mayer.huawei@gmx.com,3GPPLiaison@etsi.org',
    'ieee-802':'Paul Nikolich <p.nikolich@ieee.org>,Pat Thaler <pthaler@broadcom.com>',
    'ieee-802-1':'Paul Nikolich <p.nikolich@ieee.org>,Glen Parsons <glenn.parsons@ericsson.com>,John Messenger <jmessenger@advaoptical.com>',
    'ieee-802-11':'Dorothy Stanley <dstanley@agere.com>, Adrian Stephens <adrian.p.stephens@intel.com>',
    'cablelabs':'Greg White <g.white@CableLabs.com>',
    'iso-iec-jtc1-sc29':'Watanabe Shinji <watanabe@itscj.ipsj.or.jp>',
    'iso-iec-jtc1-sc29-wg1':'Watanabe Shinji <watanabe@itscj.ipsj.or.jp>',
    'iso-iec-jtc1-sc29-wg11':'Watanabe Shinji <watanabe@itscj.ipsj.or.jp>',
    'unicode':'Richard McGowan <rick@unicode.org>',
    'isotc46':'sabine.donnardcusse@afnor.org',
    'w3c':u'Wendy Seltzer <wseltzer@w3.org>,Philippe Le Hégaret <plh@w3.org>',
    # change to m3aawg
    'maawg':'Mike Adkins <madkins@fb.com>,technical-chair@mailman.m3aawg.org',
    'ecma-tc39':'John Neuman <johnneumann.openstrat@gmail.com>,Istvan Sebestyen <istvan@ecma-interational.org>',
}
    