Datatracker information
_______________________

Content
=======

The files in this directory are modified versions of bootstrap_.  This is
a cumbersome way to customize bootsrap, but as of the time of writing this
(03 Apr 2015), there seems to be no provision for including modifications
within the distributed build environment without either editing files in
place, or copying and modifying parts of the build environment.

Bootstrap 3.3.4 was added in [9374], see the changes with::

   $ svn diff -r 9374:9894 bootstrap/less/

Bootstrap 3.3.5 was added in [9894] and [9895], see the changes since then with::

   $ svn diff -r 9895 bootstrap/less/

Modifications done::

	less/variables.less	# modified with our datatracker-specific changes
	less/buttons.less	# added .btn-pass
	less/labels.less	# added .label-pass
	less/panels.less	# added .panel-pass
	less/mixins/forms.less	# modified inline label background-color

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
files. As a Bootstrap user, this is normally the command you want.  Changes to
the ``dist/`` directory will be picked up by ``manage.py collectstatic`` as part
of ``bin/mkrelease``.

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
