# Copyright The IETF Trust 2025, All Rights Reserved

from collections import defaultdict

from django.db import migrations

from ietf.person.name import plain_name


def get_plain_name(person):
    return person.plain or plain_name(person.name)


def forward(apps, schema_editor):
    """Remove any 'auth' Role objects for groups of type 'sdo'

    The IAB has decided that the Authorized Individual concept for
    authorizing entry or management of liaison statments hasn't worked
    well - the roles for the groups are not being maintained, Instead,
    the concept will be removed and the liaison managers or secretariat
    (and soon the liaison coordinators) will operate the liaison tool
    on their behalf.
    """
    Role = apps.get_model("group", "Role")
    GroupEvent = apps.get_model("group", "GroupEvent")
    groups = defaultdict(list)
    role_qs = Role.objects.filter(name_id="auth", group__type_id="sdo")
    for role in role_qs:
        groups[role.group].append(role)
    for group in groups:
        desc = f"Removed Authorized Persons: {', '.join([get_plain_name(role.person) for role in groups[group]])}"
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
        ("group", "0004_modern_list_archive"),
    ]

    operations = [migrations.RunPython(forward, reverse)]


# At the time this migration was created, it would have removed these Role objects:
# { "authorized_individuals" : [
# {"person_id": 107937, "group_id": 56, "email": "hannu.hietalahti@nokia.com" }, # Hannu Hietalahti is Authorized Individual in 3gpp
# {"person_id": 107943, "group_id": 56, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Authorized Individual in 3gpp
# {"person_id": 112807, "group_id": 56, "email": "Paolo.Usai@etsi.org" }, # Paolo Usai is Authorized Individual in 3gpp
# {"person_id": 105859, "group_id": 56, "email": "atle.monrad@ericsson.com" }, # Atle Monrad is Authorized Individual in 3gpp
# {"person_id": 116149, "group_id": 1907, "email": "tsgsx_chair@3GPP2.org" }, # Xiaowu Zhao is Authorized Individual in 3gpp2-tsg-sx
# {"person_id": 120914, "group_id": 1902, "email": "ozgur.oyman@intel.com" }, # Ozgur Oyman is Authorized Individual in 3gpp-tsgsa-sa4
# {"person_id": 107943, "group_id": 1902, "email": "3GPPLiaison@etsi.org" }, # Susanna Kooistra is Authorized Individual in 3gpp-tsgsa-sa4
# {"person_id": 119203, "group_id": 1902, "email": "fanyanping@huawei.com" }, # Yanping Fan is Authorized Individual in 3gpp-tsgsa-sa4
# {"person_id": 112977, "group_id": 1902, "email": "tomas.frankkila@ericsson.com" }, # Tomas Frankkila is Authorized Individual in 3gpp-tsgsa-sa4
# {"person_id": 120240, "group_id": 2019, "email": "CM8655@att.com" }, # Peter Musgrove is Authorized Individual in atis-eloc-tf
# {"person_id": 120241, "group_id": 2019, "email": "Christian.Militeau@intrado.com" }, # Christian Militeau is Authorized Individual in atis-eloc-tf
# {"person_id": 120243, "group_id": 2019, "email": "ablasgen@atis.org" }, # Alexandra Blasgen is Authorized Individual in atis-eloc-tf
# {"person_id": 114696, "group_id": 67, "email": "KEN.KO@adtran.com" }, # Ken Ko is Authorized Individual in broadband-forum
# {"person_id": 119494, "group_id": 67, "email": "michael.fargano@centurylink.com" }, # Michael Fargano is Authorized Individual in broadband-forum
# {"person_id": 124318, "group_id": 67, "email": "joey.boyd@adtran.com" }, # Joey Boyd is Authorized Individual in broadband-forum
# {"person_id": 114762, "group_id": 67, "email": "bwelch@juniper.net" }, # Bill Welch is Authorized Individual in broadband-forum
# {"person_id": 112837, "group_id": 67, "email": "christophe.alter@orange.com" }, # Christophe Alter is Authorized Individual in broadband-forum
# {"person_id": 141083, "group_id": 2407, "email": "dan.middleton@intel.com" }, # Dan Middleton is Authorized Individual in confidential-computing-consortium
# {"person_id": 117421, "group_id": 1933, "email": "chairman@dmtf.org" }, # Winston Bumpus is Authorized Individual in dmtf
# {"person_id": 116529, "group_id": 1919, "email": "istvan@ecma-international.org" }, # Istvan Sebestyen is Authorized Individual in ecma-tc39
# {"person_id": 116363, "group_id": 1915, "email": "e2nasupport@etsi.org" }, # Sonia Compans is Authorized Individual in etsi-e2na
# {"person_id": 116862, "group_id": 2003, "email": "latif@ladid.lu" }, # Latif Ladid is Authorized Individual in etsi-isg-ip6
# {"person_id": 116283, "group_id": 2198, "email": "adrian.neal@vodafone.com" }, # Adrian Neal is Authorized Individual in etsi-isg-mec
# {"person_id": 119412, "group_id": 2004, "email": "jkfernic@uwaterloo.ca" }, # Jennifer Fernick is Authorized Individual in etsi-isg-qsc
# {"person_id": 122406, "group_id": 2165, "email": "d.lake@surrey.ac.uk" }, # David Lake is Authorized Individual in etsi-ngp
# {"person_id": 122407, "group_id": 2165, "email": "andy.sutton@ee.co.uk" }, # Andy Sutton is Authorized Individual in etsi-ngp
# {"person_id": 112609, "group_id": 2165, "email": "richard.li@futurewei.com" }, # Richard Li is Authorized Individual in etsi-ngp
# {"person_id": 122406, "group_id": 2177, "email": "d.lake@surrey.ac.uk" }, # David Lake is Authorized Individual in etsi-ngp-isp
# {"person_id": 112609, "group_id": 2177, "email": "richard.li@futurewei.com" }, # Richard Li is Authorized Individual in etsi-ngp-isp
# {"person_id": 122407, "group_id": 2177, "email": "andy.sutton@ee.co.uk" }, # Andy Sutton is Authorized Individual in etsi-ngp-isp
# {"person_id": 118527, "group_id": 1986, "email": "luca.pesando@telecomitalia.it" }, # Luca Pesando is Authorized Individual in etsi-ntech
# {"person_id": 118526, "group_id": 1986, "email": "NTECHsupport@etsi.org" }, # Sylwia Korycinska is Authorized Individual in etsi-ntech
# {"person_id": 116052, "group_id": 1904, "email": "Beniamino.gorini@alcatel-lucent.com" }, # Gorini Beniamino is Authorized Individual in etsi-tc-ee
# {"person_id": 19651, "group_id": 63, "email": "glenn.parsons@ericsson.com" }, # Glenn Parsons is Authorized Individual in ieee-802-1
# {"person_id": 107599, "group_id": 63, "email": "tony@jeffree.co.uk" }, # Tony Jeffree is Authorized Individual in ieee-802-1
# {"person_id": 117415, "group_id": 1862, "email": "Adrian.P.Stephens@intel.com" }, # Adrian Stephens is Authorized Individual in ieee-802-11
# {"person_id": 106284, "group_id": 1862, "email": "dstanley@arubanetworks.com" }, # Dorothy Stanley is Authorized Individual in ieee-802-11
# {"person_id": 114106, "group_id": 1871, "email": "r.b.marks@ieee.org" }, # Roger Marks is Authorized Individual in ieee-802-16
# {"person_id": 101753, "group_id": 1885, "email": "max.riegel@ieee.org" }, # Max Riegel is Authorized Individual in ieee-802-ec-omniran
# {"person_id": 113810, "group_id": 1859, "email": "jehrig@inventures.com" }, # John Ehrig is Authorized Individual in imtc
# {"person_id": 123010, "group_id": 48, "email": "Emil.Kowalczyk@orange.com" }, # Emil Kowalczyk is Authorized Individual in iso-iec-jtc1-sc2
# {"person_id": 11182, "group_id": 48, "email": "paf@netnod.se" }, # Patrik Fältström is Authorized Individual in iso-iec-jtc1-sc2
# {"person_id": 117429, "group_id": 1939, "email": "krystyna.passia@din.de" }, # Krystyna Passia is Authorized Individual in iso-iec-jtc1-sc27
# {"person_id": 117428, "group_id": 1939, "email": "walter.fumy@bdr.de" }, # Walter Fumy is Authorized Individual in iso-iec-jtc1-sc27
# {"person_id": 114435, "group_id": 74, "email": "watanabe@itscj.ipsj.or.jp" }, # Shinji Watanabe is Authorized Individual in iso-iec-jtc1-sc29-wg11
# {"person_id": 112106, "group_id": 49, "email": "jooran@kisi.or.kr" }, # Jooran Lee is Authorized Individual in iso-iec-jtc1-sc6
# {"person_id": 17037, "group_id": 49, "email": "dykim@comsun.chungnnam.ac.kr" }, # Dae Kim is Authorized Individual in iso-iec-jtc1-sc6
# {"person_id": 117426, "group_id": 1938, "email": "chair@jtc1-sc7.org" }, # Francois Coallier is Authorized Individual in iso-iec-jtc1-sc7
# {"person_id": 117427, "group_id": 1938, "email": "secretariat@jtc1-sc7.org" }, # Witold Suryn is Authorized Individual in iso-iec-jtc1-sc7
# {"person_id": 118769, "group_id": 2144, "email": "alexandre.petrescu@gmail.com" }, # Alexandre Petrescu is Authorized Individual in isotc204
# {"person_id": 115544, "group_id": 1890, "email": "sergio.buonomo@itu.int" }, # Sergio Buonomo is Authorized Individual in itu-r
# {"person_id": 122111, "group_id": 2157, "email": "h.mazar@atdi.com" }, # Haim Mazar is Authorized Individual in itu-r-wp-5c
# {"person_id": 115544, "group_id": 2157, "email": "sergio.buonomo@itu.int" }, # Sergio Buonomo is Authorized Individual in itu-r-wp-5c
# {"person_id": 112105, "group_id": 51, "email": "Malcolm.Johnson@itu.int" }, # Malcom Johnson is Authorized Individual in itu-t
# {"person_id": 113911, "group_id": 1860, "email": "martin.adolph@itu.int" }, # Martin Adolph is Authorized Individual in itu-t-fg-dist
# {"person_id": 122779, "group_id": 2180, "email": "Leo.Lehmann@bakom.admin.ch" }, # Leo Lehmann is Authorized Individual in itu-t-fg-imt-2020
# {"person_id": 103383, "group_id": 2180, "email": "peter.ashwoodsmith@huawei.com" }, # Peter Ashwood-Smith is Authorized Individual in itu-t-fg-imt-2020
# {"person_id": 107300, "group_id": 1872, "email": "tatiana.kurakova@itu.int" }, # Tatiana Kurakova is Authorized Individual in itu-t-jca-cloud
# {"person_id": 106224, "group_id": 1872, "email": "mmorrow@cisco.com" }, # Monique Morrow is Authorized Individual in itu-t-jca-cloud
# {"person_id": 105714, "group_id": 1874, "email": "martin.euchner@itu.int" }, # Martin Euchner is Authorized Individual in itu-t-jca-cop
# {"person_id": 106475, "group_id": 2170, "email": "khj@etri.re.kr" }, # Hyoung-Jun Kim is Authorized Individual in itu-t-jca-iot-scc
# {"person_id": 122491, "group_id": 2170, "email": "tsbjcaiot@itu.int" }, # ITU Tsb is Authorized Individual in itu-t-jca-iot-scc
# {"person_id": 122490, "group_id": 2170, "email": "fabio.bigi@virgilio.it" }, # Fabio Bigi is Authorized Individual in itu-t-jca-iot-scc
# {"person_id": 116952, "group_id": 1927, "email": "chengying10@chinaunicom.cn" }, # Ying Cheng is Authorized Individual in itu-t-jca-sdn
# {"person_id": 111205, "group_id": 1927, "email": "t-egawa@ct.jp.nec.com" }, # Takashi Egawa is Authorized Individual in itu-t-jca-sdn
# {"person_id": 107298, "group_id": 2178, "email": "tsbsg11@itu.int" }, # Arshey Odedra is Authorized Individual in itu-tsbsg-11
# {"person_id": 107300, "group_id": 77, "email": "tatiana.kurakova@itu.int" }, # Tatiana Kurakova is Authorized Individual in itu-t-sg-11
# {"person_id": 112573, "group_id": 77, "email": "stefano.polidori@itu.int" }, # Stefano Polidori is Authorized Individual in itu-t-sg-11
# {"person_id": 115401, "group_id": 84, "email": "spennock@rim.com" }, # Scott Pennock is Authorized Individual in itu-t-sg-12
# {"person_id": 114255, "group_id": 84, "email": "hiroshi.ota@itu.int" }, # Hiroshi Ota is Authorized Individual in itu-t-sg-12
# {"person_id": 113032, "group_id": 84, "email": "catherine.quinquis@orange.com" }, # Catherine Quinquis is Authorized Individual in itu-t-sg-12
# {"person_id": 113031, "group_id": 84, "email": "gunilla.berndtsson@ericsson.com" }, # Gunilla Berndtsson is Authorized Individual in itu-t-sg-12
# {"person_id": 113672, "group_id": 84, "email": "sarah.scott@itu.int" }, # Sarah Scott is Authorized Individual in itu-t-sg-12
# {"person_id": 122459, "group_id": 81, "email": "chan@etri.re.kr" }, # Kangchan Lee is Authorized Individual in itu-t-sg-13
# {"person_id": 107300, "group_id": 81, "email": "tatiana.kurakova@itu.int" }, # Tatiana Kurakova is Authorized Individual in itu-t-sg-13
# {"person_id": 109145, "group_id": 62, "email": "lihan@chinamobile.com" }, # Han Li is Authorized Individual in itu-t-sg-15
# {"person_id": 115875, "group_id": 62, "email": "mark.jones@xtera.com" }, # Mark Jones is Authorized Individual in itu-t-sg-15
# {"person_id": 115846, "group_id": 62, "email": "peter.stassar@huawei.com" }, # Peter Stassar is Authorized Individual in itu-t-sg-15
# {"person_id": 123452, "group_id": 62, "email": "sshew@ciena.com" }, # Stephen Shew is Authorized Individual in itu-t-sg-15
# {"person_id": 109312, "group_id": 62, "email": "huubatwork@gmail.com" }, # Huub van Helvoort is Authorized Individual in itu-t-sg-15
# {"person_id": 115874, "group_id": 62, "email": "tom.huber@tellabs.com" }, # Tom Huber is Authorized Individual in itu-t-sg-15
# {"person_id": 110799, "group_id": 62, "email": "koike.yoshinori@lab.ntt.co.jp" }, # Yoshinori Koike is Authorized Individual in itu-t-sg-15
# {"person_id": 110831, "group_id": 62, "email": "kam.lam@nokia.com" }, # Hing-Kam Lam is Authorized Individual in itu-t-sg-15
# {"person_id": 114255, "group_id": 62, "email": "hiroshi.ota@itu.int" }, # Hiroshi Ota is Authorized Individual in itu-t-sg-15
# {"person_id": 115874, "group_id": 62, "email": "tom.huber@coriant.com" }, # Tom Huber is Authorized Individual in itu-t-sg-15
# {"person_id": 123014, "group_id": 62, "email": "jessy.rouyer@nokia.com" }, # Jessy Rouyer is Authorized Individual in itu-t-sg-15
# {"person_id": 111160, "group_id": 62, "email": "ryoo@etri.re.kr" }, # Jeong-dong Ryoo is Authorized Individual in itu-t-sg-15
# {"person_id": 107296, "group_id": 62, "email": "greg.jones@itu.int" }, # Greg Jones is Authorized Individual in itu-t-sg-15
# {"person_id": 118539, "group_id": 72, "email": "rosa.angelesleondev@itu.int" }, # Rosa De Vivero is Authorized Individual in itu-t-sg-16
# {"person_id": 123169, "group_id": 72, "email": "garysull@microsoft.com" }, # Gary Sullivan is Authorized Individual in itu-t-sg-16
# {"person_id": 107746, "group_id": 72, "email": "hiwasaki.yusuke@lab.ntt.co.jp" }, # Yusuke Hiwasaki is Authorized Individual in itu-t-sg-16
# {"person_id": 108160, "group_id": 1987, "email": "Christian.Groves@nteczone.com" }, # Christian Groves is Authorized Individual in itu-t-sg-16-q3
# {"person_id": 118539, "group_id": 1987, "email": "rosa.angelesleondev@itu.int" }, # Rosa De Vivero is Authorized Individual in itu-t-sg-16-q3
# {"person_id": 124354, "group_id": 76, "email": "jhbaek@kisa.or.kr" }, # Jonghyun Baek is Authorized Individual in itu-t-sg-17
# {"person_id": 12898, "group_id": 1937, "email": "youki-k@is.aist-nara.ac.jp" }, # Youki Kadobayashi is Authorized Individual in itu-t-sg-17-q4
# {"person_id": 113593, "group_id": 79, "email": "maite.comasbarnes@itu.int" }, # Maite Barnes is Authorized Individual in itu-t-sg-3
# {"person_id": 122983, "group_id": 2000, "email": "cristina.bueti@itu.int" }, # Cristina Bueti is Authorized Individual in itu-t-sg-5
# {"person_id": 112573, "group_id": 2072, "email": "stefano.polidori@itu.int" }, # Stefano Polidori is Authorized Individual in itu-t-sg-9
# {"person_id": 113101, "group_id": 82, "email": "steve.trowbridge@alcatel-lucent.com" }, # Stephen Trowbridge is Authorized Individual in itu-t-tsag
# {"person_id": 20783, "group_id": 82, "email": "reinhard.scholl@itu.int" }, # Reinhard Scholl is Authorized Individual in itu-t-tsag
# {"person_id": 107300, "group_id": 1846, "email": "tatiana.kurakova@itu.int" }, # Tatiana Kurakova is Authorized Individual in itu-t-wp-5-13
# {"person_id": 112107, "group_id": 69, "email": "michael.oreirdan@maawg.org" }, # Michael O'Reirdan is Authorized Individual in maawg
# {"person_id": 121870, "group_id": 75, "email": "liaisons@mef.net" }, # Liaison Mef is Authorized Individual in mef
# {"person_id": 112510, "group_id": 75, "email": "nan@mef.net" }, # Nan Chen is Authorized Individual in mef
# {"person_id": 124306, "group_id": 75, "email": "jason.wolfe@bell.ca" }, # WOLFE Jason is Authorized Individual in mef
# {"person_id": 114454, "group_id": 75, "email": "mike.bencheck@siamasystems.com" }, # Mike Bencheck is Authorized Individual in mef
# {"person_id": 115327, "group_id": 1888, "email": "klaus.moschner@ngmn.org" }, # Klaus Moschner is Authorized Individual in ngmn
# {"person_id": 123305, "group_id": 1888, "email": "office@ngmn.org" }, # Office Ngmn is Authorized Individual in ngmn
# {"person_id": 115160, "group_id": 1888, "email": "jminlee@sk.com" }, # Jongmin Lee is Authorized Individual in ngmn
# {"person_id": 117424, "group_id": 1936, "email": "patrick.gallagher@nist.gov" }, # Patrick Gallagher is Authorized Individual in nist
# {"person_id": 117431, "group_id": 1941, "email": "chet.ensign@xn--oasis-open-vt6e.org" }, # Chet Ensign is Authorized Individual in oasis
# {"person_id": 120913, "group_id": 2142, "email": "james.walker@tatacommunications.com" }, # James Walker is Authorized Individual in occ
# {"person_id": 6699, "group_id": 2142, "email": "dromasca@gmail.com" }, # Dan Romascanu is Authorized Individual in occ
# {"person_id": 118403, "group_id": 2142, "email": "richard.schell@verizon.com" }, # Rick Schell is Authorized Individual in occ
# {"person_id": 109676, "group_id": 83, "email": "Jonathan.Sadler@tellabs.com" }, # Jonathan Sadler is Authorized Individual in oif
# {"person_id": 122843, "group_id": 2122, "email": "tzhang@omaorg.org" }, # Tiffany Zhang is Authorized Individual in oma
# {"person_id": 116967, "group_id": 1947, "email": "JMudge@omaorg.org" }, # John Mudge is Authorized Individual in oma-architecture-wg
# {"person_id": 117423, "group_id": 1935, "email": "soley@omg.org" }, # Richard Soley is Authorized Individual in omg
# {"person_id": 110831, "group_id": 1858, "email": "kam.lam@nokia.com" }, # Hing-Kam Lam is Authorized Individual in onf
# {"person_id": 113674, "group_id": 1858, "email": "dan.pitt@opennetworking.org" }, # Dan Pitt is Authorized Individual in onf
# {"person_id": 118348, "group_id": 1984, "email": "dave.hood@ericsson.com" }, # Dave Hood is Authorized Individual in onf-arch-wg
# {"person_id": 116967, "group_id": 60, "email": "JMudge@omaorg.org" }, # John Mudge is Authorized Individual in open-mobile-alliance
# {"person_id": 112613, "group_id": 60, "email": "jerry.shih@att.com" }, # Jerry Shih is Authorized Individual in open-mobile-alliance
# {"person_id": 113067, "group_id": 60, "email": "laurent.goix@econocom.com" }, # Laurent Goix is Authorized Individual in open-mobile-alliance
# {"person_id": 112772, "group_id": 60, "email": "zhiyuan.hu@alcatel-sbell.com.cn" }, # Hu Zhiyuan is Authorized Individual in open-mobile-alliance
# {"person_id": 113064, "group_id": 60, "email": "thierry.berisot@telekom.de" }, # Thierry Berisot is Authorized Individual in open-mobile-alliance
# {"person_id": 124276, "group_id": 2212, "email": "jmisener@qti.qualcomm.com" }, # Jim Misener is Authorized Individual in sae-cell-v2x
# {"person_id": 124278, "group_id": 2212, "email": "Keith.Wilson@sae.org" }, # Keith Wilson is Authorized Individual in sae-cell-v2x
# {"person_id": 124277, "group_id": 2212, "email": "Elizabeth.Perry@sae.org" }, # Elizabeth Perry is Authorized Individual in sae-cell-v2x
# {"person_id": 117430, "group_id": 1940, "email": "admin@trustedcomputinggroup.org" }, # Lindsay Adamson is Authorized Individual in tcg
# {"person_id": 117422, "group_id": 1934, "email": "j.hietala@opengroup.org" }, # Jim Hietala is Authorized Individual in the-open-group
# {"person_id": 112104, "group_id": 53, "email": "rick@unicode.org" }, # Rick McGowan is Authorized Individual in unicode
# {"person_id": 112103, "group_id": 54, "email": "plh@w3.org" }, # Philippe Le Hégaret is Authorized Individual in w3c
# {"person_id": 120261, "group_id": 54, "email": "wendy@seltzer.org" }, # Wendy Seltzer is Authorized Individual in w3c
# {"person_id": 118020, "group_id": 1955, "email": "tiago@wballiance.com" }, # Tiago Rodrigues is Authorized Individual in wba
# {"person_id": 125489, "group_id": 1955, "email": "bruno@wballiance.com" }, # Bruno Tomas is Authorized Individual in wba
# {"person_id": 109129, "group_id": 70, "email": "smccammon@amsl.com" }, # Stephanie McCammon is Authorized Individual in zigbee-alliance
# ]}
