<div align="center">
  
<img src="media/docs/ietf-datatracker-logo.svg" alt="IETF Datatracker" width="600" />

[![Release](https://img.shields.io/github/release/ietf-tools/datatracker.svg?style=flat&maxAge=3600)](https://github.com/ietf-tools/datatracker/releases)
[![License](https://img.shields.io/badge/license-BSD3-blue.svg?style=flat)](https://github.com/ietf-tools/datatracker/blob/main/LICENSE)
![Nightly DB Build](https://img.shields.io/github/workflow/status/ietf-tools/datatracker/dev-db-nightly?label=Nightly%20DB%20Build&style=flat&logo=docker&logoColor=white&maxAge=3600)

##### The day-to-day front-end to the IETF database for people who work on IETF standards.

</div>

- [**Production Website**](https://datatracker.ietf.org)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Code Tree Overview](#code-tree-overview)
    - [Adding a New Web Page](#adding-a-new-web-page)
    - [Testing your work](#testing-your-work)
- [Docker Dev Environment](#docker-dev-environment)
- [Continuous Integration](#continuous-integration)
- [Database & Assets](#database--assets)

---

### Getting Started

This project is following the standard **Git Feature Workflow with Develop Branch** development model. Learn about all the various steps of the development workflow, from creating a fork to submitting a pull request, in the [Contributing](CONTRIBUTING.md) guide.

> Make sure to read the [Styleguides](CONTRIBUTING.md#styleguides) section to ensure a cohesive code format across the project.

You can submit bug reports, enhancement and new feature requests in the [discussions](https://github.com/ietf-tools/datatracker/discussions) area. Accepted tickets will be converted to issues.

#### Prerequisites

- Python 3.6
- Django 2.x
- Node.js 16.x
- MariaDB 10

> See the [Docker Dev Environment](#docker-dev-environment) section below for a preconfigured docker environment.

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
