# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import subprocess, hashlib
from django.utils.encoding import force_bytes

from django.conf import settings

def update_htpasswd_file(username, password):
    if getattr(settings, 'USE_PYTHON_HTDIGEST', None):
        pass_file = settings.HTPASSWD_FILE
        realm = settings.HTDIGEST_REALM
        prefix = force_bytes('%s:%s:' % (username, realm))
        key = force_bytes(hashlib.md5(prefix + force_bytes(password)).hexdigest())
        f = io.open(pass_file, 'r+b')
        pos = f.tell()
        line = f.readline()
        while line:
            if line.startswith(prefix):
                break
            pos=f.tell()
            line = f.readline()
        f.seek(pos)
        f.write(b'%s%s\n' % (prefix, key))
        f.close()
    else:
        p = subprocess.Popen([settings.HTPASSWD_COMMAND, "-b", settings.HTPASSWD_FILE, username, password], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
