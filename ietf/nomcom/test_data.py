from django.contrib.auth.models import User

from ietf.group.models import Group
from ietf.person.models import Email, Person
from ietf.name.models import GroupStateName, GroupTypeName
from ietf.nomcom.models import NomCom, Position, NomineePosition, Nominee

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


def nomcom_test_data():
    group, created = Group.objects.get_or_create(name='IAB/IESG Nominating Committee 2013/2014',
                                        state=GroupStateName.objects.get(='active'),
                                        type=GroupTypeName.objects.get(slug='nomcom'),
                                        acronym='nomcom2013')
    nomcom, created = NomCom.objects.get_or_create(group=group)
    u, created = User.objects.get_or_create(username="plain")
    plainman, created = Person.objects.get_or_create(
        name="Plain Man",
        ascii="Plain Man",
        user=u)
    email, cerated = Email.objects.get_or_create(
        address="plain@example.com",
        person=plainman)
    for name, description in POSITIONS.iteritems():
        position, created = Position.objects.get_or_create(nomcom=nomcom,
                                                           name=name,
                                                           description=description,
                                                           is_open=True,
                                                           incumbent=email)
    Position.objects.get(name='GEN')
    nominee, created = Nominee.objects.get_or_create(email=email)
    nominee_position, created = NomineePosition.objects.get_or_create(position=position, nominee=nominee)
