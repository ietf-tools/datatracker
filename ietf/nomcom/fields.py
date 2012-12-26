import tempfile
from django.conf import settings
from django.db import models

from ietf.utils.pipe import pipe


class EncryptedException(Exception):
    pass


class EncryptedTextField(models.TextField):
    def pre_save(self, instance, add):
        if add:
            comments = getattr(instance, 'comments')
            position = getattr(instance, 'position')
            cert_file = position.nomcom.public_key.path
            comments_file = tempfile.NamedTemporaryFile()
            comments_file.write(comments)

            code, out, error = pipe("%s smime -encrypt -in %s %s" % (settings.OPENSSL_COMMAND,
                                    comments_file.name,
                                    cert_file))
            comments_file.close()
            if not error:
                instance.comments = out
                return out
            else:
                raise EncryptedException(error)
        else:
            return instance.comments
