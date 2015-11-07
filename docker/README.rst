
====================================================
Datatracker Development in a Docker Container (beta)
====================================================

Intro
=====

Docker_ is a set of tools which lets you package software together with its
dependencies in lightweight containers, and run it in isolated virtual environments.

During and just after IETF-94 I've spent quite a bit of time setting up a docker
image which provides the dependencies needed to run the datatracker, and it's now
available for beta testing.  Hopefully this should make it substantially easier to
get started with datatracker development.

Steps
=====

1. Set up Docker on your preferred platform.  Official installers
   exist for many Linux flavours, OS X, Windows and Cloud services.

   Docker containers require the services of an underlying Linux API,
   which means that on OS X and Windows, these have to be provided
   by a virtual machine which runs a minimal Linux image.  The virtual
   machine used is commonly VirtualBox, although at least one
   unofficial VM image and controller (boot2docker_) also supports
   Parallels, XenServer and VMWare.

   The primary installers available is the unofficial boot2docker_ and
   the official `Docker Engine`_.  I've tried both, and at this time,
   November 2015, boot2docker has worked much better for me than
   Docker Engine.  YMMV.

   Boot2docker can self-upgrade and provides up-to-date docker server
   and clients.  Run update after you install::

      ~ $ boot2docker upgrade

2. Check out your datatracker branch as usual, in a suitable directory.
   We'll assume ``~/src/dt/`` here, and assume you are ``'coder'``::

      ~/src/dt/ $ svn co https://svn.tools.ietf.org/svn/tools/ietfdb/personal/coder/6.8.2.dev0

3. In the checked-out working copy, you'll find a ``data/`` directory
   at the top level.  Fetch down a pre-built copy of the datatracker
   database, place it in this directory, unpack it, and fix permissions::

      ~/src/dt/6.8.2.dev0/data/ $ wget https://www.ietf.org/lib/dt/sprint/ietf_utf8.bin.tar.bz2 .
      ~/src/dt/6.8.2.dev0/data/ $ tar xjf ietf_utf8.bin.tar.bz2
      ~/src/dt/6.8.2.dev0/data/ $ chmod -R go+rwX mysql

4. In the checked-out working copy, you'll also find a ``docker/``
   directory at the top level.  It contains a Dockerfile which can
   be used to build a docker image, but that doesn't concern us at
   the moment.  We will be using a wrapper script, ``'run'``, to
   run a pre-built docker image fetched from the docker hub::

      ~/src/dt/6.8.2.dev0/docker/ $ ./run

   This will pull down the latest docker datatracker image, start it
   up with appropriate settings, map the internal ``/var/lib/mysql/``
   directory to the external ``data/mysql/`` directory where we placed
   the database, set up a python virtualenv for you, install some
   dependencies, and drop you in a bash shell where you can run the
   datatracker.

5. Make sure that all requirements are installed::

      (virtual) $ cd ~/src/dt/6.8.2.dev0
      (virtual) $ pip install -r requirements.txt

6. You are now ready to run the tests::

      (virtual) $ ietf/manage.py test --settings=settings_sqlitetest

   and then start the dev server::

      (virtual) $ ietf/manage.py runserver 0.0.0.0:8000

   Note the IP address ``0.0.0.0`` used to make the dev server bind
   to all addresses.  The internal port 8000 has been mapped to port
   8000 externally, too.  In order to find the IP address of the
   VirtualBox, run ``'$ boot2docker ip'`` or equivalent *outside* the
   virtual environment::

      ~/src/dt/6.8.2.dev0/ $ boot2docker ip
      192.168.59.103

      ~/src/dt/6.8.2.dev0/ $ open http://192.168.59.103:8000/


..  _Docker: https://www.docker.com/
..  _`Docker Engine`: https://docs.docker.com/engine/installation/
..  _boot2docker: http://boot2docker.io/
..  _VirtualBox: https://www.virtualbox.org/


