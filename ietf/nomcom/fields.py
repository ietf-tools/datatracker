from django.conf import settings
from django.db import models

from ietf.utils.pipe import pipe


class EncryptedException(Exception):
    pass


class EncryptedTextField(models.TextField):
    def pre_save(self, instance, add):
        if add:
            comments = getattr(instance, 'comments')
            nomcom = getattr(instance, 'nomcom')
            cert_file = nomcom.public_key.path

            code, out, error = pipe("%s smime -encrypt -in /dev/stdin %s" % (settings.OPENSSL_COMMAND,
                                    cert_file), comments)
            if not error:
                instance.comments = out
                return out
            else:
                raise EncryptedException(error)
        else:
            return instance.comments
