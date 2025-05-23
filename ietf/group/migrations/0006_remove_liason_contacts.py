# Copyright The IETF Trust 2025, All Rights Reserved

from collections import defaultdict

from django.db import migrations

from ietf.person.name import plain_name


def get_plain_name(person):
    return person.plain or plain_name(person.name)


def forward(apps, schema_editor):
    """Removes liaison_contact and liaison_cc_contact roles from all groups

    The IAB has decided to remove the liaison_contact and liaison_cc_contact
    role concept from the datatracker as the roles are not well understood
    and have not been being maintained.
    """
    Role = apps.get_model("group", "Role")
    GroupEvent = apps.get_model("group", "GroupEvent")
    for role_name in ["liaison_contact", "liaison_cc_contact"]:
        groups = defaultdict(list)
        role_qs = Role.objects.filter(name_id=role_name)
        for role in role_qs:
            groups[role.group].append(role)
        for group in groups:
            desc = f"Removed {role_name}: {', '.join([get_plain_name(role.person) for role in groups[group]])}"
            GroupEvent.objects.create(
                group=group,
                by_id=1,  # (System)
                desc=desc,
            )
        role_qs.delete()


def reverse(apps, schema_editor):
    """Intentionally does nothing"""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("group", "0005_remove_sdo_authorized_individuals"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]


# At the time this migration was created, it would remove these objects
# {"liaison_contacts":[
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 56, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 56, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp
#   { "role_name": "liaison_contact", "person_id": 127959, "group_id": 57, "email": "mahendra@qualcomm.com" }, # Mahendran Ac is Liaison Contact in 3gpp2
#   { "role_name": "liaison_contact", "person_id": 111440, "group_id": 2026, "email": "georg.mayer.huawei@gmx.com" }, # Georg Mayer is Liaison Contact in 3gpp-tsgct
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2026, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgct
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2027, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgct-ct1
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2027, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgct-ct1
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2410, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgct-ct3
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2410, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgct-ct3
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2028, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgct-ct4
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2028, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgct-ct4
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2029, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgran
#   { "role_name": "liaison_contact", "person_id": 111440, "group_id": 2029, "email": "georg.mayer.huawei@gmx.com" }, # Georg Mayer is Liaison Contact in 3gpp-tsgran
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2030, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgran-ran2
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2030, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgran-ran2
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2023, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgsa
#   { "role_name": "liaison_contact", "person_id": 111440, "group_id": 2023, "email": "georg.mayer.huawei@gmx.com" }, # Georg Mayer is Liaison Contact in 3gpp-tsgsa
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2024, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgsa-sa2
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2024, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgsa-sa2
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2025, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgsa-sa3
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2025, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgsa-sa3
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 1902, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgsa-sa4
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 1902, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgsa-sa4
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2031, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in 3gpp-tsgt-wg2
#   { "role_name": "liaison_contact", "person_id": 107737, "group_id": 2031, "email": "lionel.morand@orange.com" }, # Lionel Morand is Liaison Contact in 3gpp-tsgt-wg2
#   { "role_name": "liaison_contact", "person_id": 106345, "group_id": 1396, "email": "Menachem.Dodge@ecitele.com" }, # Menachem Dodge is Liaison Contact in adslmib
#   { "role_name": "liaison_contact", "person_id": 108054, "group_id": 1956, "email": "shengjiang@bupt.edu.cn" }, # Sheng Jiang is Liaison Contact in anima
#   { "role_name": "liaison_contact", "person_id": 11834, "group_id": 1956, "email": "tte@cs.fau.de" }, # Toerless Eckert is Liaison Contact in anima
#   { "role_name": "liaison_contact", "person_id": 21684, "group_id": 1805, "email": "barryleiba@computer.org" }, # Barry Leiba is Liaison Contact in appsawg
#   { "role_name": "liaison_contact", "person_id": 102154, "group_id": 1805, "email": "alexey.melnikov@isode.com" }, # Alexey Melnikov is Liaison Contact in appsawg
#   { "role_name": "liaison_contact", "person_id": 107279, "group_id": 1805, "email": "yaojk@cnnic.cn" }, # Jiankang Yao is Liaison Contact in appsawg
#   { "role_name": "liaison_contact", "person_id": 100754, "group_id": 941, "email": "tom.taylor@rogers.com" }, # Tom Taylor is Liaison Contact in avt
#   { "role_name": "liaison_contact", "person_id": 105873, "group_id": 941, "email": "ron.even.tlv@gmail.com" }, # Roni Even is Liaison Contact in avt
#   { "role_name": "liaison_contact", "person_id": 105097, "group_id": 1813, "email": "keith.drage@alcatel-lucent.com" }, # Keith Drage is Liaison Contact in avtext
#   { "role_name": "liaison_contact", "person_id": 101923, "group_id": 1813, "email": "jonathan@vidyo.com" }, # Jonathan Lennox is Liaison Contact in avtext
#   { "role_name": "liaison_contact", "person_id": 108279, "group_id": 1960, "email": "martin.vigoureux@alcatel-lucent.com" }, # Martin Vigoureux is Liaison Contact in bess
#   { "role_name": "liaison_contact", "person_id": 109666, "group_id": 66, "email": "g.white@cablelabs.com" }, # Greg White is Liaison Contact in cablelabs
#   { "role_name": "liaison_contact", "person_id": 117421, "group_id": 1933, "email": "chairman@dmtf.org" }, # Winston Bumpus is Liaison Contact in dmtf
#   { "role_name": "liaison_contact", "person_id": 127961, "group_id": 1739, "email": "statements@ietf.org" }, # statements@ietf.org is Liaison Contact in drinks
#   { "role_name": "liaison_contact", "person_id": 109505, "group_id": 1787, "email": "bernie@ietf.hoeneisen.ch" }, # Bernie Hoeneisen is Liaison Contact in e2md
#   { "role_name": "liaison_contact", "person_id": 109059, "group_id": 1787, "email": "ray.bellis@nominet.org.uk" }, # Ray Bellis is Liaison Contact in e2md
#   { "role_name": "liaison_contact", "person_id": 116529, "group_id": 1919, "email": "istvan@ecma-interational.org" }, # Istvan Sebestyen is Liaison Contact in ecma-tc39
#   { "role_name": "liaison_contact", "person_id": 127964, "group_id": 1919, "email": "johnneumann.openstrat@gmail.com" }, # John Neuman is Liaison Contact in ecma-tc39
#   { "role_name": "liaison_contact", "person_id": 106012, "group_id": 1643, "email": "marc.linsner@cisco.com" }, # Marc Linsner is Liaison Contact in ecrit
#   { "role_name": "liaison_contact", "person_id": 107084, "group_id": 1643, "email": "rmarshall@telecomsys.com" }, # Roger Marshall is Liaison Contact in ecrit
#   { "role_name": "liaison_contact", "person_id": 116363, "group_id": 1915, "email": "e2nasupport@etsi.org" }, # Sonia Compans is Liaison Contact in etsi-e2na
#   { "role_name": "liaison_contact", "person_id": 126473, "group_id": 2261, "email": "isgsupport@etsi.org" }, # Sonia Compan is Liaison Contact in etsi-isg-sai
#   { "role_name": "liaison_contact", "person_id": 128316, "group_id": 2301, "email": "GSMALiaisons@gsma.com" }, # David Pollington is Liaison Contact in gsma-ztc
#   { "role_name": "liaison_contact", "person_id": 3056, "group_id": 1875, "email": "shares@ndzh.com" }, # Susan Hares is Liaison Contact in i2rs
#   { "role_name": "liaison_contact", "person_id": 105046, "group_id": 1875, "email": "jhaas@pfrc.org" }, # Jeffrey Haas is Liaison Contact in i2rs
#   { "role_name": "liaison_contact", "person_id": 120845, "group_id": 61, "email": "tale@dd.org" }, # David Lawrence is Liaison Contact in icann-board-of-directors
#   { "role_name": "liaison_contact", "person_id": 112851, "group_id": 2105, "email": "pthaler@broadcom.com" }, # Patricia Thaler is Liaison Contact in ieee-802
#   { "role_name": "liaison_contact", "person_id": 127968, "group_id": 2105, "email": "p.nikolich@ieee.org" }, # Paul Nikolich is Liaison Contact in ieee-802
#   { "role_name": "liaison_contact", "person_id": 19651, "group_id": 63, "email": "glenn.parsons@ericsson.com" }, # Glenn Parsons is Liaison Contact in ieee-802-1
#   { "role_name": "liaison_contact", "person_id": 123875, "group_id": 63, "email": "JMessenger@advaoptical.com" }, # John Messenger is Liaison Contact in ieee-802-1
#   { "role_name": "liaison_contact", "person_id": 127968, "group_id": 63, "email": "p.nikolich@ieee.org" }, # Paul Nikolich is Liaison Contact in ieee-802-1
#   { "role_name": "liaison_contact", "person_id": 117415, "group_id": 1862, "email": "Adrian.P.Stephens@intel.com" }, # Adrian Stephens is Liaison Contact in ieee-802-11
#   { "role_name": "liaison_contact", "person_id": 106284, "group_id": 1862, "email": "dstanley@agere.com" }, # Dorothy Stanley is Liaison Contact in ieee-802-11
#   { "role_name": "liaison_contact", "person_id": 128345, "group_id": 2302, "email": "liaison@iowngf.org" }, # Forum Iown is Liaison Contact in iown-global-forum
#   { "role_name": "liaison_contact", "person_id": 117428, "group_id": 1939, "email": "walter.fumy@bdr.de" }, # Walter Fumy is Liaison Contact in iso-iec-jtc1-sc27
#   { "role_name": "liaison_contact", "person_id": 117429, "group_id": 1939, "email": "krystyna.passia@din.de" }, # Krystyna Passia is Liaison Contact in iso-iec-jtc1-sc27
#   { "role_name": "liaison_contact", "person_id": 151289, "group_id": 50, "email": "koike@itscj.ipsj.or.jp" }, # Mayumi Koike is Liaison Contact in iso-iec-jtc1-sc29
#   { "role_name": "liaison_contact", "person_id": 151289, "group_id": 2110, "email": "koike@itscj.ipsj.or.jp" }, # Mayumi Koike is Liaison Contact in iso-iec-jtc1-sc29-wg1
#   { "role_name": "liaison_contact", "person_id": 114435, "group_id": 74, "email": "watanabe@itscj.ipsj.or.jp" }, # Shinji Watanabe is Liaison Contact in iso-iec-jtc1-sc29-wg11
#   { "role_name": "liaison_contact", "person_id": 112106, "group_id": 49, "email": "jooran@kisi.or.kr" }, # Jooran Lee is Liaison Contact in iso-iec-jtc1-sc6
#   { "role_name": "liaison_contact", "person_id": 113587, "group_id": 49, "email": "dykim@cnu.kr" }, # Chungnam University is Liaison Contact in iso-iec-jtc1-sc6
#   { "role_name": "liaison_contact", "person_id": 117427, "group_id": 1938, "email": "secretariat@jtc1-sc7.org" }, # Witold Suryn is Liaison Contact in iso-iec-jtc1-sc7
#   { "role_name": "liaison_contact", "person_id": 117426, "group_id": 1938, "email": "chair@jtc1-sc7.org" }, # Francois Coallier is Liaison Contact in iso-iec-jtc1-sc7
#   { "role_name": "liaison_contact", "person_id": 127971, "group_id": 68, "email": "sabine.donnardcusse@afnor.org" }, # sabine.donnardcusse@afnor.org is Liaison Contact in isotc46
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2057, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1890, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-r
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2058, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-r-wp5a
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2059, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-r-wp5d
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2060, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-r-wp8a
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2061, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-r-wp8f
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 51, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2063, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-fg-cloud
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1860, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-fg-dist
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2064, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-fg-iptv
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2065, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-fg-ngnm
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2062, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-ipv6-group
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1872, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-jca-cloud
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1874, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-jca-cop
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2066, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-jca-idm
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1927, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-jca-sdn
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 65, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-mpls
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 52, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-ngn
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2067, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-ngnmfg
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 77, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-11
#   { "role_name": "liaison_contact", "person_id": 128236, "group_id": 77, "email": "denis.andreev@itu.int" }, # Denis ANDREEV is Liaison Contact in itu-t-sg-11
#   { "role_name": "liaison_contact", "person_id": 107300, "group_id": 77, "email": "tatiana.kurakova@itu.int" }, # Tatiana Kurakova is Liaison Contact in itu-t-sg-11
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2074, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-11-q5
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2075, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-11-wp2
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 84, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-12
#   { "role_name": "liaison_contact", "person_id": 102900, "group_id": 84, "email": "acmorton@att.com" }, # Al Morton is Liaison Contact in itu-t-sg-12
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2076, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-12-q12
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2077, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-12-q17
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2082, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-q11
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2078, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-q3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2079, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-q5
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2080, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-q7
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2081, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-q9
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2083, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-wp3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2084, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-wp4
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2085, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-13-wp5
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2086, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-14
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 62, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2087, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q1
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2092, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q10
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2093, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q11
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2094, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q12
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2095, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q14
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2096, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q15
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2088, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2089, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q4
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2090, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q6
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2091, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-q9
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2097, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-wp1
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2098, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-15-wp3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 72, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-16
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2101, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-16-q10
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1987, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-16-q3
#   { "role_name": "liaison_contact", "person_id": 118539, "group_id": 1987, "email": "rosa.angelesleondev@itu.int" }, # Rosa De Vivero is Liaison Contact in itu-t-sg-16-q3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2099, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-16-q8
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2100, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-16-q9
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 76, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-17
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2102, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-17-q2
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1937, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-17-q4
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1954, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-17-tsb
#   { "role_name": "liaison_contact", "person_id": 12898, "group_id": 1954, "email": "youki-k@is.aist-nara.ac.jp" }, # Youki Kadobayashi is Liaison Contact in itu-t-sg-17-tsb
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 78, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-2
#   { "role_name": "liaison_contact", "person_id": 127962, "group_id": 78, "email": "dr.guinena@ntra.gov.eg" }, # dr.guinena@ntra.gov.eg is Liaison Contact in itu-t-sg-2
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2103, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-20
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2073, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-2-q1
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 79, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-3
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2068, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-4
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2000, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-5
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2069, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-6
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2070, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-7
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2071, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-8
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 2072, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-sg-9
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 82, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-tsag
#   { "role_name": "liaison_contact", "person_id": 127957, "group_id": 82, "email": "tsbtsag@itu.int" }, # Bilel Jamoussi is Liaison Contact in itu-t-tsag
#   { "role_name": "liaison_cc_contact", "person_id": 127958, "group_id": 1846, "email": "itu-t-liaison@iab.org" }, # itu-t liaison is Liaison CC Contact in itu-t-wp-5-13
#   { "role_name": "liaison_contact", "person_id": 10083, "group_id": 1882, "email": "paul.hoffman@vpnc.org" }, # Paul Hoffman is Liaison Contact in json
#   { "role_name": "liaison_contact", "person_id": 111178, "group_id": 1882, "email": "mamille2@cisco.com" }, # Matthew Miller is Liaison Contact in json
#   { "role_name": "liaison_contact", "person_id": 106881, "group_id": 1593, "email": "vach.kompella@alcatel.com" }, # Vach Kompella is Liaison Contact in l2vpn
#   { "role_name": "liaison_contact", "person_id": 19987, "group_id": 1593, "email": "danny@arbor.net" }, # Danny McPherson is Liaison Contact in l2vpn
#   { "role_name": "liaison_contact", "person_id": 2329, "group_id": 1593, "email": "stbryant@cisco.com" }, # Stewart Bryant is Liaison Contact in l2vpn
#   { "role_name": "liaison_contact", "person_id": 101552, "group_id": 1593, "email": "Shane.Amante@Level3.com" }, # Shane Amante is Liaison Contact in l2vpn
#   { "role_name": "liaison_contact", "person_id": 110305, "group_id": 1877, "email": "jason.weil@twcable.com" }, # Jason Weil is Liaison Contact in lmap
#   { "role_name": "liaison_contact", "person_id": 6699, "group_id": 1877, "email": "dromasca@avaya.com" }, # Dan Romascanu is Liaison Contact in lmap
#   { "role_name": "liaison_contact", "person_id": 127969, "group_id": 69, "email": "madkins@fb.com" }, # Mike Adkins is Liaison Contact in maawg
#   { "role_name": "liaison_contact", "person_id": 127970, "group_id": 69, "email": "technical-chair@mailman.m3aawg.org" }, # technical-chair@mailman.m3aawg.org is Liaison Contact in maawg
#   { "role_name": "liaison_contact", "person_id": 112512, "group_id": 75, "email": "rraghu@ciena.com" }, # Raghu Ranganathan is Liaison Contact in mef
#   { "role_name": "liaison_contact", "person_id": 119947, "group_id": 1755, "email": "mrw@lilacglade.org" }, # Margaret Cullen is Liaison Contact in mif
#   { "role_name": "liaison_contact", "person_id": 109884, "group_id": 1755, "email": "denghui02@hotmail.com" }, # Hui Deng is Liaison Contact in mif
#   { "role_name": "liaison_contact", "person_id": 128292, "group_id": 1936, "email": "james.olthoff@nist.gov" }, # James Olthoff is Liaison Contact in nist
#   { "role_name": "liaison_contact", "person_id": 104183, "group_id": 1537, "email": "john.loughney@nokia.com" }, # John Loughney is Liaison Contact in nsis
#   { "role_name": "liaison_contact", "person_id": 105786, "group_id": 1840, "email": "matthew.bocci@nokia.com" }, # Matthew Bocci is Liaison Contact in nvo3
#   { "role_name": "liaison_contact", "person_id": 112438, "group_id": 1840, "email": "bensons@queuefull.net" }, # Benson Schliesser is Liaison Contact in nvo3
#   { "role_name": "liaison_contact", "person_id": 107943, "group_id": 2296, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Liaison Contact in o3gpptsgran3
#   { "role_name": "liaison_contact", "person_id": 127966, "group_id": 1941, "email": "chet.ensign@oasis-open.org" }, # chet.ensign@oasis-open.org is Liaison Contact in oasis
#   { "role_name": "liaison_contact", "person_id": 117423, "group_id": 1935, "email": "soley@omg.org" }, # Richard Soley is Liaison Contact in omg
#   { "role_name": "liaison_contact", "person_id": 127963, "group_id": 1858, "email": "dan.pitt@opennetworkingfoundation.org" }, # dan.pitt@opennetworkingfoundation.org is Liaison Contact in onf
#   { "role_name": "liaison_contact", "person_id": 108304, "group_id": 1599, "email": "gunter.van_de_velde@nokia.com" }, # Gunter Van de Velde is Liaison Contact in opsec
#   { "role_name": "liaison_contact", "person_id": 111647, "group_id": 1599, "email": "kk@google.com" }, # Chittimaneni Kk is Liaison Contact in opsec
#   { "role_name": "liaison_contact", "person_id": 111656, "group_id": 1599, "email": "warren@kumari.net" }, # Warren Kumari is Liaison Contact in opsec
#   { "role_name": "liaison_contact", "person_id": 106471, "group_id": 1188, "email": "dbrungard@att.com" }, # Deborah Brungard is Liaison Contact in ospf
#   { "role_name": "liaison_contact", "person_id": 104198, "group_id": 1188, "email": "adrian@olddog.co.uk" }, # Adrian Farrel is Liaison Contact in ospf
#   { "role_name": "liaison_contact", "person_id": 104816, "group_id": 1188, "email": "akr@cisco.com" }, # Abhay Roy is Liaison Contact in ospf
#   { "role_name": "liaison_contact", "person_id": 10784, "group_id": 1188, "email": "acee@redback.com" }, # Acee Lindem is Liaison Contact in ospf
#   { "role_name": "liaison_contact", "person_id": 108123, "group_id": 1819, "email": "Gabor.Bajko@nokia.com" }, # Gabor Bajko is Liaison Contact in paws
#   { "role_name": "liaison_contact", "person_id": 106987, "group_id": 1819, "email": "br@brianrosen.net" }, # Brian Rosen is Liaison Contact in paws
#   { "role_name": "liaison_cc_contact", "person_id": 122823, "group_id": 1630, "email": "ketant.ietf@gmail.com" }, # Ketan Talaulikar is Liaison CC Contact in pce
#   { "role_name": "liaison_contact", "person_id": 125031, "group_id": 1630, "email": "andrew.stone@nokia.com" }, # Andrew Stone is Liaison Contact in pce
#   { "role_name": "liaison_contact", "person_id": 108213, "group_id": 1630, "email": "julien.meuric@orange.com" }, # Julien Meuric is Liaison Contact in pce
#   { "role_name": "liaison_contact", "person_id": 111477, "group_id": 1630, "email": "dd@dhruvdhody.com" }, # Dhruv Dhody is Liaison Contact in pce
#   { "role_name": "liaison_contact", "person_id": 112773, "group_id": 1701, "email": "lars.eggert@nokia.com" }, # Lars Eggert is Liaison Contact in pcn
#   { "role_name": "liaison_contact", "person_id": 12671, "group_id": 1437, "email": "adamson@itd.nrl.navy.mil" }, # Brian Adamson is Liaison Contact in rmt
#   { "role_name": "liaison_contact", "person_id": 100609, "group_id": 1437, "email": "lorenzo@vicisano.net" }, # Lorenzo Vicisano is Liaison Contact in rmt
#   { "role_name": "liaison_contact", "person_id": 115213, "group_id": 1730, "email": "maria.ines.robles@ericsson.com" }, # Ines Robles is Liaison Contact in roll
#   { "role_name": "liaison_contact", "person_id": 110721, "group_id": 1820, "email": "ted.ietf@gmail.com" }, # Ted Hardie is Liaison Contact in rtcweb
#   { "role_name": "liaison_contact", "person_id": 104294, "group_id": 1820, "email": "magnus.westerlund@ericsson.com" }, # Magnus Westerlund is Liaison Contact in rtcweb
#   { "role_name": "liaison_contact", "person_id": 105791, "group_id": 1820, "email": "fluffy@iii.ca" }, # Cullen Jennings is Liaison Contact in rtcweb
#   { "role_name": "liaison_contact", "person_id": 105906, "group_id": 1910, "email": "james.n.guichard@futurewei.com" }, # Jim Guichard is Liaison Contact in sfc
#   { "role_name": "liaison_contact", "person_id": 3862, "group_id": 1910, "email": "jmh@joelhalpern.com" }, # Joel Halpern is Liaison Contact in sfc
#   { "role_name": "liaison_contact", "person_id": 127960, "group_id": 1462, "email": "sipcore@ietf.org" }, # sipcore@ietf.org is Liaison Contact in sip
#   { "role_name": "liaison_contact", "person_id": 103769, "group_id": 1762, "email": "adam@nostrum.com" }, # Adam Roach is Liaison Contact in sipcore
#   { "role_name": "liaison_contact", "person_id": 108554, "group_id": 1762, "email": "pkyzivat@alum.mit.edu" }, # Paul Kyzivat is Liaison Contact in sipcore
#   { "role_name": "liaison_contact", "person_id": 103539, "group_id": 1542, "email": "gonzalo.camarillo@ericsson.com" }, # Gonzalo Camarillo is Liaison Contact in sipping
#   { "role_name": "liaison_contact", "person_id": 103612, "group_id": 1542, "email": "jf.mule@cablelabs.com" }, # Jean-Francois Mule is Liaison Contact in sipping
#   { "role_name": "liaison_contact", "person_id": 3862, "group_id": 1905, "email": "jmh@joelhalpern.com" }, # Joel Halpern is Liaison Contact in spring
#   { "role_name": "liaison_contact", "person_id": 109802, "group_id": 1905, "email": "aretana.ietf@gmail.com" }, # Alvaro Retana is Liaison Contact in spring
#   { "role_name": "liaison_contact", "person_id": 107172, "group_id": 1905, "email": "bruno.decraene@orange.com" }, # Bruno Decraene is Liaison Contact in spring
#   { "role_name": "liaison_contact", "person_id": 5376, "group_id": 1899, "email": "housley@vigilsec.com" }, # Russ Housley is Liaison Contact in stir
#   { "role_name": "liaison_contact", "person_id": 103961, "group_id": 1899, "email": "rjsparks@nostrum.com" }, # Robert Sparks is Liaison Contact in stir
#   { "role_name": "liaison_contact", "person_id": 117430, "group_id": 1940, "email": "admin@trustedcomputinggroup.org" }, # Lindsay Adamson is Liaison Contact in tcg
#   { "role_name": "liaison_contact", "person_id": 110932, "group_id": 1985, "email": "oscar.gonzalezdedios@telefonica.com" }, # Oscar de Dios is Liaison Contact in teas
#   { "role_name": "liaison_contact", "person_id": 10064, "group_id": 1985, "email": "lberger@labn.net" }, # Lou Berger is Liaison Contact in teas
#   { "role_name": "liaison_contact", "person_id": 114351, "group_id": 1985, "email": "vbeeram@juniper.net" }, # Vishnu Beeram is Liaison Contact in teas
#   { "role_name": "liaison_contact", "person_id": 117422, "group_id": 1934, "email": "j.hietala@opengroup.org" }, # Jim Hietala is Liaison Contact in the-open-group
#   { "role_name": "liaison_contact", "person_id": 106414, "group_id": 1709, "email": "yaakovjstein@gmail.com" }, # Yaakov Stein is Liaison Contact in tictoc
#   { "role_name": "liaison_contact", "person_id": 4857, "group_id": 1709, "email": "kodonog@pobox.com" }, # Karen O'Donoghue is Liaison Contact in tictoc
#   { "role_name": "liaison_contact", "person_id": 144713, "group_id": 2420, "email": "liaisons@tmforum.org" }, # liaisons@tmforum.org is Liaison Contact in tmforum
#   { "role_name": "liaison_contact", "person_id": 112773, "group_id": 1324, "email": "lars@eggert.org" }, # Lars Eggert is Liaison Contact in tsv
#   { "role_name": "liaison_contact", "person_id": 112104, "group_id": 53, "email": "rick@unicode.org" }, # Rick McGowan is Liaison Contact in unicode
#   { "role_name": "liaison_contact", "person_id": 105907, "group_id": 1864, "email": "stpeter@stpeter.im" }, # Peter Saint-Andre is Liaison Contact in videocodec
#   { "role_name": "liaison_contact", "person_id": 120261, "group_id": 54, "email": "wseltzer@w3.org" }, # Wendy Seltzer is Liaison Contact in w3c
#   { "role_name": "liaison_contact", "person_id": 112103, "group_id": 54, "email": "plh@w3.org" }, # Philippe Le Hégaret is Liaison Contact in w3c
#   { "role_name": "liaison_contact", "person_id": 107520, "group_id": 1957, "email": "shida@ntt-at.com" }, # Shida Schubert is Liaison Contact in webpush
#   { "role_name": "liaison_contact", "person_id": 110049, "group_id": 1957, "email": "jhildebr@cisco.com" }, # Joe Hildebrand is Liaison Contact in webpush
#   { "role_name": "liaison_contact", "person_id": 103769, "group_id": 1601, "email": "adam@nostrum.com" }, # Adam Roach is Liaison Contact in xcon
#   { "role_name": "liaison_contact", "person_id": 107520, "group_id": 1815, "email": "shida@ntt-at.com" }, # Shida Schubert is Liaison Contact in xrblock
#   { "role_name": "liaison_contact", "person_id": 6699, "group_id": 1815, "email": "dromasca@avaya.com" }, # Dan Romascanu is Liaison Contact in xrblock
# ]}
