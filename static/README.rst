Handling of External Javascript and CSS Components 
==================================================

This directory (``static/``) holds a number of subdirectories, where one is handled
differently than the rest: the ``lib/`` subdirectory holds distribution files for external
client-side components, currently (18 Apr 2015) this means ``js`` and ``css`` components.

These components each reside in their own subdirectory, which is named with the component
name:

    henrik@zinfandel $ ls -l static/lib
    total 44
    drwxr-xr-x 6 henrik henrik 4096 Jul 25 15:25 bootstrap
    drwxr-xr-x 4 henrik henrik 4096 Jul 25 15:25 bootstrap-datepicker
    drwxr-xr-x 4 henrik henrik 4096 Jul 25 15:25 font-awesome
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:25 jquery
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:25 jquery.cookie
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:24 ptmono
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:24 ptsans
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:24 ptserif
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:25 select2
    drwxr-xr-x 2 henrik henrik 4096 Jul 25 15:25 select2-bootstrap-css

If resources served over a CDN and/or with a high max-age don't have different URLs for
different versions, then any component upgrade which is accompanied by a change in template
functionality will be have a long transition time during which the new pages are served with
old components, with possible breakage.  We want to avoid this.

The intention is that after a release has been checked out, but before it is deployed,
the whole static directory should be copied to a location which is accessible under the
URL given by STATIC_URL -- in production mode this URL contains the datatracker release
version, which will let the CDN serve the static files which correspond to the current
release.

With the exception of the ``pt*`` fonts, all components under ``static/lib/`` are managed
through a bower_ file; ``ietf/static/bower.json``.  In order to install a new
version of a component, you should update the ``bower.json`` file, and then run the management
command::

    $ ietf/manage.py bower_install

That command will fetch the required version of each external component listed in
``bower.json`` (actually, it will do this for *all* ``bower.json`` files found in the
``static/`` directories of all ``INSTALLED_APPS``), saving them temporarily under
``.tmp/bower_components/``; it will then extract the relevant ``js`` and ``css`` files and
place them in an appropriately named directory under ``static/lib/``.  The location
used by ``bower_install`` is is controlled by ``COMPONENT_ROOT`` in ``settings.py``.

Any datatracker-specific static files which should be served by the CDN rather than
directly by the datatracker web server should be moved from under ``static/ to ``ietf/static/``,
so that they will be collected by the ``ietf/manage.py collectstatic`` command and
placed under `static/lib/`` from where they will be made available to the CDN.  Any
template files referencing the files in question will need to be updated to use the
``{% static 'foo/bar.jpg' %}`` notation to reference the files, so that the correct
static url will be emitted.

.. _bower: http://bower.io/
