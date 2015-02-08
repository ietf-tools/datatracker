# -*- coding: utf-8 -*-
from __future__ import print_function
from django.conf import settings
from south.v2 import DataMigration
from ietf.utils.management.commands.import_htpasswd import import_htpasswd_file

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        # Note: Don't use "from appname.models import ModelName". 
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.
        print("Importing password hashes from %s," % settings.HTPASSWD_FILE)
        print("leaving entries without matching usernames alone.")
        import_htpasswd_file(settings.HTPASSWD_FILE, verbosity=2)

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        
    }

    complete_apps = ['ietfauth']
    symmetrical = True
