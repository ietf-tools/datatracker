from redesign import unaccent
from redesign.person.models import Person, Email, Alias

def clean_email_address(addr):
    addr = addr.replace("!", "@").replace("(at)", "@") # some obvious @ replacements
    addr = addr[addr.rfind('<') + 1:addr.find('>')] # whack surrounding <...>
    addr = addr.strip()
    if not "@" in addr:
        return ""
    else:
        return addr

def old_person_to_person(person):
    return Person.objects.get(id=person.pk)

def old_person_to_email(person):
    hardcoded_emails = { 'Dinara Suleymanova': "dinaras@ietf.org" }
    
    return clean_email_address(person.email()[1] or hardcoded_emails.get("%s %s" % (person.first_name, person.last_name)) or "")

def get_or_create_email(o, create_fake):
    # take person on o and get or create new Email and Person objects
    email = old_person_to_email(o.person)
    if not email:
        if create_fake:
            email = u"unknown-email-%s-%s" % (o.person.first_name, o.person.last_name)
            print ("USING FAKE EMAIL %s for %s %s %s" % (email, o.person.pk, o.person.first_name, o.person.last_name)).encode('utf-8')
        else:
            print ("NO EMAIL FOR %s %s %s %s %s" % (o.__class__, o.pk, o.person.pk, o.person.first_name, o.person.last_name)).encode('utf-8')
            return None
    
    e, _ = Email.objects.select_related("person").get_or_create(address=email)
    if not e.person:
        n = u"%s %s" % (o.person.first_name, o.person.last_name)
        asciified = unaccent.asciify(n)
        aliases = Alias.objects.filter(name__in=(n, asciified))
        if aliases:
            p = aliases[0].person
        else:
            p = Person.objects.create(id=o.person.pk, name=n, ascii=asciified)
            # FIXME: fill in address?
            
            Alias.objects.create(name=n, person=p)
            if asciified != n:
                Alias.objects.create(name=asciified, person=p)
        
        e.person = p
        e.save()

    return e
