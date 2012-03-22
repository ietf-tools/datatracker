from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
        (r'^search/$', "ietf.person.views.ajax_search_emails", None, 'ajax_search_emails'),
)
