from django.core.mail import EmailMessage


class IETFEmailMessage(EmailMessage):

    def __init__(self, *args, **kwargs):
        cc = kwargs.pop('cc', [])
        if cc:
            assert isinstance(cc, (list, tuple)), '"cc" argument must be a list or tuple'
            self.cc = list(cc)
        else:
            self.cc = []
        super(IETFEmailMessage, self).__init__(*args, **kwargs)

    def message(self):
        msg = super(IETFEmailMessage, self).message()
        if self.cc:
            msg['Cc'] = ', '.join(self.cc)
        if self.bcc:
            msg['Bcc'] = ', '.join(self.bcc)
        return msg

    def recipients(self):
        return self.to + self.cc + self.bcc
