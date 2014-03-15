Installation
============
Follow this instructions to start using dajaxice in your django project.

Installing dajaxice
-------------------

Add `dajaxice` in your project settings.py inside ``INSTALLED_APPS``::

    INSTALLED_APPS = (
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.sites',
            'dajaxice',
            ...
    )

Ensure that your ``TEMPLATE_LOADERS``, looks like the following. Probably you'll only need to uncomment the last line.::

    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
        'django.template.loaders.eggs.Loader',
    )

Ensure that ``TEMPLATE_CONTEXT_PROCESSORS`` has ``django.core.context_processors.request``. Probably you'll only need to add the last line::

    TEMPLATE_CONTEXT_PROCESSORS = (
        'django.contrib.auth.context_processors.auth',
        'django.core.context_processors.debug',
        'django.core.context_processors.i18n',
        'django.core.context_processors.media',
        'django.core.context_processors.static',
        'django.core.context_processors.request',
        'django.contrib.messages.context_processors.messages'
    )

Add ``dajaxice.finders.DajaxiceFinder`` to ``STATICFILES_FINDERS``::

    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
        'dajaxice.finders.DajaxiceFinder',
    )

Configure dajaxice url
----------------------

Add the following code inside urls.py::

    from dajaxice.core import dajaxice_autodiscover, dajaxice_config
    dajaxice_autodiscover()

Add a new line in urls.py urlpatterns with this code::

    urlpatterns = patterns('',
        ...
        url(dajaxice_config.dajaxice_url, include('dajaxice.urls')),
        ...
    )

If you aren't using ``django.contrib.staticfiles``, you should also enable it importing::

    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

and adding this line to the bottom of your urls.py::

    urlpatterns += staticfiles_urlpatterns()

Install dajaxice in your templates
----------------------------------
Dajaxice needs some JS to work. To include it in your templates, you should load ``dajaxice_templatetags`` and use ``dajaxice_js_import`` TemplateTag inside your head section. This TemplateTag will print needed js.

.. code-block:: html

    {% load dajaxice_templatetags %}

    <html>
      <head>
        <title>My base template</title>
        ...
        {% dajaxice_js_import %}
      </head>
        ...
    </html>

This templatetag will include all the js dajaxice needs.

Use Dajaxice!
-------------
Now you can create your first ajax function following the :doc:`quickstart`.
