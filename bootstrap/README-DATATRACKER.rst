Datatracker information
_______________________

Content
=======

The files in this directory are modified versions of bootstrap v3.3.4.  This is
a cumbersome way to customize bootsrap, but as of the time of writing this
(03 Apr 2015), there seems to be no provision for including modifications
within the distributed build environment without either editing files in
place, or copying and modifying parts of the build environment.

Modifications done::

	less/variables.less	# modified with our datatracker-specific changes

Setup
=====

In order to set up things to build new static/css/bootstrap* files, do the
following (copied from http://getbootstrap.com/getting-started/#grunt)

Bootstrap uses Grunt for its build system, with convenient methods for working
with the framework. It's how we compile our code, run tests, and more.

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

Regenerates the /dist/ directory with compiled and minified CSS and JavaScript
files. As a Bootstrap user, this is normally the command you want.

::

   grunt watch			# (Watch)

Watches the Less source files and automatically recompiles them to CSS
whenever you save a change.

::

   grunt test (Run tests)

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


