# IETF Datatracker

## Intro

We now use `npm` to manage assets for the Datatracker, and `parcel` to
package them. `npm` maintains its `node` packages under `node_modules`.

The Datatracker includes these packages from the various Javascript and
CSS files in `ietf/static/js` and `ietf/static/css`, respectively.
Static images are likewise in `ietf/static/images`.

Whenever changes are made to the files under `ietf/static`, you must
re-run `parcel` to package them:

``` shell
npx parcel build
```

This will create packages under `ietf/static/dist/ietf`, which are then
served by the Django development server, and which must be uploaded to
the CDN.

## Use Bootstrap Whenever You Can

The "new" datatracker uses Twitter Bootstrap for the UI.

Get familiar with <https://getbootstrap.com/getting-started/> and use
those UI elements, CSS classes, etc. instead of cooking up your own.

Some ground rules:

-   Think hard before tweaking the bootstrap CSS, it will make it harder
    to upgrade to future releases.
-   No `<style>` tags in the HTML! Put CSS into the "morecss" block of
    a template instead.
-   CSS that is used by multiple templates goes into static/css/ietf.css
    or a new CSS file.
-   Javascript that is only used on one template goes into the "js"
    block of that template.
-   Javascript that is used by multiple templates goes into
    static/js/ietf.js or a new js file.
-   Every template includes jquery, so write jquery code and not plain
    Javascript. It's shorter and often faster.
-   Avoid CSS, HTML styling or Javascript in the python code!

## Serving Static Files via CDN

### Production Mode

If resources served over a CDN and/or with a high max-age don't have
different URLs for different versions, then any component upgrade which
is accompanied by a change in template functionality will have a long
transition time during which the new pages are served with old
components, with possible breakage. We want to avoid this.

The intention is that after a release has been checked out, but before
it is deployed, the standard django `collectstatic` management command
will be run, resulting in all static files being collected from their
working directory location and placed in an appropriate location for
serving via CDN. This location will have the datatracker release version
as part of its URL, so that after the deployment of a new release, the
CDN will be forced to fetch the appropriate static files for that
release.

An important part of this is to set up the `STATIC_ROOT` and
`STATIC_URL` settings appropriately. In 6.4.0, the setting is as follows
in production mode:

```
STATIC_URL = "https://www.ietf.org/lib/dt/%s/"%__version__
STATIC_ROOT = CDN_ROOT + "/a/www/www6s/lib/dt/%s/"%__version__
```

The result is that all static files collected via the `collectstatic`
command will be placed in a location served via CDN, with the release
version being part of the URL.

### Development Mode

In development mode, `STATIC_URL` is set to `/static/`, and Django's
`staticfiles` infrastructure makes the static files available under that
local URL root (unless you set
`settings.SERVE_CDN_FILES_LOCALLY_IN_DEV_MODE` to `False`). It is not
necessary to actually populate the `static/` directory by running
`collectstatic` in order for static files to be served when running
`ietf/manage.py runserver` -- the `runserver` command has extra support
for finding and serving static files without running collectstatic.

In order to work backwards from a file served in development mode to the
location from which it is served, the mapping is as follows:

| Development URL | Working copy location |
| --------------- | --------------------- |
| localhost:8000/static/ietf/*  |  ietf/static/ietf/* |
| localhost:8000/static/secr/*  |  ietf/secr/static/secr/*|

## Handling of External Javascript and CSS Components

In order to make it easy to keep track of and upgrade external
components, these are now handled by a tool called `npm` via the
configuration in `package.json`.

## Handling of Internal Static Files

Previous to this release, internal static files were located under
`static/`, mixed together with the external components. They are now
located under `ietf/static/ietf/` and `ietf/secr/static/secr`, and will
be collected for serving via CDN by the `collectstatic` command. Any
static files associated with a particular app will be handled the same
way (which means that all `admin/` static files automatically will be
handled correctly, too).

## Changes to Template Files

In order to make the template files refer to the correct versioned CDN
URL (as given by the STATIC_URL root) all references to static files in
the templates have been updated to use the `static` template tag when
referring to static files. This will automatically result in both
serving static files from the right place in development mode, and
referring to the correct versioned URL in production mode and the
simpler `/static/` URLs in development mode.

## Deployment

During deployment, it is now necessary to run the management command:

``` shell
ietf/manage.py collectstatic
````
before activating a new release.