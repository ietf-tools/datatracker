#!/usr/bin/env python

import os, sys, shutil, pathlib

# boilerplate
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../web/"))
sys.path = [ basedir ] + sys.path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

import django
django.setup()

from ietf.group.models import Role

old_images_dir = os.path.join(django.conf.settings.OLD_PHOTOS_DIR,'wg/images/')
new_images_dir = os.path.join(django.conf.settings.PHOTOS_DIR,django.conf.settings.PHOTO_URL_PREFIX)

old_image_files = []
for (dirpath, dirnames, filenames) in os.walk(old_images_dir):
   old_image_files.extend(filenames)
   break # Only interested in the files in the top directory

old_image_files_lc = map(lambda x:x.lower(),old_image_files)

interesting_persons = set()

interesting_persons.update([r.person for r in Role.objects.filter(group__type='wg',group__state='active',name='chair')])
interesting_persons.update([r.person for r in Role.objects.filter(group__type='rg',group__state='active',name='chair')])
interesting_persons.update([r.person for r in Role.objects.filter(group__type='area',group__state='active',name_id='ad')])
interesting_persons.update([r.person for r in Role.objects.filter(group__acronym='iab',name_id='member')])
interesting_persons.update([r.person for r in Role.objects.filter(group__acronym='irtf',name_id='chair')])

#from ietf.person.models import Person
#interesting_persons = Person.objects.filter(name__contains="Burman")

exceptions = {
'Aboba' : 'aboba-bernard',
'Bernardos' : 'cano-carlos',
'Bormann' : 'bormann-carsten',
'Wesley George' : 'george-wes',
'Hinden' : 'hinden-bob',
'Hutton' : 'hutton-andy',
'Narten' : 'narten-thomas', # but there's no picture of him 
'O\'Donoghue' : 'odonoghue-karen',
'Przygienda' : 'przygienda-antoni', 
'Salowey' : 'salowey-joe',
'Patricia Thaler' : 'thaler-pat',
'Gunter Van de Velde' : 'vandevelde-gunter',
'Eric Vyncke' : 'vynke-eric',
'Zuniga' : 'zuniga-carlos-juan',
'Zhen Cao' : 'zhen-cao',

}

# Manually copied Bo Burman and Thubert Pascal from wg/photos/
# Manually copied Victor Pascual (main image, not thumb) from wg/
# Manually copied Eric Vync?ke (main image, not thumb) from wg/photos/
# Manually copied Danial King (main image, not thumb) from wg/photos/
# Manually copied the thumb (not labelled as such) for Tianran Zhou as both the main and thumb image from wg/photos/


processed_files = []

for person in sorted(list(interesting_persons),key=lambda x:x.last_name()+x.ascii):
    substr_pattern = None
    for exception in exceptions:
        if exception in person.ascii:
            substr_pattern = exceptions[exception]
            break
    if not substr_pattern:
        name_parts = person.ascii.lower().split()
        substr_pattern = '-'.join(name_parts[-1:]+name_parts[0:1])

    candidates = [x for x in old_image_files_lc if x.startswith(substr_pattern)]

    # Fixup for other exceptional cases
    if person.ascii=="Lee Howard":
        candidates = candidates[:2] # strip howard-lee1.jpg

    if person.ascii=="David Oran":
        candidates = ['oran-dave-th.jpg','oran-david.jpg']

    if person.ascii=="Susan Hares":
        candidates = ['hares-sue-th.jpg','hares-susan.jpg']

    if person.ascii=="Mahesh Jethanandani":
        candidates = ['mahesh-jethanandani-th.jpg','jethanandani-mahesh.jpg']

    if len(candidates) not in [0,2]:
        candidates = [x for x in candidates if not '00' in x]

    # At this point we either have no candidates or two. If two, the first will be the thumb

    def original_case(name):
        return old_image_files[old_image_files_lc.index(name)]

    def copy(old, new):
        global processed_files
        print("Copying", old, "to", new)
        shutil.copy(old, new)
        processed_files.append(old)
        
    if len(candidates)==2:
        old_name = original_case(candidates[1])
        old_thumb_name = original_case(candidates[0])
        old_name_ext = os.path.splitext(old_name)[1]
        old_thumb_name_ext = os.path.splitext(old_thumb_name)[1]

        new_name = person.photo_name(thumb=False)+old_name_ext.lower()
        new_thumb_name = person.photo_name(thumb=True)+old_thumb_name_ext.lower()

        copy( os.path.join(old_images_dir,old_name), os.path.join(new_images_dir,new_name) )

        #
        copy( os.path.join(old_images_dir,old_thumb_name),  os.path.join(new_images_dir,new_thumb_name) )


for file in pathlib.Path(old_images_dir).iterdir():
    if file.is_file():
        if not str(file) in processed_files:
            print("Not processed:", file.name)
