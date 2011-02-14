import os

from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag('submit/submission_files.html', takes_context=True)
def show_submission_files(context, submission):
    result = []
    for ext in submission.file_type.split(','):
        source = os.path.join(settings.STAGING_PATH, '%s-%s%s' % (submission.filename, submission.revision, ext))
        if os.path.exists(source):
            result.append({'name': '[%s version ]' % ext[1:].capitalize(),
                           'url': '%s%s-%s%s' % (settings.STAGING_URL, submission.filename, submission.revision, ext)})
    return {'files': result}
