# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import models
from django.utils.encoding import smart_str

from ietf.utils.pipe import pipe
from ietf.utils.log import log

class EncryptedException(Exception):
    pass

class EncryptedTextField(models.TextField):
    def pre_save(self, instance, add):
        if add:
            comments = smart_str(getattr(instance, 'comments'))
            nomcom = getattr(instance, 'nomcom')
            try:
                cert_file = nomcom.public_key.path
            except ValueError as e:
                raise ValueError("Trying to read the NomCom public key: " + str(e))

            command = "%s smime -encrypt -in /dev/stdin %s" % (settings.OPENSSL_COMMAND, cert_file)
            code, out, error = pipe(command, comments.encode('utf-8'))
            if code != 0:
                log("openssl error: %s:\n  Error %s: %s" %(command, code, error))
            if not error:
                instance.comments = out
                return out
            else:
                raise EncryptedException(error)
        else:
            return instance.comments
