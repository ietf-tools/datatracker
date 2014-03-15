.. django-dajaxice documentation master file, created by
   sphinx-quickstart on Fri May 25 08:02:23 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


django-dajaxice
===============

Dajaxixe is an Easy to use AJAX library for django. Its main goal is to trivialize the asynchronous communication within the django server code and your js code. Dajaxice uses the unobtrusive standard-compliant (W3C) XMLHttpRequest 1.0 object.

django-dajaxice is a **JS-framework agnostic** library and focuses on decoupling the presentation logic from the server-side logic. dajaxice only requieres **5 minutes to start working.**

Dajaxice has the following aims:

* Isolate the communication between the client and the server.
* JS Framework agnostic (No Prototype, JQuery... needed ).
* Presentation logic outside the views (No presentation code inside ajax functions).
* Lightweight.
* Crossbrowsing ready.
* `Unobtrusive standard-compliant (W3C) XMLHttpRequest 1.0 <http://code.google.com/p/xmlhttprequest/>`_ object usage.

Documentation
-------------
.. toctree::
   :maxdepth: 2

   installation
   quickstart

   custom-error-callbacks
   utils
   production-environment
   migrating-to-05
   available-settings

   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

