from django.conf import settings
from django.db import models
from django.utils.encoding import smart_str

from ietf.utils.pipe import pipe


class EncryptedException(Exception):
    pass


class EncryptedTextField(models.TextField):
    def pre_save(self, instance, add):
        if add:
            comments = smart_str(getattr(instance, 'comments'))
            nomcom = getattr(instance, 'nomcom')
            cert_file = nomcom.public_key.path

            code, out, error = pipe("%s smime -encrypt -in /dev/stdin %s" % (settings.OPENSSL_COMMAND,
                                    cert_file), comments)
            if code != 0:
                log("openssl error: %s:\n  Error %s: %s" %(command, code, error))        
            if not error:
                instance.comments = out
                return out
            else:
                raise EncryptedException(error)
        else:
            return instance.comments
