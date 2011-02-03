from ietf.submit.models import IdSubmissionStatus

class ErrorManager(object):
    ERROR_CODES = {
        'DEFAULT': 'Unknow error',
        'INVALID_FILENAME': 111,
        'EXCEEDED_SIZE': 102,
    }

    def get_error_str(self, key):
        error_code = self.ERROR_CODES.get(key, self.ERROR_CODES['DEFAULT'])
        if isinstance(error_code, basestring):
            return '%s (%s)' % (key, error_code)
        try:
            return IdSubmissionStatus.objects.get(status_id=error_code).status_value
        except IdSubmissionStatus.DoesNotExist:
            return '%s (%s)' % (self.ERROR_CODES['DEFAULT'], key)

MainErrorManager=ErrorManager()
