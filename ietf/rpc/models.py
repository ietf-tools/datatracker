from django.db import models

from ietf.doc.models import Document
from ietf.name.models import StdLevelName, StreamName, SourceFormatName, TlpBoilerplateChoiceName


class RfcToBe(models.Model):
    """
    
    Notes:
     * not in_progress and not published = abandoned without publication
    """
    in_progress = models.BooleanField(default=True)
    published = models.DateTimeField(null=True)  # should match a DocEvent on the rfc Document
    is_april_first_rfc = models.BooleanField(default=False)
    draft = models.ForeignKey(Document, null=True, on_delete=models.PROTECT)  # only null if is_april_first_rfc is True
    cluster = models.ForeignKey("Cluster", null=True, on_delete=models.SET_NULL)

    submitted_format = models.ForeignKey(SourceFormatName, on_delete=models.PROTECT)
    submitted_std_level = models.ForeignKey(StdLevelName, on_delete=models.PROTECT)
    submitted_boilerplate = models.ForeignKey(TlpBoilerplateChoiceName, on_delete=models.PROTECT)
    submitted_stream = models.ForeignKey(StreamName, on_delete=models.PROTECT)

    intended_std_level = models.ForeignKey(StdLevelName, on_delete=models.PROTECT)
    intended_boilerplate = models.ForeignKey(TlpBoilerplateChoiceName, on_delete=models.PROTECT)
    intended_stream = models.ForeignKey(StreamName, on_delete=models.PROTECT)

    external_deadline = models.DateTimeField(null=True)
    internal_goal = models.DateTimeField(null=True)

    class Meta:
        # todo validator to enforce draft null only if is_april_first_rfc
        pass

    
class Cluster(models.Model):
    pass

