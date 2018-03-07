
import glob
import os

from django.conf import settings
from django.contrib import messages

import debug                            # pyflakes:ignore

from ietf.utils.html import sanitize_html

def handle_upload_file(file,filename,meeting,subdir, request=None):
    '''
    This function takes a file object, a filename and a meeting object and subdir as string.
    It saves the file to the appropriate directory, get_materials_path() + subdir.
    If the file is a zip file, it creates a new directory in 'slides', which is the basename of the
    zip file and unzips the file in the new directory.
    '''
    base, extension = os.path.splitext(filename)

    if extension == '.zip':
        path = os.path.join(meeting.get_materials_path(),subdir,base)
        if not os.path.exists(path):
            os.mkdir(path)
    else:
        path = os.path.join(meeting.get_materials_path(),subdir)
        if not os.path.exists(path):
            os.makedirs(path)

    # agendas and minutes can only have one file instance so delete file if it already exists
    if subdir in ('agenda','minutes'):
        old_files = glob.glob(os.path.join(path,base) + '.*')
        for f in old_files:
            os.remove(f)

    destination = open(os.path.join(path,filename), 'wb+')
    if extension in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS['text/html']:
        file.open()
        text = file.read().decode('utf-8')
        # Whole file sanitization; add back '<html>' (sanitize will remove it)
        clean = u"""<!DOCTYPE html>
        <html lang="en">
        <head><title>%s</title></head>
        <body>
        %s
        </body>
        </html>
        """ % (filename, sanitize_html(text))
        destination.write(clean.encode('utf8'))
        if request and clean != text:
            messages.warning(request, "Uploaded html content is sanitized to prevent unsafe content.  "
                                      "Your upload %s was changed by the sanitization; please check the "
                                       "resulting content.  " % (filename, ))
    else:
        for chunk in file.chunks():
            destination.write(chunk)
    destination.close()

    # unzip zipfile
    if extension == '.zip':
        os.chdir(path)
        os.system('unzip %s' % filename)

