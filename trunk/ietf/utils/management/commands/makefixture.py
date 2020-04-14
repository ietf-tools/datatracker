# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# From https://github.com/ericholscher/django-test-utils/blob/master/test_utils/management/commands/makefixture.py


"""
"Make fixture" command.

Highly useful for making test fixtures. Use it to pick only few items
from your data to serialize, restricted by primary keys. By default
command also serializes foreign keys and m2m relations. You can turn
off related items serialization with --skip-related option.

How to use:
python manage.py makefixture

will display what models are installed

python manage.py makefixture User[:3]
or
python manage.py makefixture auth.User[:3]
or
python manage.py makefixture django.contrib.auth.User[:3]

will serialize users with ids 1 and 2, with assigned groups, permissions
and content types.

python manage.py makefixture YourModel[3] YourModel[6:10]

will serialize YourModel with key 3 and keys 6 to 9 inclusively.

Of course, you can serialize whole tables, and also different tables at
once, and use options of dumpdata:

python manage.py makefixture --format=xml --indent=4 YourModel[3] AnotherModel auth.User[:5] auth.Group
"""
# From http://www.djangosnippets.org/snippets/918/

#save into anyapp/management/commands/makefixture.py
#or back into django/core/management/commands/makefixture.py
#v0.1 -- current version
#known issues:
#no support for generic relations
#no support for one-to-one relations

from django.core import serializers
from django.core.management.base import CommandError
from django.core.management.base import LabelCommand
from django.db.models.fields.related import ForeignKey
from django.db.models.fields.related import ManyToManyField
from django.apps import apps

DEBUG = True

def model_name(m):
    module = m.__module__.split('.')[:-1] # remove .models
    return ".".join(module + [m._meta.object_name])

class Command(LabelCommand):
    help = 'Output the contents of the database as a fixture of the given format.'
    args = 'modelname[pk] or modelname[id1:id2] repeated one or more times'

    def add_arguments(self, parser):
        parser.add_argument('--skip-related', default=True, action='store_false', dest='propagate',
            help='Specifies if we shall not add related objects.')
        parser.add_argument('--reverse', default=[], action='append', dest='reverse',
            help="Reverse relations to follow (e.g. 'Job.task_set').")
        parser.add_argument('--format', default='json', dest='format',
            help='Specifies the output serialization format for fixtures.')
        parser.add_argument('--indent', default=None, dest='indent', type=int,
            help='Specifies the indent level to use when pretty-printing output')

    def handle_reverse(self, **options):
        follow_reverse = options.get('reverse', [])
        to_reverse = {}
        for arg in follow_reverse:
            try:
                model_name, related_set_name = arg.rsplit(".", 1)
            except:
                raise CommandError("Bad fieldname on '--reverse %s'" % arg)
            model = self.get_model_from_name(model_name)
            try:
                getattr(model, related_set_name)
            except AttributeError:
                raise CommandError("Field '%s' does not exist on model '%s'" % (
                                   related_set_name, model_name))
            to_reverse.setdefault(model, []).append(related_set_name)
        return to_reverse

    def handle_models(self, models, **options):
        format = options.get('format','json')
        indent = options.get('indent',None)
        show_traceback = options.get('traceback', False)
        propagate = options.get('propagate', True)
        follow_reverse = self.handle_reverse(**options)

        # Check that the serialization format exists; this is a shortcut to
        # avoid collating all the objects and _then_ failing.
        if format not in serializers.get_public_serializer_formats():
            raise CommandError("Unknown serialization format: %s" % format)

        try:
            serializers.get_serializer(format)
        except KeyError:
            raise CommandError("Unknown serialization format: %s" % format)

        objects = []
        for model, slice in models:
            if isinstance(slice, str) and slice:
                objects.extend(model._default_manager.filter(pk__exact=slice))
            elif not slice or type(slice) is list:
                items = model._default_manager.all()
                if slice and slice[0]:
                    items = items.filter(pk__gte=slice[0])
                if slice and slice[1]:
                    items = items.filter(pk__lt=slice[1])
                items = items.order_by(model._meta.pk.attname)
                objects.extend(items)
            else:
                raise CommandError("Wrong slice: %s" % slice)

        all = objects
        collected = set([(x.__class__, x.pk) for x in all])
        related = []
        for obj in objects:
            # follow reverse relations as requested
            for reverse_field in follow_reverse.get(obj.__class__, []):
                mgr = getattr(obj, reverse_field)
                for new in mgr.all():
                    if new and not (new.__class__, new.pk) in collected:
                        collected.add((new.__class__, new.pk))
                        related.append(new)
        objects += related
        all.extend(related)
        if propagate:
            while objects:
                related = []
                for obj in objects:
                    if DEBUG:
                        print("Adding %s[%s]" % (model_name(obj), obj.pk))
                    # follow forward relation fields
                    for f in obj.__class__._meta.fields + obj.__class__._meta.many_to_many:
                        if isinstance(f, ForeignKey):
                            new = getattr(obj, f.name) # instantiate object
                            if new and not (new.__class__, new.pk) in collected:
                                collected.add((new.__class__, new.pk))
                                related.append(new)
                        if isinstance(f, ManyToManyField):
                            for new in getattr(obj, f.name).all():
                                if new and not (new.__class__, new.pk) in collected:
                                    collected.add((new.__class__, new.pk))
                                    related.append(new)
                objects = related
                all.extend(related)

        try:
            return serializers.serialize(format, all, indent=indent)
        except Exception as e:
            if show_traceback:
                raise
            raise CommandError("Unable to serialize database: %s" % e)

    def get_models(self):
        return [(m, model_name(m)) for m in apps.get_models()]

    def get_model_from_name(self, search):
        """Given a name of a model, return the model object associated with it

The name can be either fully specified or uniquely matching the
end of the model name. e.g.
django.contrib.auth.User
or
auth.User
raises CommandError if model can't be found or uniquely determined
"""
        models = [model for model, name in self.get_models()
                        if name.endswith('.'+name) or name == search]
        if not models:
            raise CommandError("Unknown model: %s" % search)
        if len(models)>1:
            raise CommandError("Ambiguous model name: %s" % search)
        return models[0]

    def handle_label(self, labels, **options):
        parsed = []
        for label in labels:
            search, pks = label, ''
            if '[' in label:
                search, pks = label.split('[', 1)
            slice = ''
            if ':' in pks:
                slice = pks.rstrip(']').split(':', 1)
            elif pks:
                slice = pks.rstrip(']')
            model = self.get_model_from_name(search)
            parsed.append((model, slice))
        return self.handle_models(parsed, **options)

    def list_models(self):
        names = [name for _model, name in self.get_models()]
        raise CommandError('Neither model name nor slice given. Installed model names: \n%s' % ",\n".join(names))

    def handle(self, *labels, **options):
        if not labels:
            self.list_models()

        output = []
        label_output = self.handle_label(labels, **options)
        if label_output:
            output.append(label_output)
        return '\n'.join(output)
