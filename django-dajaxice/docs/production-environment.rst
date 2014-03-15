Production Environment
======================

Since ``0.5`` dajaxice takes advantage of ``django.contrib.staticfiles`` so deploying a dajaxice application live is much easy than in previous versions.

You need to remember to run ``python manage.py collectstatic`` before deploying your code live. This command will collect all the static files your application need into ``STATIC_ROOT``. For further information, this is the `Django static files docuemntation <https://docs.djangoproject.com/en/dev/howto/static-files/>`_

