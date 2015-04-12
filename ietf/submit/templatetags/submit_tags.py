import os

from django import template
from django.conf import settings
from django.utils.html import mark_safe, escape

register = template.Library()


@register.inclusion_tag('submit/submission_files.html', takes_context=True)
def show_submission_files(context, submission):
    result = []
    for ext in submission.file_types.split(','):
        exists = False
        source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (submission.name, submission.rev, ext))
        if os.path.exists(source):
            exists = True
        elif submission.state_id == "posted":
            continue
        result.append({'ext': '%s' % ext[1:],
                       'exists': exists,
		       'url': '%s%s-%s%s' % (settings.IDSUBMIT_STAGING_URL, submission.name, submission.rev, ext)})
    return {'files': result}


@register.filter
def two_pages_decorated_with_errors(submission, errors):
    pages = submission.first_two_pages or ''
    if 'rev' not in errors.keys():
        return mark_safe('<pre>%s</pre>' % escape(pages))
    result = '<pre>\n'
    for line in pages.split('\n'):
        if line.find('%s-%s' % (submission.name, submission.rev)) > -1:
            result += '<div class="bg-danger"><b>'
            result += escape(line)
            result += '\n'
            result += '</b></div>\n'
        else:
            result += escape(line)
            result += '\n'
    result += '</pre>pre>\n'
    return mark_safe(result)
