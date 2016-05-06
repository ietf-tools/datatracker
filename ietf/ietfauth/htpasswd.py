import subprocess, hashlib

from django.conf import settings

def update_htpasswd_file(username, password):
    if getattr(settings, 'USE_PYTHON_HTDIGEST', None):
        pass_file = settings.HTPASSWD_FILE
        realm = settings.HTDIGEST_REALM
        prefix = '%s:%s:' % (username, realm)
        key = hashlib.md5(prefix + password).hexdigest()
        f = open(pass_file, 'r+')
        pos = f.tell()
        line = f.readline()
        while line:
            if line.startswith(prefix):
                break
            pos=f.tell()
            line = f.readline()
        f.seek(pos)
        f.write('%s%s\n' % (prefix, key))
        f.close()
    else:
        p = subprocess.Popen([settings.HTPASSWD_COMMAND, "-b", settings.HTPASSWD_FILE, username, password], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
