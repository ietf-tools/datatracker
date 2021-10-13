# Datatracker Development in Docker

1. [Set up Docker](https://docs.docker.com/get-started/) on your preferred
   platform.

2. If you have a copy of the datatracker code checked out already, simply `cd`
   to the top-level directory.

   If not, check out a datatracker branch as usual. We'll check out `trunk`
   below, but you can use any branch:

       svn co https://svn.ietf.org/svn/tools/ietfdb/trunk
       cd trunk

3. **TEMPORARY:** Replace the contents of the `docker` directory with Lars'
   files.

4. **TEMPORARY:** Until Lars' changes have been merged and a docker image is
   available for download, you will need to build it locally:

       docker/build -l

    This will take a while, but only needs to be done once.

5. Use the `docker/run` script to start the datatracker container. You will be
   dropped into a shell from which you can start the datatracker and execute
   related commands as usual, for example:

       ietf/manage.py runserver 0.0.0.0:8000

   If you do not already have a copy of the IETF database available in the
   `data` directory, one will be downloaded and imported the first time you run
   `docker/run`. This will take some time.

   Once the datatracker has started, you should be able to open
   [http://localhost:8000](http://localhost:8000) in a browser and see the
   landing page.