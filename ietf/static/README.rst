Handling of External Javascript and CSS Components 
==================================================

This directory (``ietf/static/``) exists for the sole purpose of providing a
visible location for ``ietf/static/bower.json``, a bower_ file which lists the
external web assets used by the datatracker.

In order to update the version of a component listed in
``ietf/static/bower.json``, or add a new one, you should edit ``bower.json``,
and then run the management command::

    $ ietf/manage.py bower_install

That command will fetch the required version of each external component listed
in ``bower.json`` (actually, it will do this for *all* ``bower.json`` files
found in the ``static/`` directories of all ``INSTALLED_APPS`` and the
directories in ``settings.STATICFILES_DIRS``), saving them temporarily under
``.tmp/bower_components/``; it will then extract the relevant ``js`` and
``css`` files and place them in an appropriately named directory under
``static/lib/``.  The latter location is controlled by ``COMPONENT_ROOT`` in
``settings.py``.

(Not surprisingly, you need to have bower_ installed in order to use this
management command.)

The ``bower_install`` command is not run automatically by ``bin/mkrelease``,
since it needs an updated ``bower.json`` in order to do anything interesting;
and we're not running ``bower update`` since some package releases break
compatibility.  So when you're intending to 


.. _bower: http://bower.io/
