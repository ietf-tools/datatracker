import tempfile
import os

from django.contrib.auth.models import User
from django.conf import settings

from ietf.utils.pipe import pipe
from ietf.group.models import Group, Role
from ietf.person.models import Email, Person
from ietf.name.models import RoleName
from ietf.nomcom.models import NomCom, Position, Nominee

COMMUNITY_USER = 'plain'
CHAIR_USER = 'chair'
MEMBER_USER = 'member'
SECRETARIAT_USER = 'secretariat'
EMAIL_DOMAIN = '@example.com'

USERS = [COMMUNITY_USER, CHAIR_USER, MEMBER_USER, SECRETARIAT_USER]

POSITIONS = {
    "GEN": "IETF Chair/Gen AD",
    "APP": "APP Area Director",
    "INT": "INT Area Director",
    "OAM": "OPS Area Director",
    "OPS": "OPS Area Director",
    "RAI": "RAI Area Director",
    "RTG": "RTG Area Director",
    "SEC": "SEC Area Director",
    "TSV": "TSV Area Director",
    "IAB": "IAB Member",
    "IAOC": "IAOC Member",
  }


def generate_cert():
    """Function to generate cert"""
    config = """
            [ req ]
            distinguished_name = req_distinguished_name
            string_mask        = utf8only
            x509_extensions    = ss_v3_ca

            [ req_distinguished_name ]
            commonName           = Common Name (e.g., NomComYY)
            commonName_default  = NomCom12

            [ ss_v3_ca ]

            subjectKeyIdentifier = hash
            keyUsage = critical, digitalSignature, keyEncipherment, dataEncipherment
            basicConstraints = critical, CA:true
            subjectAltName = email:nomcom12@ietf.org
            extendedKeyUsage= emailProtection"""

    config_file = tempfile.NamedTemporaryFile(delete=False)
    privatekey_file = tempfile.NamedTemporaryFile(delete=False)
    cert_file = tempfile.NamedTemporaryFile(delete=False)

    config_file.write(config)
    config_file.close()

    command = "%s req -config %s -x509 -new -newkey rsa:2048 -sha256 -days 730 -nodes \
                -keyout %s -out %s -batch"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                       config_file.name,
                                       privatekey_file.name,
                                       cert_file.name))
    privatekey_file.close()
    cert_file.close()
    return cert_file, privatekey_file


def check_comments(encryped, plain, privatekey_file):
    encrypted_file = tempfile.NamedTemporaryFile(delete=False)
    encrypted_file.write(encryped)
    encrypted_file.close()

    # to decrypt comments was encryped and check they are equal to the plain comments
    decrypted_file = tempfile.NamedTemporaryFile(delete=False)
    command = "%s smime -decrypt -in %s -out %s -inkey %s"
    code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                        encrypted_file.name,
                                        decrypted_file.name,
                                        privatekey_file.name))

    decrypted_file.close()
    encrypted_file.close()
    decrypted_comments = open(decrypted_file.name, 'r').read()
    os.unlink(encrypted_file.name)
    os.unlink(decrypted_file.name)

    return decrypted_comments == plain


def nomcom_test_data():
    # groups
    group, created = Group.objects.get_or_create(name='IAB/IESG Nominating Committee 2013/2014',
                                        state_id='active',
                                        type_id='nomcom',
                                        acronym='nomcom2013')
    nomcom, created = NomCom.objects.get_or_create(group=group)

    secretariat, created = Group.objects.get_or_create(name="Secretariat",
                                                       acronym="secretariat",
                                                       state_id="active",
                                                       type_id="ietf",
                                                       parent=None)
    # users
    for user in USERS:
        u, created = User.objects.get_or_create(username=user, password=user)
        person, created = Person.objects.get_or_create(
            name=user,
            ascii=user,
            user=u)
        email, created = Email.objects.get_or_create(
            address="%s%s" % (user, EMAIL_DOMAIN),
            person=person)

        if user == CHAIR_USER:
            role, created = RoleName.objects.get_or_create(slug="chair")
            Role.objects.get_or_create(name=role,
                                       group=group,
                                       person=person,
                                       email=email)
        if user == MEMBER_USER:
            role, created = RoleName.objects.get_or_create(slug="member")
            Role.objects.get_or_create(name=role,
                                       group=group,
                                       person=person,
                                       email=email)
        if user == SECRETARIAT_USER:
            role, created = RoleName.objects.get_or_create(slug="secr")
            Role.objects.create(name=role,
                                group=secretariat,
                                person=person,
                                email=email)
    # nominee
    email = Email.objects.get(person__name=COMMUNITY_USER)
    nominee, created = Nominee.objects.get_or_create(email=email)

    # positions
    for name, description in POSITIONS.iteritems():
        position, created = Position.objects.get_or_create(nomcom=nomcom,
                                                           name=name,
                                                           description=description,
                                                           is_open=True,
                                                           incumbent=email)
