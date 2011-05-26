from person.models import Person

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
    
