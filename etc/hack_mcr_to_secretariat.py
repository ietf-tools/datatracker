from ietf.person.models import Person, Email
from ietf.name.models import RoleName
from ietf.group.models import Group

mcr = Person.objects.get(pk=102254)
secr = RoleName.objects.get(pk="secr")
secretariat = Group.objects.get(pk=4)
email = Email(address = "orlando@credil.org", person=mcr, active=True)
email.save()
mcr.role_set.create(name=secr, email=email, group=secretariat)

