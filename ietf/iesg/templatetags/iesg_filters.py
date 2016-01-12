from django import template

register = template.Library()

@register.filter
def telechat_page_count(telechat):
    page_count = 0
    for num, section in telechat['sections']:
        if num in ('2.1.1','2.1.2','2.2.1','2.2.2','3.1.1','3.1.2','3.2.1','3.2.2',):
            for doc in section['docs']:
                page_count += getattr(doc,'pages',0)
    return page_count

# An alternate implementation:
# sum([doc.pages for doc in Document.objects.filter(docevent__telechatdocevent__telechat_date=d,type='draft').distict() if doc.telechat_date()==d])
