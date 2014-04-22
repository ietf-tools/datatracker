Changelog
=========

0.5.5
^^^^^
* Return XMLHttpRequest from concreate functions as well as from function call.
* Fixed django 1.5 compatibility: Content-Type have to be application/x-www-form-urlencoded otherwise Django discards POST data.
* Fix JS generation errors
* Fix @dajaxice_register legacy decorator

0.5.4.1
^^^^^^^
* Fix JS generation errors.

0.5.4
^^^^^
* Fix JS generation errors.

0.5.3
^^^^^
* Fix some Windows bugs.
* Fix some JS generation errors.
* Make dajaxice use CSRF_COOKIE_NAME.

0.5.2
^^^^^
* Fix GET dajaxice requests in order to send args as part of the url.

0.5.1
^^^^^
* Make django-dajaxice work with django 1.3
* Fix installation steps
* Update json2.js

0.5
^^^
* General Project clean-up
* Django>=1.3 is now a requirement
* Fixed numerous CSRF issues
* Dajaxice now use django.contrib.staticfiles
* Fix SERVER_ROOT_URL issues
* Fixed js_core issues accepting multiple arguments
* New upgraded documentation
* Marketing site (http://dajaxproject.com) is now open-source
* Fix JS generation issues
* Travis-ci integration


0.2
^^^
* Fix bug with the 'is_callback_a_function' variable in dajaxice.core.js
* Fix bug with csrftoken in landing pages using dajaxice.
* Improve reliability handling server errors.
* Exception handling was fully rewritten. Dajaxice default_error_callback is now configurable using Dajaxice.setup.
* Custom error messages per dajaxice call.
* Dajaxice now propagate docstrings to javascript dajaxice functions.
* Added DAJAXICE_JS_DOCSTRINGS to configure docstrings propagation behaviour, default=False.
* Updated installation guide for compatibility with django 1.3
* dajaxice now uses the logger 'dajaxice' and not 'dajaxice.DajaxiceRequest'
* Documentation Updated.

0.1.8.1
^^^^^^^
* Fixed bug #25 related to CSRF verification on Django 1.2.5

0.1.8
^^^^^
* Add build dir to ignores
* Remove MANIFEST file and auto-generate it through MANIFEST.in
* Add MANIFEST to ignores
* Include examples and docs dirs to source distribution
* Add long_description to setup.py
* Fixed Flaw in AJAX CSRF handling (X-CSRFToken Django 1.2.5)

0.1.7
^^^^^
* Fixing dajaxice callback model to improve security against XSS attacks.
* Dajaxice callbacks should be passed as functions and not as strings.
* Old string-callback maintained for backward compatibility.(usage not recommended)
* New documentation using Sphinx
* Adding a decorators.py file with a helper decorator to register functions (Douglas Soares de Andrade)

0.1.6
^^^^^
* Fixing registration bugs
* Added some tests

0.1.5
^^^^^
* Now dajaxice functions must be registered using dajaxice_functions.register instead of adding that functions to DAJAXICE_FUNCTIONS list inside settings.py. This pattern is very similar to django.contrib.admin model registration.
* Now dajaxice functions could be placed inside any module depth.
* With this approach dajaxice app reusability was improved.
* Old style registration (using DAJAXICE_FUNCTIONS) works too, but isn't recommended.
* New tests added.

0.1.3
^^^^^
* CSRF middleware buf fixed
* Improved production and development logging
* New custom Exception message
* New notify_exception to send traceback to admins
* Fixed semicolon issues
* Fixed unicode errors
* Fixed generate_static_dajaxice before easy_install usage
* Fixed IE6 bug in dajaxice.core.js

0.1.2
^^^^^
* New and cleaned setup.py

0.1.1
^^^^^
* json2.js and XMLHttpRequest libs included
* New settings DAJAXICE_XMLHTTPREQUEST_JS_IMPORT and DAJAXICE_JSON2_JS_IMPORT

0.1.0
^^^^^
* dajaxice AJAX functions now receive parameters as function arguments.
* dajaxice now uses standard python logging
* some bugs fixed

0.0.1
^^^^^
* First Release
