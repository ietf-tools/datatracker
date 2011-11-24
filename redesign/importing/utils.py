from ietf.utils import unaccent
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

def person_name(person):
    def clean_prefix(n):
        n = clean(n)
        if n in [".", "Mr.", "<s/", "e", "fas", "lk", "Miss", "Mr", "Mr,", "Mr.", "Mr..", "MRS", "Mrs.", "ms", "Ms,", "Ms.", "Ms.    L", "mw", "prefix", "q", "qjfglesjtg", "s", "te mr", "\Mr."]:
            return "" # skip

        fixes = { "Dr": "Dr.", "Lt.Colonel": "Lt. Col.", "M": "M.", "Prof": "Prof.", "Prof.Dr.": "Prof. Dr.", "Professort": "Professor" }
        return fixes.get(n, n)

    def clean_suffix(n):
        n = clean(n)
        if n in ["q", "a", "suffix", "u", "w", "x", "\\"]:
            return "" # skip

        fixes = { "Jr": "Jr.", "Ph. D.": "Ph.D.", "Ph.D": "Ph.D.", "PhD":"Ph.D.", "Phd.": "Phd.", "Scd": "Sc.D." }
        return fixes.get(n, n)

    def clean(n):
        if not n:
            return ""
        return n.replace("]", "").strip()

    def initial_fixup(n):
        if len(n) == 1:
            return n + "."
        return n

    names = [clean_prefix(person.name_prefix), clean(person.first_name),
             initial_fixup(clean(person.middle_initial)), clean(person.last_name), clean_suffix(person.name_suffix)]

    return u" ".join(n for n in names if n)

def old_person_to_person(person):
    try:
        return Person.objects.get(id=person.pk)
    except Person.DoesNotExist:
        return Person.objects.get(alias__name=person_name(person))

def old_person_to_email(person):
    hardcoded_emails = {
        "Dinara Suleymanova": "dinaras@ietf.org",
        "Dow Street": "dow.street@linquest.com",
        }
    
    return clean_email_address(person.email()[1] or hardcoded_emails.get(u"%s %s" % (person.first_name, person.last_name)) or "")

def get_or_create_email(o, create_fake):
    # take o.person (or o) and get or create new Email and Person objects
    person = o.person if hasattr(o, "person") else o

    name = person_name(person)

    email = old_person_to_email(person)
    if not email:
        if create_fake:
            email = u"unknown-email-%s" % name.replace(" ", "-")
            print ("USING FAKE EMAIL %s for %s %s" % (email, person.pk, name)).encode('utf-8')
        else:
            print ("NO EMAIL FOR %s %s %s %s" % (o.__class__, o.pk, person.pk, name)).encode('utf-8')
            return None
    
    e, _ = Email.objects.select_related("person").get_or_create(address=email)
    if not e.person:
        asciified = unaccent.asciify(name)
        aliases = Alias.objects.filter(name__in=(name, asciified)).select_related('person')
        if aliases:
            p = aliases[0].person
        else:
            p = Person(id=person.pk, name=name, ascii=asciified)
            
            from ietf.idtracker.models import PostalAddress
            addresses = person.postaladdress_set.filter(address_priority=1)
            if addresses:
                p.affiliation = (addresses[0].affiliated_company or "").strip()
                # should probably import p.address here

            p.save()
            
            Alias.objects.create(name=p.name, person=p)
            if p.ascii != p.name:
                Alias.objects.create(name=p.ascii, person=p)
        
        e.person = p
        e.save()
    else:
        if e.person.name != name:
            if not Alias.objects.filter(name=name):
                Alias.objects.create(name=name, person=e.person)
            # take longest name rather than the first we encounter
            if len(name) > e.person.name:
                e.person.name = name
                e.person.save()

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

def dont_save_queries():
    # prevent memory from leaking when settings.DEBUG=True
    from django.db import connection
    class DontSaveQueries(object):
        def append(self, x):
            pass 
    connection.queries = DontSaveQueries()
