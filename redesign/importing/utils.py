from redesign import unaccent
from redesign.person.models import Person, Email, Alias

def clean_email_address(addr):
    addr = addr.replace("!", "@").replace("(at)", "@") # some obvious @ replacements
    # whack surrounding <...>    
    addr = addr[addr.rfind('<') + 1:]
    end = addr.find('>')
    if end != -1:
        addr = addr[:end]
    addr = addr.strip()
    if not "@" in addr:
        return ""
    else:
        return addr

def old_person_to_person(person):
    try:
        return Person.objects.get(id=person.pk)
    except Person.DoesNotExist:
        return Person.objects.get(alias__name=u"%s %s" % (person.first_name, person.last_name))

def old_person_to_email(person):
    hardcoded_emails = { 'Dinara Suleymanova': "dinaras@ietf.org" }
    
    return clean_email_address(person.email()[1] or hardcoded_emails.get("%s %s" % (person.first_name, person.last_name)) or "")

def get_or_create_email(o, create_fake):
    # take o.person (or o) and get or create new Email and Person objects
    person = o.person if hasattr(o, "person") else o
    
    email = old_person_to_email(person)
    if not email:
        if create_fake:
            email = u"unknown-email-%s-%s" % (person.first_name, person.last_name)
            print ("USING FAKE EMAIL %s for %s %s %s" % (email, person.pk, person.first_name, person.last_name)).encode('utf-8')
        else:
            print ("NO EMAIL FOR %s %s %s %s %s" % (o.__class__, o.pk, person.pk, person.first_name, person.last_name)).encode('utf-8')
            return None
    
    e, _ = Email.objects.select_related("person").get_or_create(address=email)
    if not e.person:
        n = u"%s %s" % (person.first_name, person.last_name)
        asciified = unaccent.asciify(n)
        aliases = Alias.objects.filter(name__in=(n, asciified))
        if aliases:
            p = aliases[0].person
        else:
            p = Person(id=person.pk, name=n, ascii=asciified)
            
            from ietf.idtracker.models import PostalAddress
            addresses = person.postaladdress_set.filter(address_priority=1)
            if addresses:
                p.affiliation = (addresses[0].affiliated_company or "").strip()
                # should probably import p.address here

            p.save()
            
            Alias.objects.create(name=n, person=p)
            if asciified != n:
                Alias.objects.create(name=asciified, person=p)
        
        e.person = p
        e.save()

    return e

def possibly_import_other_priority_email(email, addr):
    addr = clean_email_address(addr or "")
    if addr and addr.lower() != email.address.lower():
        try:
            e = Email.objects.get(address=addr)
            if e.person != email.person or e.active != False:
                e.person = email.person
                e.active = False
                e.save()
        except Email.DoesNotExist:
            Email.objects.create(address=addr, person=email.person, active=False)
