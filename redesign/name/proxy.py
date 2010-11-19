from redesign.proxy_utils import TranslatingManager
from models import *

class IDStatus(DocStateName):
    def __init__(self, base):
        for f in base._meta.fields:
            setattr(self, f.name, getattr(base, f.name))
    
    #status_id = models.AutoField(primary_key=True)
    
    #status = models.CharField(max_length=25, db_column='status_value')
    @property
    def status(self):
        return self.name

    def __unicode__(self):
        return super(self.__class__, self).__unicode__()
    
    class Meta:
        proxy = True
