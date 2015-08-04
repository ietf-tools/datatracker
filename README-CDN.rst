================================================================================
		  Serving Static Datatracker Files via a CDN
================================================================================

Intro
=====

With release 6.4.0, the way that the static files used by the datatracker are
handled changes substantially.  Static files were previously versioned under a
top-level ``static/`` directory, but this is not the case any more.  External
files (such as for instance ``jquery.min.js``) are now placed under
``ietf/externals/static/`` and updated using a tool called bower_, while
datatracker-specific files (images, css, js, etc.) are located under
``ietf/static/ietf/`` and ``ietf/secr/static/secr/`` respectively.

The following sections provide more details about handling of internals,
externals, and how deployment is done.


Serving Static Files via CDN
============================

Production Mode
---------------

If resources served over a CDN and/or with a high max-age don't have different
URLs for different versions, then any component upgrade which is accompanied
by a change in template functionality will have a long transition time
during which the new pages are served with old components, with possible
breakage.  We want to avoid this.

The intention is that after a release has been checked out, but before it is
deployed, the standard django 'collectstatic' management command will be
run, resulting in all static files being collected from their working
directory location and placed in an appropiate location for serving via CDN.
This location will have the datatracker release version as part of its URL,
so that after the deployment of a new release, the CDN will be forced to fetch
the appropriate static files for that release.

An important part of this is to set up the ``STATIC_ROOT`` and ``STATIC_URL``
settings appropriately.  In 6.4.0, the setting is as follows in production
mode::

    STATIC_URL = "https://www.ietf.org/lib/dt/%s/"%__version__
    STATIC_ROOT = CDN_ROOT + "/a/www/www6s/lib/dt/%s/"%__version__

The result is that all static files collected via the ``collectstatic``
command will be placed in a location served via CDN, with the release
version being part of the URL.

Development Mode
----------------

In development mode, ``STATIC_URL`` is set to ``/static/``, and Django's
``staticfiles`` infrastructure makes the static files available under that
local URL root (unless you set
``settings.SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE`` to ``False``).  It is not
necessary to actually populate the ``static/`` directory by running
``collectstatic`` in order for static files to be served when running
``ietf/manage.py runserver`` -- the ``runserver`` command has extra support
for finding and serving static files without running collectstatic.

In order to work backwards from a file served in development mode to the
location from which it is served, the mapping is as follows::

	==============================	==============================	
	Development URL			Working copy location
	==============================	==============================	
	localhost:8000/static/ietf/*	ietf/static/ietf/*
	localhost:8000/static/secr/*	ietf/secr/static/secr/*
	localhost:8000/static/*		ietf/externals/static/*
	==============================	==============================	

Handling of External Javascript and CSS Components 
==================================================

In order to make it easy to keep track of and upgrade external components,
these are now handled by a tool called ``bower``, via a new management
command ``bower_install``.  Each external component is listed in a file
``ietf/bower.json``.  In order to update the version of a component listed in
``ietf/bower.json``, or add a new one, you should edit ``bower.json``, and
then run the management command::

    $ ietf/manage.py bower_install

(Not surprisingly, you need to have bower_ installed in order to use this
management command.)

That command will fetch the required version of each external component listed
in ``bower.json`` (actually, it will do this for *all* ``bower.json`` files
found in the ``static/`` directories of all ``INSTALLED_APPS`` and the
directories in ``settings.STATICFILES_DIRS``), saving them temporarily under
``.tmp/bower_components/``; it will then extract the relevant production
``js`` and ``css`` files and place them in an appropriately named directory
under ``ietf/externals/static/``.  The latter location is taken from
``COMPONENT_ROOT`` in ``settings.py``.

Managing external components via bower has the additional benefit of
managing dependencies -- components that have dependencies will pull in
these, so that they also are placed under ``ietf/externals/static/``.
You still have to manually add the necessary stylesheet and/or javascript
references to your templates, though.

The ``bower_install`` command is not run automatically by ``bin/mkrelease``,
since it needs an updated ``bower.json`` in order to do anything interesting.
So when you're intending to update an external web asset to a newer version,
you need to edit the ``bower.json`` file, run ``manage.py bower_install``,
verify that the new version doesn't break things, and then commit the new
files under ``ietf/externals/static/`` and the updated ``bower.json``.

.. _bower: http://bower.io/

The  ``ietf/externals/static/`` Directory
-----------------------------------------

The directory ``ietf/externals/static/`` holds a number of subdirectories
which hold distribution files for external client-side components, collected
by ``bower_install`` as described above.  Currently
(01 Aug 2015) this means ``js`` and ``css`` components and fonts.

These components each reside in their own subdirectory, which is named with
the component name::

    henrik@zinfandel $ ls -l ietf/externals/static/
    total 40
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

The ``pt*`` fonts are an exception, in that there is no bower component
available for these fonts, so they have been put in place manually.


Handling of Internal Static Files
=================================

Previous to this release, internal static files were located under
``static/``, mixed together with the external components.  They are now
located under ``ietf/static/ietf/`` and ``ietf/secr/static/secr``, and will be
collected for serving via CDN by the ``collectstatic`` command.  Any static
files associated with a particular app will be handled the same way (which
means that all ``admin/`` static files automatically will be handled correctly, too).

Handling of Customised Bootstrap Files
======================================

We are using a customised version of Bootstrap_, which is handled specially,
by a SVN externals definition in ``ietf/static/ietf``.  That pulls the content
of the ``bootstrap/dist/`` directory (which is generated by running ``grunt``
in the ``bootstrap/`` directory) into ``ietf/static/ietf/bootstrap``, from
where it is collected by ``collectstatic``.

Changes to Template Files
=========================

In order to make the template files refer to the correct versioned CDN URL
(as given by the STATIC_URL root) all references to static files in the
templates have been updated to use the ``static`` template tag when referring
to static files.  This will automatically result in both serving static files
from the right place in development mode, and referring to the correct
versioned URL in production mode and the simpler ``/static/`` urls in
development mode.

.. _bootstrap: http://getbootstrap.com/

Deployment
==========

During deployment, it is now necessary to run the management command::

  $ ietf/manage.py collectstatic

before activating a new release.  

The deployment ``README`` file at ``/a/www/ietf-datatracker/README`` has been
updated accordingly.
