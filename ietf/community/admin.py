# Copyright The IETF Trust 2017-2019, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from ietf.community.models import CommunityList, SearchRule, EmailSubscription

class CommunityListAdmin(admin.ModelAdmin):
    list_display = [u'id', 'user', 'group']
    raw_id_fields = ['user', 'group']
admin.site.register(CommunityList, CommunityListAdmin)

class SearchRuleAdmin(admin.ModelAdmin):
    list_display = [u'id', 'community_list', 'rule_type', 'state', 'group', 'person', 'text']
    raw_id_fields = ['community_list', 'state', 'group', 'person', 'name_contains_index']
admin.site.register(SearchRule, SearchRuleAdmin)

class EmailSubscriptionAdmin(admin.ModelAdmin):
    list_display = [u'id', 'community_list', 'email', 'notify_on']
    raw_id_fields = ['community_list', 'email']
admin.site.register(EmailSubscription, EmailSubscriptionAdmin)

