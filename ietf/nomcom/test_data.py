import tempfile
import os

from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.group.models import Group, ChangeStateGroupEvent
from ietf.nomcom.models import NomCom, Position, Nominee
from ietf.person.models import Email, Person
from ietf.utils.pipe import pipe
from ietf.utils.test_data import create_person

COMMUNITY_USER = 'plain'
CHAIR_USER = 'nomcomchair'
MEMBER_USER = 'nomcommember'
SECRETARIAT_USER = 'secretary'
EMAIL_DOMAIN = '@example.com'
NOMCOM_YEAR = "2013"

POSITIONS = [
    "GEN",
    "APP",
    "INT",
    "OAM",
    "OPS",
    "RAI",
    "RTG",
    "SEC",
    "TSV",
    "IAB",
    "IAOC"
  ]


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
    decrypted_comments = open(decrypted_file.name, 'r').read().decode('utf8')
    os.unlink(encrypted_file.name)
    os.unlink(decrypted_file.name)

    return decrypted_comments == plain

nomcom_test_cert_file = None

def nomcom_test_data():
    # groups
    group, created = Group.objects.get_or_create(name='IAB/IESG Nominating Committee 2013/2014',
                                        state_id='active',
                                        type_id='nomcom',
                                        acronym='nomcom%s' % NOMCOM_YEAR)

    nomcom, created = NomCom.objects.get_or_create(group=group)

    global nomcom_test_cert_file
    if not nomcom_test_cert_file:
        nomcom_test_cert_file, privatekey_file = generate_cert()

    nomcom.public_key.storage = FileSystemStorage(location=settings.NOMCOM_PUBLIC_KEYS_DIR)
    nomcom.public_key.save('cert', File(open(nomcom_test_cert_file.name, 'r')))

    # chair and member
    create_person(group, "chair", username=CHAIR_USER)
    create_person(group, "member", username=MEMBER_USER)

    # nominee
    u, created = User.objects.get_or_create(username=COMMUNITY_USER)
    if created:
        u.set_password(COMMUNITY_USER+"+password")
        u.save()
    plainman, _ = Person.objects.get_or_create(name="Plain Man", ascii="Plain Man", user=u)
    email, _ = Email.objects.get_or_create(address="plain@example.com", person=plainman)
    nominee, _ = Nominee.objects.get_or_create(email=email, nomcom=nomcom)

    # positions
    for name in POSITIONS:
        position, created = Position.objects.get_or_create(nomcom=nomcom,
                                                           name=name,
                                                           is_open=True)

    ChangeStateGroupEvent.objects.get_or_create(group=group,
                                                type="changed_state",
                                                state_id="active",
                                                time=group.time,
                                                by=Person.objects.all()[0])
