Datatracker information
_______________________

Content
=======

The files in this directory are standard drop of the bootstrap sources (at
the moment 3.3.6). All modifications are contained in less/ietf.less, which
is included in modified less/theme.less and less/bootstrap.less.  This lets
ietf.less override variables defined in variables.less.  ietf.less also adds
a few additional styles that complement those defined in other less files
(mostly, the various *-pass styles.)

When upgrading to a new version of bootstrap, make sure to add

  @import "ietf.less"

after each import of less/variables.less. At the moment, the only two locations
where this occurs are in less/theme.less and less/bootstrap.less.


Setup
=====

Bootstrap uses Grunt for its build system, with convenient methods for working
with the framework. It's how we compile our code, run tests, and more.

In order to set up things to build new ``static/lib/bootstrap/**`` files, do the
following (copied from http://getbootstrap.com/getting-started/#grunt):


Installing Grunt
----------------

To install Grunt, you must first download and install node.js (which includes
npm). npm stands for node packaged modules and is a way to manage development
dependencies through node.js.

Then, from the command line: Install grunt-cli globally with ::

   npm install -g grunt-cli.

Navigate to the root /bootstrap/ directory, then run::

   npm install

npm will look at the package.json file and automatically install the necessary
local dependencies listed there.

When completed, you'll be able to run the various Grunt commands provided from
the command line.

Usage
=====

Available Grunt commands
------------------------

::

   grunt dist			# (Just compile CSS and JavaScript)

Regenerates the ``dist/`` directory with compiled and minified CSS and JavaScript
files. As a Bootstrap user, this is normally the command you want.  Changes in the
``dist/`` directory which are committed to the svn repository will be replicated in
the ``ietf/static/ietf/bootstrap`` directory through and svn:externals declaration.

During development, you'll need to manually rsync newly generated files in place
after doing ``grunt dist``:  ``rsync -a dist/ ../ietf/static/ietf/bootstrap/``)

During deployment, they will be picked up by ``manage.py collectstatic`` and placed
in the production environment's static directory.

::

   grunt watch			# (Watch)

Watches the Less source files and automatically recompiles them to CSS
whenever you save a change.

::

   grunt test			# (Run tests)

Runs JSHint and runs the QUnit tests headlessly in PhantomJS.

::

   grunt docs			# (Build & test the docs assets)

Builds and tests CSS, JavaScript, and other assets which are used when running
the documentation locally via jekyll serve.

::

   grunt			# (Build absolutely everything and run tests)

Compiles and minifies CSS and JavaScript, builds the documentation website,
runs the HTML5 validator against the docs, regenerates the Customizer assets,
and more. Requires Jekyll. Usually only necessary if you're hacking on
Bootstrap itself.


.. _bootstrap: http://getbootstrap.com
