Migrating to 0.5
=================

Upgrade to django 1.3 or 1.4
----------------------------

Dajaxice ``0.5`` requires ``django>=1.3``, so in order to make dajaxice work you'll need to upgrade your app to any of these ones.

* `Django 1.3 release notes <https://docs.djangoproject.com/en/dev/releases/1.3/>`_
* `Django 1.4 release notes <https://docs.djangoproject.com/en/dev/releases/1.4/>`_


Make django static-files work
-----------------------------

Add this at the beginning of your ``urls.py`` file::

    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

and add this line to the bottom of your urls.py::

    urlpatterns += staticfiles_urlpatterns()

Add a new staticfiles finder named ``dajaxice.finders.DajaxiceFinder`` to the list of ``STATICFILES_FINDERS``::

    STATICFILES_FINDERS = ('django.contrib.staticfiles.finders.FileSystemFinder',
                           'django.contrib.staticfiles.finders.AppDirectoriesFinder',
                           'dajaxice.finders.DajaxiceFinder')

Update dajaxice core url
------------------------

Add ``dajaxice_config`` to the list of modules to import::

    # Old import
    from dajaxice.core import dajaxice_autodiscover

    # New import
    from dajaxice.core import dajaxice_autodiscover, dajaxice_config


And replate your old dajaxice url with the new one::

    # Old style
    (r'^%s/' % settings.DAJAXICE_MEDIA_PREFIX, include('dajaxice.urls')),

    # New style
    url(dajaxice_config.dajaxice_url, include('dajaxice.urls')),


Done!
-----

Your app should be working now!
You can now read the :doc:`quickstart <quickstart>` to discover some of the new dajaxice features.
