# Copyright The IETF Trust 2016-2019, All Rights Reserved

import glob
import io
import os

from django.conf import settings
from django.contrib import messages
from django.utils.encoding import smart_text

import debug                            # pyflakes:ignore

from ietf.utils.html import sanitize_document

def handle_upload_file(file,filename,meeting,subdir, request=None, encoding=None):
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

    destination = io.open(os.path.join(path,filename), 'wb+')
    if extension in settings.MEETING_VALID_MIME_TYPE_EXTENSIONS['text/html']:
        file.open()
        text = file.read()
        if encoding:
            try:
                text = text.decode(encoding)
            except LookupError as e:
                return "Failure trying to save '%s': Could not identify the file encoding, got '%s'.  Hint: Try to upload as UTF-8." % (filename, str(e)[:120])
        else:
            try:
                text = smart_text(text)
            except UnicodeDecodeError as e:
                return "Failure trying to save '%s'. Hint: Try to upload as UTF-8: %s..." % (filename, str(e)[:120])
        # Whole file sanitization; add back what's missing from a complete
        # document (sanitize will remove these).
        clean = sanitize_document(text)
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

    return None
