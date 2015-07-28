Handling of External Javascript and CSS Components 
==================================================

The file ``bower.json`` in this direcory is a bower_ file which lists the
external web assets used by the datatracker.

In order to update the version of a component listed in ``ietf/bower.json``,
or add a new one, you should edit ``bower.json``, and then run the management
command::

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
compatibility.  So when you're intending to update an external web asset to a
newer version, you need to edit the ``bower.json`` file, run ``manage.py
bower_install``, verify that the new version doesn't break things, and then
commit the new files under ``static\lib\`` and the updated ``bower.json``.

.. _bower: http://bower.io/
