import os

from django import template
from django.conf import settings
from django.utils.html import mark_safe, escape

from ietf.submit.utils import POSTED, POSTED_BY_SECRETARIAT


register = template.Library()


@register.inclusion_tag('submit/submission_files.html', takes_context=True)
def show_submission_files(context, submission):
    result = []
    for ext in submission.file_type.split(','):
        exists = False
        source = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s%s' % (submission.filename, submission.revision, ext))
        if os.path.exists(source):
            exists = True
        elif submission.status_id in [POSTED, POSTED_BY_SECRETARIAT]:
            continue
        result.append({'name': '[%s version ]' % ext[1:].capitalize(),
                       'exists': exists,
		       'url': '%s%s-%s%s' % (settings.IDSUBMIT_STAGING_URL, submission.filename, submission.revision, ext)})
    return {'files': result}


@register.filter
def two_pages_decorated_with_validation(value, validation):
    pages = value.first_two_pages or ''
    if not 'revision' in validation.warnings.keys():
        return mark_safe('<pre class="twopages" style="display: none;">%s</pre>' % escape(pages))
    result = '<pre class="twopages" style="display: none;">\n'
    for line in pages.split('\n'):
        if line.find('%s-%s' % (value.filename, value.revision)) > -1:
            result += '</pre><pre class="twopages" style="display: none; background: red;">'
            result += escape(line)
            result += '\n'
            result += '</pre><pre class="twopages" style="display: none;">\n'
        else:
            result += escape(line)
            result += '\n'
    return mark_safe(result)
