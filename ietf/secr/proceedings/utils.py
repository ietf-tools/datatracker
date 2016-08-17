import glob
import os

import debug                            # pyflakes:ignore

def handle_upload_file(file,filename,meeting,subdir):
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
    for chunk in file.chunks():
        destination.write(chunk)
    destination.close()

    # unzip zipfile
    if extension == '.zip':
        os.chdir(path)
        os.system('unzip %s' % filename)

