import sys, os, argparse

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path = [ basedir ] + sys.path
os.environ["DJANGO_SETTINGS_MODULE"] = "ietf.settings"

virtualenv_activation = os.path.join(basedir, "env", "bin", "activate_this.py")
if os.path.exists(virtualenv_activation):
    execfile(virtualenv_activation, dict(__file__=virtualenv_activation))

import django
django.setup()

from django.conf import settings

from ietf.doc.models import Document
from ietf.utils.draft import Draft

parser = argparse.ArgumentParser()
parser.add_argument("--document", help="specific document name")
parser.add_argument("--words", action="store_true", help="fill in word count")
args = parser.parse_args()


docs_qs = Document.objects.filter(type="draft")

if args.document:
    docs_qs = docs_qs.filter(docalias__name=args.document)

for doc in docs_qs.prefetch_related("docalias_set"):
    canonical_name = doc.name
    for n in doc.docalias_set.all():
        if n.name.startswith("rfc"):
            canonical_name = n.name

    if canonical_name.startswith("rfc"):
        path = os.path.join(settings.RFC_PATH, canonical_name + ".txt")
    else:
        path = os.path.join(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR, canonical_name + "-" + doc.rev + ".txt")

    if not os.path.exists(path):
        print "skipping", doc.name, "no txt file found at", path
        continue

    with open(path, 'r') as f:
        d = Draft(f.read(), path)

        updates = {}

        if args.words:
            words = d.get_wordcount()
            if words != doc.words:
                updates["words"] = words

        if updates:
            Document.objects.filter(pk=doc.pk).update(**updates)
            print "updated", canonical_name

