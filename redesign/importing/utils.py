def person_email(person):
    hardcoded_emails = { 'Dinara Suleymanova': "dinaras@ietf.org" }
    
    return person.email()[1] or hardcoded_emails.get("%s %s" % (person.first_name, person.last_name))
    
