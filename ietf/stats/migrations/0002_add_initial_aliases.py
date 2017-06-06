# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_affiliation_info(apps, schema_editor):
    AffiliationAlias = apps.get_model("stats", "AffiliationAlias")

    AffiliationAlias.objects.get_or_create(alias="cisco", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco system", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco systems (india) private limited", name="Cisco Systems")
    AffiliationAlias.objects.get_or_create(alias="cisco systems india pvt", name="Cisco Systems")

    AffiliationIgnoredEnding = apps.get_model("stats", "AffiliationIgnoredEnding")
    AffiliationIgnoredEnding.objects.get_or_create(ending="LLC\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="Ltd\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="Inc\.?")
    AffiliationIgnoredEnding.objects.get_or_create(ending="GmbH\.?")

    CountryAlias = apps.get_model("stats", "CountryAlias")
    for iso_country_code in ['AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU', 'AW',
                             'AX', 'AZ', 'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM', 'BN',
                             'BO', 'BQ', 'BR', 'BS', 'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF', 'CG',
                             'CH', 'CI', 'CK', 'CL', 'CM', 'CN', 'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY', 'CZ',
                             'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE', 'EG', 'EH', 'ER', 'ES', 'ET', 'FI',
                             'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF', 'GG', 'GH', 'GI', 'GL',
                             'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM', 'HN', 'HR',
                             'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT', 'JE', 'JM',
                             'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP', 'KR', 'KW', 'KY', 'KZ', 'LA',
                             'LB', 'LC', 'LI', 'LK', 'LR', 'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME',
                             'MF', 'MG', 'MH', 'MK', 'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU',
                             'MV', 'MW', 'MX', 'MY', 'MZ', 'NA', 'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP',
                             'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG', 'PH', 'PK', 'PL', 'PM', 'PN', 'PR',
                             'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW', 'SA', 'SB', 'SC', 'SD',
                             'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS', 'ST', 'SV',
                             'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK', 'TL', 'TM', 'TN', 'TO',
                             'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE',
                             'VG', 'VI', 'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW']:
        CountryAlias.objects.get_or_create(alias=iso_country_code, country_id=iso_country_code)

    CountryAlias.objects.get_or_create(alias="russian federation", country_id="RU")
    CountryAlias.objects.get_or_create(alias="p. r. china", country_id="CN")
    CountryAlias.objects.get_or_create(alias="p.r. china", country_id="CN")
    CountryAlias.objects.get_or_create(alias="p.r.china", country_id="CN")
    CountryAlias.objects.get_or_create(alias="p.r china", country_id="CN")
    CountryAlias.objects.get_or_create(alias="p.r. of china", country_id="CN")
    CountryAlias.objects.get_or_create(alias="PRC", country_id="CN")
    CountryAlias.objects.get_or_create(alias="P.R.C", country_id="CN")
    CountryAlias.objects.get_or_create(alias="P.R.C.", country_id="CN")
    CountryAlias.objects.get_or_create(alias="beijing", country_id="CN")
    CountryAlias.objects.get_or_create(alias="shenzhen", country_id="CN")
    CountryAlias.objects.get_or_create(alias="R.O.C.", country_id="TW")
    CountryAlias.objects.get_or_create(alias="usa", country_id="US")
    CountryAlias.objects.get_or_create(alias="UAS", country_id="US")
    CountryAlias.objects.get_or_create(alias="USA.", country_id="US")
    CountryAlias.objects.get_or_create(alias="u.s.a.", country_id="US")
    CountryAlias.objects.get_or_create(alias="u. s. a.", country_id="US")
    CountryAlias.objects.get_or_create(alias="u.s.a", country_id="US")
    CountryAlias.objects.get_or_create(alias="u.s.", country_id="US")
    CountryAlias.objects.get_or_create(alias="U.S", country_id="GB")
    CountryAlias.objects.get_or_create(alias="US of A", country_id="US")
    CountryAlias.objects.get_or_create(alias="united sates", country_id="US")
    CountryAlias.objects.get_or_create(alias="united state", country_id="US")
    CountryAlias.objects.get_or_create(alias="united states", country_id="US")
    CountryAlias.objects.get_or_create(alias="unites states", country_id="US")
    CountryAlias.objects.get_or_create(alias="texas", country_id="US")
    CountryAlias.objects.get_or_create(alias="UK", country_id="GB")
    CountryAlias.objects.get_or_create(alias="united kingcom", country_id="GB")
    CountryAlias.objects.get_or_create(alias="great britain", country_id="GB")
    CountryAlias.objects.get_or_create(alias="england", country_id="GB")
    CountryAlias.objects.get_or_create(alias="U.K.", country_id="GB")
    CountryAlias.objects.get_or_create(alias="U.K", country_id="GB")
    CountryAlias.objects.get_or_create(alias="Uk", country_id="GB")
    CountryAlias.objects.get_or_create(alias="scotland", country_id="GB")
    CountryAlias.objects.get_or_create(alias="republic of korea", country_id="KR")
    CountryAlias.objects.get_or_create(alias="korea", country_id="KR")
    CountryAlias.objects.get_or_create(alias="korea rep", country_id="KR")
    CountryAlias.objects.get_or_create(alias="korea (the republic of)", country_id="KR")
    CountryAlias.objects.get_or_create(alias="the netherlands", country_id="NL")
    CountryAlias.objects.get_or_create(alias="netherland", country_id="NL")
    CountryAlias.objects.get_or_create(alias="danmark", country_id="DK")
    CountryAlias.objects.get_or_create(alias="sweeden", country_id="SE")
    CountryAlias.objects.get_or_create(alias="swede", country_id="SE")
    CountryAlias.objects.get_or_create(alias="belgique", country_id="BE")
    CountryAlias.objects.get_or_create(alias="madrid", country_id="ES")
    CountryAlias.objects.get_or_create(alias="espana", country_id="ES")
    CountryAlias.objects.get_or_create(alias="hellas", country_id="GR")
    CountryAlias.objects.get_or_create(alias="gemany", country_id="DE")
    CountryAlias.objects.get_or_create(alias="deutschland", country_id="DE")
    CountryAlias.objects.get_or_create(alias="italia", country_id="IT")
    CountryAlias.objects.get_or_create(alias="isreal", country_id="IL")
    CountryAlias.objects.get_or_create(alias="tel aviv", country_id="IL")
    CountryAlias.objects.get_or_create(alias="UAE", country_id="AE")
    CountryAlias.objects.get_or_create(alias="grand-duchy of luxembourg", country_id="LU")
    CountryAlias.objects.get_or_create(alias="brasil", country_id="BR")


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_affiliation_info, migrations.RunPython.noop)
    ]
