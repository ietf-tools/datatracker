
from django.db import migrations, models

INITIAL_MAIN_NAMES = ['Akamai', 'Alcatel', 'Alcatel-Lucent', 'Amazon', 'Apple', 'Arista', 'Aruba', 'AT&T', 'Avaya', 'BBN', 'Boeing', 
    'Broadcom', 'Cabletron', 
    'CERNET', 'Check Point', 'Ciena', 'Cisco', 'DEC', 'Ericsson', 'EMC', 'Fastmail', 'France Telecom', 'Fraunhofer', 'Fujitsu', 
    'Futurewei', 'Google', 'Hewlett-Packard', 'Hitachi', 'HPE', 'Huawei', 'IBM', 'INRIA', 'Intel', 'IEEE', 'ISODE', 'JHU', 'Juniper', 
    'KDDI', 'Lucent', 'MCI', 'Meta', 'Microsoft', 'MIT', 'Motorola', 'Mozilla',
    'NASA', 'NEC', 'Netscape','Nokia', 'Nortel', 'NTT', 'NVIDIA', 'Oracle', 'Pantheon', 'Redback', 
    'Qualcomm', 'Samsung', 'Siemens', 'Softbank', 'Telefonica', 'T-Mobile', 'Telia', 'Tencent',
    'UUNET', 'VeriSign', 'Verizon', 'Videotron','Vodafone', 'Wellfleet', 'Xerox', 'ZTE']

OBSOLETED_AFFILIATION_ALIASES = [
    {'alias': 'cisco systems india pvt', 'name': 'cisco Systems'},
    {'alias': 'cisco systems (india) private limited', 'name': 'cisco Systems'},
    {'alias': 'cisco system', 'name': 'cisco Systems'},
    {'alias': 'cisco', 'name': 'cisco Systems'},
]

ADDITIONAL_AFFILIATION_ALIASES = [    
    {'alias': 'Asia Pacific Network Information Centre', 'name': 'APNIC'},
    {'alias': 'ATT', 'name': 'AT&T'},
    {'alias': 'AWS', 'name': 'Amazon'},
    {'alias': 'BUPT', 'name': 'Beijing University of Posts and Telecommunications'},
    {'alias': 'CERT', 'name': 'US-CERT'},
    {'alias': 'CMU', 'name': 'Carnegie Mellon University'},
    {'alias': 'Columbia University', 'name': 'Columbia University'},
    {'alias': 'Consultant', 'name': 'Independent'},
    {'alias': 'Digital Equipment Corporation', 'name': 'DEC'},
    {'alias': 'HP', 'name': 'Hewlett-Packard'},
    {'alias': 'Independent Consultant', 'name': 'Independent'},
    {'alias': 'Individual', 'name': 'Independent'},
    {'alias': 'Individual Contributor', 'name': 'Independent'},
    {'alias': 'Internet Systems Consortium', 'name': 'ISC'},
    {'alias': 'Johns Hopkins University ', 'name': 'JHU'},
    {'alias': 'National Institute of Standards and Technology', 'name': 'US-NIST'},
    {'alias': 'NIST', 'name': 'US-NIST'},
    {'alias': 'Person', 'name': 'Independent'},
    {'alias': 'The Boeing Company', 'name': 'Boeing'},
    {'alias': 'Unaffiliated', 'name': 'Independent'},
]

ADDITIONAL_IGNORE_ENDINGS = [
    'ab\\.?', 'ag\\.?', 'corp\\.?', 'corporation\\.?', 'corportation\\.?', 'international pte ltd\\.?',  'limited\\.?', 
    'l.l.c\\.?',
    'private limited\\.?', 'pty ltd\\.?',
    'pvt ltd\\.?', 's\\.a\\.s\\.?', 's\\.a\\.r\\.l\\.?', 's\\.p\\.a\\.?'
]

NEW_COUNTRY_ALIASES = [
        {'alias': 'belgie', 'country': 'Belgium'},
        {'alias': 'belgique', 'country': 'Belgium'},
        {'alias': 'cccp', 'country': 'Russia'},
        {'alias': 'chinese', 'country': 'China'},
        {'alias': 'finlandia', 'country': 'Finland'},
        {'alias': 'holland', 'country': 'Netherlands'},
        {'alias': 'nederland', 'country': 'Netherlands'},
        {'alias': 'soviet union', 'country': 'Russia'},
        {'alias': 'suomi', 'country': 'Finland'},
        {'alias': 'the netherlands', 'country': 'Netherlands'},
        {'alias': 'u.k.', 'country': 'United Kingdom'},
        {'alias': 'ussr', 'country': 'Russia'},
        {'alias': 'u.s.s.r.', 'country': 'Russia'},
        {'alias': 'россия', 'country': 'Russia'},
        {'alias': 'российская федерация', 'country': 'Russia'},
        {'alias': 'wales', 'country': 'United Kingdom'},
]

def forward(apps, schema_editor):
    """Add initial main names, update country & affiliation aliases."""
    AffiliationMainName = apps.get_model('stats', 'AffiliationMainName')
    for name in INITIAL_MAIN_NAMES:
        AffiliationMainName.objects.get_or_create(main_name=name)

    AffiliationAlias = apps.get_model('stats', 'AffiliationAlias')
    for entry in OBSOLETED_AFFILIATION_ALIASES:
        AffiliationAlias.objects.filter(alias=entry['alias']).delete()
    for entry in ADDITIONAL_AFFILIATION_ALIASES:
        AffiliationAlias.objects.get_or_create(alias=entry['alias'], defaults={'name': entry['name']})
 
    AffiliationIgnoredEnding = apps.get_model('stats', 'AffiliationIgnoredEnding')
    for ending in ADDITIONAL_IGNORE_ENDINGS:
        AffiliationIgnoredEnding.objects.get_or_create(ending=ending)

    CountryAlias = apps.get_model('stats', 'CountryAlias')
    CountryName = apps.get_model('name', 'CountryName')

    for entry in NEW_COUNTRY_ALIASES:
        country = CountryName.objects.get(name=entry['country'])
        CountryAlias.objects.get_or_create(
            alias=entry['alias'],
            defaults={'country': country},
        )


def backward(apps, schema_editor):
    """Remove initial main names, modified country aliases, and add back some obsolete affiliation aliases."""
    AffiliationMainName = apps.get_model('stats', 'AffiliationMainName')
    AffiliationMainName.objects.filter(main_name__in=INITIAL_MAIN_NAMES).delete()

    AffiliationAlias = apps.get_model('stats', 'AffiliationAlias')
    for entry in OBSOLETED_AFFILIATION_ALIASES:
        AffiliationAlias.objects.get_or_create(alias=entry['alias'], defaults={'name': entry['name']})
    for entry in ADDITIONAL_AFFILIATION_ALIASES:
        AffiliationAlias.objects.filter(alias=entry['alias']).delete()

    AffiliationIgnoredEnding = apps.get_model('stats', 'AffiliationIgnoredEnding')
    for ending in ADDITIONAL_IGNORE_ENDINGS:
        AffiliationIgnoredEnding.objects.filter(ending=ending).delete()

    CountryAlias = apps.get_model('stats', 'CountryAlias')
    aliases_to_remove = [alias for alias, _ in NEW_COUNTRY_ALIASES]
    CountryAlias.objects.filter(alias__in=aliases_to_remove).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("stats", "0002_fix_meeting_registration_reg_type"),
    ]

    operations = [
        migrations.CreateModel(
            name='AffiliationMainName',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('main_name', models.CharField(max_length=255, unique=True, help_text="Main leading part of an affiliation, the remaing part can be ignored.")),
            ],
            options={
                'verbose_name_plural': 'affiliation main names',
            },
        ),
        migrations.RunPython(forward, backward),
    ]
