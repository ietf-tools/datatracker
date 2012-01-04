from django.db import models

'''
class AgendaItems(models.Model):
    agenda_item_id = models.IntegerField(primary_key=True)
    telechat_id = models.ForeignKey('Telechat')
    agenda_cat_id = models.IntegerField(null=True, blank=True)
    ballot_id = models.IntegerField()
    group_acronym_id = models.IntegerField()
    agenda_item_status_id = models.IntegerField(null=True, blank=True)
    iana_note = models.TextField(blank=True)
    other_note = models.TextField(blank=True)
    agenda_note_cat_id = models.IntegerField(null=True, blank=True)
    note_draft_by = models.IntegerField(null=True, blank=True)
    item_num = models.IntegerField(null=True, blank=True)
    total_num = models.IntegerField(null=True, blank=True)
    agenda_item_gr_status_id = models.IntegerField(null=True, blank=True)
    wg_action_status = models.IntegerField(null=True, blank=True)
    wg_action_status_sub = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'agenda_items'

class Telechat(models.Model):
    telechat_id = models.IntegerField(primary_key=True)
    telechat_date = models.DateField(null=True, blank=True)
    minute_approved = models.IntegerField(null=True, blank=True)
    wg_news_txt = models.TextField(blank=True)
    iab_news_txt = models.TextField(blank=True)
    management_issue = models.TextField(blank=True)
    frozen = models.IntegerField(null=True, blank=True)
    mi_frozen = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'telechat'
'''