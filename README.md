<div align="center">
  
<img src="https://raw.githubusercontent.com/ietf-tools/common/main/assets/logos/datatracker.svg" alt="IETF Datatracker" height="125" />

[![Release](https://img.shields.io/github/release/ietf-tools/datatracker.svg?style=flat&maxAge=300)](https://github.com/ietf-tools/datatracker/releases)
[![License](https://img.shields.io/github/license/ietf-tools/datatracker)](https://github.com/ietf-tools/datatracker/blob/main/LICENSE)
[![Nightly Dev DB Image](https://github.com/ietf-tools/datatracker/actions/workflows/dev-db-nightly.yml/badge.svg)](https://github.com/ietf-tools/datatracker/pkgs/container/datatracker-db)  
[![Python Version](https://img.shields.io/badge/python-3.6-blue?logo=python&logoColor=white)](#prerequisites)
[![Django Version](https://img.shields.io/badge/django-2.x-51be95?logo=django&logoColor=white)](#prerequisites)
[![Node Version](https://img.shields.io/badge/node.js-16.x-green?logo=node.js&logoColor=white)](#prerequisites)
[![MariaDB Version](https://img.shields.io/badge/mariadb-10-blue?logo=mariadb&logoColor=white)](#prerequisites)

##### The day-to-day front-end to the IETF database for people who work on IETF standards.

</div>

- [**Production Website**](https://datatracker.ietf.org)
- [Changelog](https://github.com/ietf-tools/datatracker/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Git Cloning Tips](#git-cloning-tips)
    - [Code Tree Overview](#code-tree-overview)
    - [Adding a New Web Page](#adding-a-new-web-page)
    - [Testing your work](#testing-your-work)
- [Docker Dev Environment](docker/README.md)
- [Continuous Integration](#continuous-integration)
- [Database & Assets](#database--assets)
- [Bootstrap 5 Upgrade](#bootstrap-5-upgrade)

---

### Getting Started

This project is following the standard **Git Feature Workflow** development model. Learn about all the various steps of the development workflow, from creating a fork to submitting a pull request, in the [Contributing](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md) guide.

> Make sure to read the [Styleguides](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md#styleguides) section to ensure a cohesive code format across the project.

You can submit bug reports, enhancement and new feature requests in the [discussions](https://github.com/ietf-tools/datatracker/discussions) area. Accepted tickets will be converted to issues.

#### Prerequisites

- Python 3.6
- Django 2.x
- Node.js 16.x
- MariaDB 10

> See the [Docker Dev Environment](docker/README.md) section for a preconfigured docker environment.

#### Git Cloning Tips

Because of the extensive history of this project, cloning the datatracker project locally can take a long time / disk space. You can speed up the cloning process by limiting the history depth, for example:

- To fetch only up to the 10 latest commits:
    ```sh
    git clone --depth=10 https://github.com/ietf-tools/datatracker.git
    ```
- To fetch only up to a specific date:
    ```sh
    git clone --shallow-since=DATE https://github.com/ietf-tools/datatracker.git
    ```

#### Code Tree Overview

The `ietf/templates/` directory contains Django templates used to generate web pages for the datatracker, mailing list, wgcharter and other things.

Most of the other `ietf` sub-directories, such as `meeting`, contain the python/Django model and view information that go with the related templates. In these directories, the key files are:

| File | Description |
|--|--|
| urls.py | binds a URL to a view, possibly selecting some data from the model. |
| models.py | has the data models for the tool area. |
| views.py | has the views for this tool area, and is where views are bound to the template. |

#### Adding a New Web Page

To add a new page to the tools, first explore the `models.py` to see if the model you need already exists. Within `models.py` are classes such as:

```python
class IETFWG(models.Model):
    ACTIVE = 1
    group_acronym = models.ForeignKey(Acronym, primary_key=True, unique=True, editable=False)
    group_type = models.ForeignKey(WGType)
    proposed_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    dormant_date = models.DateField(null=True, blank=True)
    ...
```

In this example, the `IETFWG` class can be used to reference various fields of the database including `group_type`. Of note here is that `group_acronym` is the `Acronym` model so fields in that model can be accessed (e.g., `group_acronym.name`).

Next, add a template for the new page in the proper sub-directory of the `ietf/templates` directory. For a simple page that iterates over one type of object, the key part of the template will look something like this:

```html
{% for wg in object_list %}
<tr>
<td><a href="{{ wg.email_archive }}">{{ wg }}</a></td>
<td>{{ wg.group_acronym.name }}</td>
</tr>
{% endfor %}
```
In this case, we're expecting `object_list` to be passed to the template from the view and expecting it to contain objects with the `IETFWG` model.

Then add a view for the template to `views.py`. A simple view might look like:

```python
def list_wgwebmail(request):
    wgs = IETFWG.objects.all();
    return render_to_response('mailinglists/wgwebmail_list.html', {'object_list': wgs})
```
The selects the IETFWG objects from the database and renders the template with them in object_list. The model you're using has to be explicitly imported at the top of views.py in the imports statement.

Finally, add a URL to display the view to `urls.py`. For this example, the reference to `list_wgwebmail` view is called:

```python
urlpatterns += patterns('',
     ...
     (r'^wg/$', views.list_wgwebmail),
)
```

#### Testing your work

Assuming you have the database settings configured already, you can run the server locally with:

```sh
 $ ietf/manage.py runserver localhost:<port>
 ```
where `<port>` is arbitrary. Then connect your web browser to `localhost:<port>` and provide the URL to see your work.

When you believe you are ready to commit your work, you should run the test suite to make sure that no tests break. You do this by running

```sh
 $ ietf/manage.py test --settings=settings_sqlitetest
```

### Docker Dev Environment

In order to simplify and reduce the time required for setup, a preconfigured docker environment is available.

Read the [Docker Dev Environment](docker/README.md) guide to get started.

### Continuous Integration

*TODO*

### Database & Assets

Nightly database dumps of the datatracker are available at  
https://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz

> Note that this link is provided as reference only. To update the database in your dev environment to the latest version, you should instead run the `docker/cleandb` script!

Additional data files used by the datatracker (e.g. instance drafts, charters, rfcs, agendas, minutes, etc.) are available at  
https://www.ietf.org/standards/ids/internet-draft-mirror-sites/

> A script is available at `docker/scripts/app-rsync-extras.sh` to automatically fetch these resources via rsync.

---

# Bootstrap 5 Upgrade

An upgrade of the UI to use Bootstrap 5 is under way. The following notes describe this work-in-progress and should
be integrated with the rest of the document as the details and processes become final.

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