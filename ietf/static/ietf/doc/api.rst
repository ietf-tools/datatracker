=====================
Datatracker API Notes
=====================


Framework
=========

The api uses tastypie (https://django-tastypie.readthedocs.org/)
to generate an API which mirrors the Django ORM (Object Relational Mapping)
for the database.  Each Django model class maps down to the SQL database
tables and up to the API.  The Django models classes are defined in the
models.py files of the datatracker:

  http://svn.tools.ietf.org/svn/tools/ietfdb/trunk/ietf/doc/models.py
  http://svn.tools.ietf.org/svn/tools/ietfdb/trunk/ietf/group/models.py
  http://svn.tools.ietf.org/svn/tools/ietfdb/trunk/ietf/iesg/models.py
  ...

The API top endpoint is at https://datatracker.ietf.org/api/v1/.  The top
endpoint lists inferior endpoints, and thus permits some autodiscovery,
but there's really no substitute for looking at the actual ORM model classes.
Comparing a class in models.py with the equivalent endpoint may give
some clue (note that in the case of Group, it's a subclass of GroupInfo):

  https://datatracker.ietf.org/api/v1/group/group/
  https://trac.tools.ietf.org/tools/ietfdb/browser/trunk/ietf/group/models.py#L14

Data is currently provided in JSON and XML format.  Adding new formats is
fairly easy, if it should be found desriable.


Documents
=========

Documents are listed at https://datatracker.ietf.org/api/v1/doc/document/ .

In general, individual database objects are represented in the api with a path
composed of the model collection, the object name, and the object key.  Most
objects have simple numerical keys, but documents have the document name as
key.  Take draft-ietf-eppext-keyrelay.  Documents have a model 'Document' which
is described in the 'doc' models.py file.  Assembling the path components
'doc', 'document' (lowercase!) and 'draft-ietf-eppext-keyrelay', we get the
URL:

  https://datatracker.ietf.org/api/v1/doc/document/draft-ietf-eppext-keyrelay/

If you instead do a search for this document, you will get a machine-readable
search result, which is composed of some meta-information about the search,
and a list with one element:

  https://datatracker.ietf.org/api/v1/doc/document/?name=draft-ietf-eppext-keyrelay

To search for documents based on state, you need to know that documents have
multiple orthogonal states:

- If a document has an rfc-editor state, you can select for it by asking for
  documents which match 'states__type__slug__in=draft-rfceditor'::

    $ curl 'https://datatracker.ietf.org/api/v1/doc/document/?limit=0&name__contains=-v6ops-&states__type__slug__in=draft-rfceditor' | python -m json.tool

- If a document has an iesg state, you can select for it by asking for
  documents which match ``'states__type__slug__in=draft-iesg'``

- If a document has a WG state, you can select for it by asking for
  documents which match ``'states__type__slug__in=draft-stream-ietf'``

- States which match ``'states__type__slug__in=draft'`` describe the basic
  Active/Expired/Dead whatever state of the draft.

You could use this in at least two alternative ways:

You could either fetch and remember the different state groups of interest to you
with queries like::

  $ curl 'https://datatracker.ietf.org/api/v1/doc/state/?format=json&limit=0&type__slug__in=draft-rfceditor'

  $ curl 'https://datatracker.ietf.org/api/v1/doc/state/?format=json&limit=0&type__slug__in=draft-iesg'

  $ curl 'https://datatracker.ietf.org/api/v1/doc/state/?format=json&limit=0&type__slug__in=draft-stream-ietf'

and then match the listed "resource_uri" of the results to the states listed for each
document when you ask for:

  $ curl 'https://datatracker.ietf.org/api/v1/doc/document/?limit=0&name__contains=-v6ops-'

Or alternatively you could do a series of queries asking for matches to the RFC Editor
state first, then the IESG state, then the Stream state, and exclude earlier hits:

  $ curl 'https://datatracker.ietf.org/api/v1/doc/document/?limit=0\\
	&name__contains=-v6ops-&states__type__slug__in=draft-rfceditor' ...

  $ curl 'https://datatracker.ietf.org/api/v1/doc/document/?limit=0\\
	&name__contains=-v6ops-&states__type__slug__in=draft-iesg' ...

etc.
