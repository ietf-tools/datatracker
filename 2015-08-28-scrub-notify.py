#!/usr/bin/env python

import os, sys, re

from copy import copy

# boilerplate
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/"))
sys.path = [ basedir ] + sys.path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

import django

django.setup()

from django.db.models import F
from django.template import Template,Context
from ietf.doc.models import Document, DocEvent
from ietf.person.models import Person
from ietf.utils.mail import send_mail_text

def message_body_template():
    return Template("""{% filter wordwrap:72 %}The Notify field for the document{{ count|pluralize }} listed at the end of this message {% if count > 1 %}were{% else %}was{% endif %} changed by removing the chair, shepherd, author, and similar addresses (in direct or alias form) to the point they could be identified.

The Datatracker now includes those addresses explicitly in each message it sends as appropriate. You can review where the datatracker sends messages for a given action in general using <https://datatracker.ietf.org/mailtoken/token>. You can review the expansions for a specific document by the new Email expansions tab on the document's page. Note that the addresses included for any given action are much more comprehensive than they were before this release.

Please review each new Notify field, and help remove any remaining addresses that will normally be copied per the configuration shown at https://datatracker.ietf.org/mailtoken/token. The field should now only contain exceptional addresses - parties you wish to be notified that aren't part of the new normal recipient set.

You can see exactly how the Notify field was changed for a given document by looking in the document's history.{% endfilter %}

{% if non_empty%}The document{{non_empty|length|pluralize }} with non-empty new Notify fields are:{% for doc in non_empty %}
    https://datatracker.ietf.org{{doc.get_absolute_url}}{% endfor %}{% endif %}

{% if empty%}The document{{non_empty|length|pluralize }} with empty new Notify fields are:{% for doc in empty %}
    https://datatracker.ietf.org{{doc.get_absolute_url}}{% endfor %}{% endif %}

""")

def other_addrs(addr):
    person = Person.objects.filter(email__address__iexact=addr).first()
    if not person:
        return None
    return [x.lower() for x in person.email_set.values_list('address',flat=True)]

def prep(item):
    retval = item.lower()
    if '<' in retval:
        if not '>' in retval:
            raise "Bad item: "+item
        start=retval.index('<')+1
        stop=retval.index('>')
        retval = retval[start:stop]
    return retval

def is_management(item, doc):

    item = prep(item)

    if any([
            item == '%s.chairs@ietf.org'%doc.name,
            item == '%s.ad@ietf.org'%doc.name,
            item == '%s.shepherd@ietf.org'%doc.name,
            item == '%s.chairs@tools.ietf.org'%doc.name,
            item == '%s.ad@tools.ietf.org'%doc.name,
            item == '%s.shepherd@tools.ietf.org'%doc.name,
            doc.ad and item == doc.ad.email_address().lower(),
            doc.shepherd and item == doc.shepherd.address.lower(),
          ]):
        return True

    if doc.group:
        if any([
                item == '%s-chairs@ietf.org'%doc.group.acronym,
                item == '%s-ads@ietf.org'%doc.group.acronym,
                item == '%s-chairs@tools.ietf.org'%doc.group.acronym,
                item == '%s-ads@tools.ietf.org'%doc.group.acronym,
              ]):
            return True
        for addr in doc.group.role_set.filter(name__in=['chair','ad','delegate']).values_list('email__address',flat=True):
            other = other_addrs(addr)
            if item == addr.lower() or item in other:
                return True
        if doc.group.parent:
            if item == '%s-ads@ietf.org'%doc.group.parent.acronym or item == '%s-ads@tools.ietf.org'%doc.group.parent.acronym:
                return True

    return False

def is_author(item, doc):
    item = prep(item)

    if item == '%s@ietf.org' % doc.name or item == '%s@tools.ietf.org' % doc.name:
        return True

    for addr in doc.authors.values_list('address',flat=True):
        other = other_addrs(addr)
        if item == addr.lower() or item in other:
            return True

    return False
    
msg_template = message_body_template()
by = Person.objects.get(name="(System)")
active_ads = list(Person.objects.filter(role__name="ad", role__group__state="active", role__group__type="area"))

affected = set()
empty = dict()
non_empty = dict()
changed = 0
emptied = 0

qs = Document.objects.exclude(notify__isnull=True).exclude(notify='')
for doc in qs:
    doc.notify = doc.notify.replace(';', ',')
    items = set([ i.strip() for i in doc.notify.split(',') if i.strip() and '@' in i])
    original_items = copy(items)
    for item in original_items:
        if any([
                 doc.group and doc.group.list_email and item.lower() == doc.group.list_email.lower(),
                 is_management(item,doc),
                 is_author(item,doc),
               ]):
            items.discard(item)
    if original_items != items:
        changed += 1
        if len(list(items))==0:
            emptied += 1 

        to = []
        if doc.ad and doc.ad in active_ads:
            to.append(doc.ad.email_address())
        if doc.group and doc.group.state_id=='active':
            to.extend(doc.group.role_set.filter(name__in=['chair','ad']).values_list('email__address',flat=True))
        if not to:
            to = ['iesg@ietf.org']

        to = ", ".join(sorted(to))
        affected.add(to)
        empty.setdefault(to,[])
        non_empty.setdefault(to,[])
        if len(list(items))==0:
            empty[to].append(doc)
        else:
            non_empty[to].append(doc)
        original_notify = doc.notify
        new_notify = ', '.join(list(items))
        doc.notify = new_notify
        doc.save()
        e = DocEvent(type="added_comment",doc=doc,time=doc.time,by=by)
        e.desc = "Notify list changed from %s to %s"% (original_notify, new_notify if new_notify else '(None)')
        e.save()

for a in list(affected):

   txt = msg_template.render(Context({'count':len(empty[a])+len(non_empty[a]),'empty':empty[a],'non_empty':non_empty[a]}))
   send_mail_text(None, to=a, frm=None, subject='Document Notify fields changed to match new Datatracker addressing defaults',txt =txt)

print "Changed",changed,"documents.",emptied,"of those had their notify field emptied"
print "Sent email to ",len(affected),"different sets of addresses"

