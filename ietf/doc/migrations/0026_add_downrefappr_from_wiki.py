# -*- coding: utf-8 -*-
from django.db import models, migrations

downref_registry_from_wiki = [
    ['rfc952', 'draft-hollenbeck-rfc4931bis'],
    ['rfc952', 'draft-hollenbeck-rfc4932bis'],
    ['rfc1094','draft-ietf-nfsv4-nfsdirect'],
    ['rfc1321','rfc3967'],
    ['rfc1813','draft-ietf-nfsv4-nfsdirect'],
    ['rfc1951','draft-ietf-lemonade-compress'],
    ['rfc1952','draft-sweet-rfc2911bis'],
    ['rfc1977','draft-sweet-rfc2911bis'],
    ['rfc2104','rfc3967'],
    ['rfc2144','draft-ietf-secsh-newmodes'],
    ['rfc2315','draft-eastlake-additional-xmlsec-uris'],
    ['rfc2330','draft-ietf-ippm-metrictest'],
    ['rfc2412','draft-ietf-cat-kerberos-pk-init'],
    ['rfc2648','draft-ietf-simple-xcap-diff'],
    ['rfc2683','draft-ietf-qresync-rfc5162bis'],
    ['rfc2702','draft-ietf-isis-admin-tags'],
    ['rfc2781','draft-ietf-appsawg-xml-mediatypes'],
    ['rfc2818','draft-dusseault-caldav'],
    ['rfc2898','draft-turner-asymmetrickeyformat-algs'],
    ['rfc2966','draft-ietf-isis-admin-tags'],
    ['rfc2985','rfc5750'],
    ['rfc2986','rfc6487'],
    ['rfc3032','draft-ietf-pals-rfc4447bis'],
    ['rfc3174','draft-harris-ssh-rsa-kex'],
    ['rfc3196','draft-sweet-rfc2911bis'],
    ['rfc3217','draft-ietf-smime-cms-rsa-kem'],
    ['rfc3272','draft-ietf-mpls-cosfield-def'],
    ['rfc3280','rfc3852'],
    ['rfc3281','rfc3852'],
    ['rfc3394','draft-ietf-smime-cms-rsa-kem'],
    ['rfc3447','draft-ietf-cat-kerberos-pk-init'],
    ['rfc3469','draft-ietf-mpls-cosfield-def'],
    ['rfc3548','draft-ietf-dnsext-dnssec-records'],
    ['rfc3564','draft-ietf-mpls-cosfield-def'],
    ['rfc3567','draft-ietf-pce-disco-proto-isis'],
    ['rfc3610','rfc4309'],
    ['rfc3843','rfc5953'],
    ['rfc3579','draft-ietf-radext-rfc4590bis'],
    ['rfc3618','draft-ietf-mboned-msdp-deploy'],
    ['rfc3713','draft-kato-ipsec-ciph-camellia'],
    ['rfc3784','draft-ietf-isis-admin-tags'],
    ['rfc3985','draft-ietf-mpls-cosfield-def'],
    ['rfc4050','draft-eastlake-additional-xmlsec-uris'],
    ['rfc4082','draft-ietf-msec-srtp-tesla'],
    ['rfc4226','draft-ietf-keyprov-pskc'],
    ['rfc4269','draft-eastlake-additional-xmlsec-uris'],
    ['rfc4291','draft-hollenbeck-rfc4932bis'],
    ['rfc4347','rfc5953'],
    ['rfc4357','draft-ietf-pkix-gost-cppk'],
    ['rfc4366','rfc5953'],
    ['rfc4492','draft-ietf-tls-chacha20-poly1305'],
    ['rfc4493','draft-songlee-aes-cmac-96'],
    ['rfc4627','draft-ietf-mediactrl-ivr-control-package'],
    ['rfc4753','draft-ietf-ipsec-ike-auth-ecdsa'],
    ['rfc4949','draft-ietf-oauth-v2'],
    ['rfc5036','draft-ietf-pals-rfc4447bis'],
    ['rfc5246','rfc5953'],
    ['rfc5280','rfc5953'],
    ['rfc5322','draft-hollenbeck-rfc4933bis'],
    ['rfc5410','draft-arkko-mikey-iana'],
    ['rfc5489','draft-ietf-tls-chacha20-poly1305'],
    ['rfc5598','draft-ietf-dkim-mailinglists'],
    ['rfc5649','draft-turner-asymmetrickeyformat-algs'],
    ['rfc5753','draft-turner-cms-symmetrickeypackage-algs'],
    ['rfc5781','draft-ietf-sidr-res-certs'],
    ['rfc5869','draft-ietf-trill-channel-tunnel'],
    ['rfc5890','draft-ietf-dkim-rfc4871bis'],
    ['rfc5911','draft-turner-asymmetrickeyformat'],
    ['rfc5912','draft-ietf-pkix-authorityclearanceconstraints'],
    ['rfc5952','rfc5953'],
    ['rfc6043','draft-arkko-mikey-iana'],
    ['rfc6090','draft-turner-akf-algs-update'],
    ['rfc6151','draft-ietf-netmod-system-mgmt'],
    ['rfc6234','draft-schaad-pkix-rfc2875-bis'],
    ['rfc6386','draft-ietf-rtcweb-video'],
    ['rfc6480','rfc6485'],
    ['rfc6480','rfc6489'],
    ['rfc6480','rfc6491'],
    ['rfc6480','rfc7935'],
    ['rfc6707','draft-ietf-cdni-metadata'],
    ['rfc6839','draft-ietf-appsawg-xml-mediatypes'],
    ['rfc7251','rfc7252'],
    ['rfc7358','draft-ietf-pals-rfc4447bis'],
    ['rfc7539','draft-ietf-tls-chacha20-poly1305'],
    ['rfc7612','draft-sweet-rfc2911bis'],
    ['rfc7748','draft-ietf-jose-cfrg-curves'],
    ['rfc8032','draft-ietf-jose-cfrg-curves'] ]


def addDownrefRelationships(apps,schema_editor):
    Document = apps.get_model('doc','Document')
    DocAlias = apps.get_model('doc','DocAlias')
    RelatedDocument = apps.get_model('doc','RelatedDocument')

    for [fn2, fn1] in downref_registry_from_wiki:
        da1 = DocAlias.objects.get(name=fn1)
        da2 = DocAlias.objects.get(name=fn2)
        RelatedDocument.objects.create(source=da1.document,
             target=da2, relationship_id='downrefappr')


def removeDownrefRelationships(apps,schema_editor):
    Document = apps.get_model('doc','Document')
    DocAlias = apps.get_model('doc','DocAlias')
    RelatedDocument = apps.get_model('doc','RelatedDocument')

    for [fn2, fn1] in downref_registry_from_wiki:
        da1 = DocAlias.objects.get(name=fn1)
        da2 = DocAlias.objects.get(name=fn2)
        RelatedDocument.objects.filter(source=da1.document,
             target=da2, relationship_id='downrefappr').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('name', '0019_add_docrelationshoname_downrefappr'),
        ('doc', '0025_auto_20170307_0146'),
    ]

    operations = [
        migrations.RunPython(addDownrefRelationships,removeDownrefRelationships)
    ]
