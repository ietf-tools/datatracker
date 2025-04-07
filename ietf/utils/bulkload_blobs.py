# Copyright The IETF Trust 2025, All Rights Reserved

import debug  # pyflakes:ignore

import datetime
import io
import rfc2html
import xml2rfc

from pathlib import Path

from django.contrib.staticfiles import finders

from django.conf import settings
from ietf.doc.storage_utils import exists_in_storage, store_bytes, store_file, store_str
from ietf.utils.log import log

from tempfile import TemporaryDirectory

from weasyprint import HTML as wpHTML
from weasyprint.text.fonts import FontConfiguration

from ietf.utils.timezone import date_today


def bulkload_all_buckets():
    bulkload_bofreq()
    bulkload_charter()
    bulkload_conflrev()
    bulkload_active_draft()
    bulkload_draft()
    bulkload_slides()
    bulkload_minutes()
    bulkload_agenda()
    bulkload_bluesheets()
    bulkload_procmaterials()
    bulkload_narrativeminutes()
    bulkload_statement()
    bulkload_statchg()
    bulkload_liai_att()
    bulkload_chatlog()
    bulkload_polls()
    bulkload_staging()
    bulkload_bibxml_ids()
    bulkload_indexes()
    bulkload_floorplan()
    bulkload_meetinghostlogo()
    bulkload_photo()
    bulkload_review()


def bulkload_bofreq():
    pass


def bulkload_charter():
    pass


def bulkload_conflrev():
    pass


def bulkload_active_draft():
    # active-draft
    pass


def bulkload_draft():

    path = Path(settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR)
    objs = path.glob("draft*")
    for obj in objs:
        if obj.suffix not in [".txt", ".p7s", ".xml", ".html", ".pdf", ".ps"]:
            continue
        name = f"{obj.suffix[1:]}/{obj.name}"
        doc_name = name[:-3]
        doc_rev = name[-3:]
        stat = obj.stat()
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
        with obj.open("rb") as file:
            content_type = ""
            text = None
            if obj.suffix == ".txt":
                content_bytes = file.read()
                try:
                    text = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    # If a latin-1 decode fails (_can_ it fail?), let this raise
                    text = content_bytes.decode("latin-1")
                    content_type = "text/plain;charset=latin-1"
            store_file(
                "draft",
                name,
                file,
                doc_name=doc_name,
                doc_rev=doc_rev,
                mtime=mtime,
                content_type=content_type,
                allow_overwrite=True,
            )
        # For now, don't try to derive things
        continue
        if obj.suffix == ".txt":
            # text will have been populated above
            htmlized = _htmlize(text)
            pdfized = _pdfize(htmlized)
            store_str(
                "draft",
                f"htmlized/{obj.stem}.html",
                htmlized,
                doc_name=doc_name,
                doc_rev=doc_rev,
                allow_overwrite=True,
            )
            store_bytes(
                "draft",
                f"pdfized/{obj.stem}.pdf",
                pdfized,
                doc_name=doc_name,
                doc_rev=doc_rev,
                allow_overwrite=True
            )
        if obj.suffix == ".xml":
            _xml2pdf(obj, doc_name, doc_rev)


def bulkload_slides():
    pass


def bulkload_minutes():
    pass


def bulkload_agenda():
    pass


def bulkload_bluesheets():
    pass


def bulkload_procmaterials():
    pass


def bulkload_narrativeminutes():
    pass


def bulkload_statement():
    pass


def bulkload_statchg():
    pass


def bulkload_liai_att():
    # liai-att
    pass


def bulkload_chatlog():
    pass


def bulkload_polls():
    pass


def bulkload_staging():
    pass


def bulkload_bibxml_ids():
    # bibxml-ids
    pass


def bulkload_indexes():
    pass


def bulkload_floorplan():
    pass


def bulkload_meetinghostlogo():
    pass


def bulkload_photo():
    pass


def bulkload_review():
    pass


def _htmlize(text):
    html = rfc2html.markup(text, path=settings.HTMLIZER_URL_PREFIX)
    html = f'<div class="rfcmarkup">{html}</div>'
    return html


def _pdfize(htmlized):
    stylesheets = [finders.find("ietf/css/document_html_referenced.css")]
    stylesheets.append(
        f"{settings.STATIC_IETF_ORG_INTERNAL}/fonts/noto-sans-mono/import.css"
    )

    try:
        font_config = FontConfiguration()
        pdf = wpHTML(string=htmlized, base_url=settings.IDTRACKER_BASE_URL).write_pdf(
            stylesheets=stylesheets,
            font_config=font_config,
            presentational_hints=True,
            optimize_images=True,
        )
    except AssertionError:
        pdf = None
    except Exception as e:
        log("weasyprint failed:" + str(e))
        raise
    return pdf


def _xml2pdf(xml_obj, doc_name, doc_rev):
    target = f"pdf/{doc_name}-{doc_rev}.pdf"
    if not exists_in_storage("draft", target):
        xml2rfc_stdout = io.StringIO()
        xml2rfc_stderr = io.StringIO()
        xml2rfc.log.write_out = xml2rfc_stdout
        xml2rfc.log.write_err = xml2rfc_stderr

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            parser = xml2rfc.XmlRfcParser(str(xml_obj), quiet=True)
            try:
                # --- Parse the xml ---
                xmltree = parser.parse(remove_comments=False)
            except Exception as err:
                raise xml2rfc.XmlRfcError(
                    "Error parsing XML",
                    xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                    xml2rfc_stderr=xml2rfc_stderr.getvalue(),
                ) from err
            # If we have v2, run it through v2v3. Keep track of the submitted version, though.
            xmlroot = xmltree.getroot()
            xml_version = xmlroot.get("version", "2")
            if xml_version == "2":
                v2v3 = xml2rfc.V2v3XmlWriter(xmltree)
                try:
                    xmltree.tree = v2v3.convert2to3()
                except Exception as err:
                    raise xml2rfc.XmlRfcError(
                        "Error converting v2 XML to v3",
                        xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                        xml2rfc_stderr=xml2rfc_stderr.getvalue(),
                    ) from err

            # --- Prep the xml ---
            today = date_today()
            prep = xml2rfc.PrepToolWriter(
                xmltree, quiet=True, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET]
            )
            prep.options.accept_prepped = True
            prep.options.date = today
            try:
                xmltree.tree = prep.prep()
            except xml2rfc.RfcWriterError:
                raise xml2rfc.XmlRfcError(
                    f"Error during xml2rfc prep: {prep.errors}",
                    xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                    xml2rfc_stderr=xml2rfc_stderr.getvalue(),
                )
            except Exception as err:
                raise xml2rfc.XmlRfcError(
                    "Unexpected error during xml2rfc prep",
                    xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                    xml2rfc_stderr=xml2rfc_stderr.getvalue(),
                ) from err

            # --- Convert to pdf ---
            pdf_path = temp_path / f"{xml_obj.stem}.pdf"
            writer = xml2rfc.PdfWriter(xmltree, quiet=True)
            writer.options.date = today
            try:
                writer.write(str(pdf_path))
            except Exception as err:
                raise xml2rfc.XmlRfcError(
                    "Error generating PDF format from XML",
                    xml2rfc_stdout=xml2rfc_stdout.getvalue(),
                    xml2rfc_stderr=xml2rfc_stderr.getvalue(),
                ) from err
            log(
                "In %s: xml2rfc %s generated %s from %s (version %s)"
                % (
                    str(xml_obj.parent),
                    xml2rfc.__version__,
                    pdf_path.name,
                    xml_obj.name,
                    xml_version,
                )
            )
            with Path(pdf_path).open("rb") as f:
                store_file("draft", f"pdf/{doc_name}-{doc_rev}.pdf", f, allow_overwrite=True)
