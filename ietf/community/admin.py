# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin

from ietf.community.models import CommunityList, SearchRule, EmailSubscription

class CommunityListAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'group']
    raw_id_fields = ['user', 'group', 'added_docs']
admin.site.register(CommunityList, CommunityListAdmin)

class SearchRuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'community_list', 'rule_type', 'state', 'group', 'person', 'text']
    raw_id_fields = ['community_list', 'state', 'group', 'person', 'name_contains_index']
    search_fields = ['person__name', 'group__acronym', 'text', ]
admin.site.register(SearchRule, SearchRuleAdmin)

class EmailSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'community_list', 'email', 'notify_on']
    raw_id_fields = ['community_list', 'email']
admin.site.register(EmailSubscription, EmailSubscriptionAdmin)

