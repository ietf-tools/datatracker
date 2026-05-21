# Copyright The IETF Trust 2026, All Rights Reserved
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import quoteattr as qa

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from lxml import etree

from ietf.doc.models import Document
from ietf.utils.log import log


def save_to_bucket(filename: str, content: str | bytes):
    bibxml_bucket = storages["bibxml_bucket"]
    bucket_path = str(Path(getattr(settings, "BIBXML_OUTPUT_PATH", "")) / filename)
    if getattr(settings, "BIBXML_DELETE_THEN_WRITE", True):
        # Django 4.2's FileSystemStorage does not support allow_overwrite.
        bibxml_bucket.delete(bucket_path)
    bibxml_bucket.save(
        bucket_path,
        ContentFile(content if isinstance(content, bytes) else content.encode("utf-8")),
    )
    log(f"Saved {bucket_path} in bibxml_bucket storage")


def get_rfc_bibxml(rfc_number):
    """Return BibXML entry for the given rfc"""

    rfc = Document.objects.get(rfc_number=rfc_number)
    link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"rfc{rfc_number}")
    date = rfc.pub_date().strftime('<date month="%B" year="%Y"/>')
    authors = ""

    for author in rfc.rfcauthor_set.all():
        if author.is_editor:
            author_entry = f"""<author fullname={qa(author.titlepage_name)} surname={qa(author.titlepage_name.split(".")[-1].strip())} role="editor"/>"""
        else:
            author_entry = f"""<author fullname={qa(author.titlepage_name)} surname={qa(author.titlepage_name.split(".")[-1].strip())}/>"""
        authors += author_entry

    return f"""<reference anchor="RFC{rfc_number}" target="{link}"><front><title>{rfc.title}</title>{date}{authors}<abstract><t>{rfc.abstract}</t></abstract></front><seriesInfo name="RFC" value="{rfc_number}"/><seriesInfo name="DOI" value="{rfc.doi}"/></reference>"""


def save_bibxml(bibxml, filename):
    """Prettify and save given BibXML"""

    # make it pretty
    pretty_bibxml = etree.tostring(
        etree.fromstring(bibxml),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=4,
    )
    save_to_bucket(filename, pretty_bibxml)


def recreate_rfc_bibxml():
    """Creates BibXML for all RFCs."""
    for rfc_number in Document.objects.filter(type_id="rfc").values_list(
        "rfc_number", flat=True
    ):
        filename = f"bibxml/rfc{rfc_number}.xml"
        bibxml = get_rfc_bibxml(rfc_number)
        save_bibxml(bibxml, filename)
