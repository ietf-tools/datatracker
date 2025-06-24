# Copyright The IETF Trust 2022-2025, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime
import io
import re
import xml2rfc

import debug  # pyflakes: ignore

from contextlib import contextmanager
from lxml.etree import XMLSyntaxError
from xml2rfc.util.date import augment_date, extract_date
from ietf.utils.timezone import date_today

from .draft import Draft


@contextmanager
def capture_xml2rfc_output():
    orig_write_out = xml2rfc.log.write_out
    orig_write_err = xml2rfc.log.write_err
    parser_out = io.StringIO()
    parser_err = io.StringIO()
    xml2rfc.log.write_out = parser_out
    xml2rfc.log.write_err = parser_err
    try:
        yield {"stdout": parser_out, "stderr": parser_err}
    finally:
        xml2rfc.log.write_out = orig_write_out
        xml2rfc.log.write_err = orig_write_err


class XMLDraft(Draft):
    """Draft from XML source

    Not all methods from the superclass are implemented yet.
    """
    def __init__(self, xml_file):
        """Initialize XMLDraft instance

        :parameter xml_file: path to file containing XML source
        """
        super().__init__()
        # cast xml_file to str so, e.g., this will work with a Path
        self.xmltree, self.xml_version = self.parse_xml(str(xml_file))
        self.xmlroot = self.xmltree.getroot()
        self.filename, self.revision = self.parse_docname(self.xmlroot)

    @staticmethod
    def parse_xml(filename):
        """Parse XML draft

        Converts to xml2rfc v3 schema, then returns the root of the v3 tree and the original
        xml version.
        """

        with capture_xml2rfc_output() as parser_logs:
            parser = xml2rfc.XmlRfcParser(filename, quiet=True)
            try:
                tree = parser.parse()
            except XMLSyntaxError:
                raise InvalidXMLError()
            except Exception as e:
                raise XMLParseError(
                    parser_logs["stdout"].getvalue(),
                    parser_logs["stderr"].getvalue(),
                ) from e

            xml_version = tree.getroot().get('version', '2')
            if xml_version == '2':
                v2v3 = xml2rfc.V2v3XmlWriter(tree)
                tree.tree = v2v3.convert2to3()
        return tree, xml_version

    def _document_name(self, ref):
        """Get document name from reference."""
        series = ["rfc", "bcp", "fyi", "std"]
        # handle xinclude first
        # FIXME: this assumes the xinclude is a bibxml href; if it isn't, there can
        # still be false negatives. it would be better to expand the xinclude and parse
        # its seriesInfo.
        if ref.tag.endswith("}include"):
            name = re.search(
                rf"reference\.({'|'.join(series).upper()})\.(\d{{4}})\.xml",
                ref.attrib["href"],
            )
            if name:
                return f"{name.group(1)}{int(name.group(2))}".lower()
            name = re.search(
                r"reference\.I-D\.(?:draft-)?(.*)\.xml", ref.attrib["href"]
            )
            if name:
                return f"draft-{name.group(1)}"
            # can't extract the name, give up
            return ""

        # check the anchor next
        anchor = ref.get("anchor").lower()  # always give back lowercase
        label = anchor.rstrip("0123456789")  # remove trailing digits
        maybe_number = anchor[len(label) :]
        if label in series and maybe_number.isdigit():
            number = int(maybe_number)
            return f"{label}{number}"

        # if we couldn't find a match so far, try the seriesInfo
        series_query = " or ".join(f"@name='{x.upper()}'" for x in series)
        for info in ref.xpath(
            f"./seriesInfo[{series_query} or @name='Internet-Draft']"
        ):
            if not info.attrib["value"]:
                continue
            if info.attrib["name"] == "Internet-Draft":
                return info.attrib["value"]
            else:
                return f'{info.attrib["name"].lower()}{info.attrib["value"]}'
        return ""

    def _reference_section_type(self, section_name):
        """Determine reference type from name of references section"""
        if section_name:
            section_name = section_name.lower()
            if 'normative' in section_name:
                return self.REF_TYPE_NORMATIVE
            elif 'informative' in section_name:
                return self.REF_TYPE_INFORMATIVE
        return self.REF_TYPE_UNKNOWN

    def _reference_section_name(self, section_elt):
        section_name = section_elt.findtext('name')
        if section_name is None and 'title' in section_elt.keys():
            section_name = section_elt.get('title')  # fall back to title if we have it
        return section_name

    @staticmethod
    def parse_docname(xmlroot):
        docname = xmlroot.attrib.get('docName')
        if docname is None:
            raise ValueError("Missing docName attribute in the XML root element")
        revmatch = re.match(
            r'^(?P<filename>.+?)(?:-(?P<rev>[0-9][0-9]))?$',
            docname,

        )
        if revmatch is None:
            raise ValueError('Unable to parse docName')
        # If a group had no match it is None
        return revmatch.group('filename'), revmatch.group('rev')

    def get_title(self):
        title_text = self.xmlroot.findtext('front/title')
        return "" if title_text is None else title_text.strip()

    @staticmethod
    def parse_creation_date(date_elt):
        if date_elt is None:
            return None

        today = date_today()

        # Outright reject non-numeric year / day (xml2rfc's extract_date does not do this)
        # (n.b., "year" can be non-numeric in a <reference> section per RFC 7991)
        year = date_elt.get("year")
        day = date_elt.get("day")
        non_numeric_year = year and not year.isdigit()
        non_numeric_day = day and not day.isdigit()
        if non_numeric_day or non_numeric_year:
            raise InvalidMetadataError(
                "Unable to parse the <date> element in the <front> section: "
                "year and day must be numeric values if specified."
            )

        try:
            # ths mimics handling of date elements in the xml2rfc text/html writers
            year, month, day = extract_date(date_elt, today)
            year, month, day = augment_date(year, month, day, today)
        except Exception as err:
            # Give a generic error if anything goes wrong so far...
            raise InvalidMetadataError(
                "Unable to parse the <date> element in the <front> section."
            ) from err

        if not day:
            # Must choose a day for a datetime.date. Per RFC 7991 sect 2.17, we use
            # today's date if it is consistent with the rest of the date. Otherwise,
            # arbitrariy (and consistent with the text parser) assume the 15th.
            if year == today.year and month == today.month:
                day = today.day
            else:
                day = 15

        try:
            creation_date = datetime.date(year, month, day)
        except Exception:
            # If everything went well, we should have had a valid datetime, but we didn't.
            # The parsing _worked_ but not in a way that we can go forward with.
            raise InvalidMetadataError(
                "The <date> element in the <front> section specified an incomplete date "
                "that was not consistent with today's date. If you specify only a year, "
                "it must be the four-digit current year. To use today's date, omit the "
                "date tag or use <date/>."
            )
        return creation_date

    def get_creation_date(self):
        return self.parse_creation_date(self.xmlroot.find("front/date"))

    # todo fix the implementation of XMLDraft.get_abstract()
    #
    # This code was pulled from ietf.submit.forms where it existed for some time.
    # It does not work, at least with modern xml2rfc. This assumes that the abstract
    # is simply text in the front/abstract node, but the XML schema wraps the actual
    # abstract text in <t> elements (and allows <dl>, <ol>, and <ul> as well). As a
    # result, this method normally returns an empty string, which is later replaced by
    # the abstract parsed from the rendered text. For now, I a commenting this out
    # and making it explicit that the abstract always comes from the text format.
    #
    # def get_abstract(self):
    #     """Extract the abstract"""
    #     abstract = self.xmlroot.findtext('front/abstract')
    #     return abstract.strip() if abstract else ''

    @staticmethod
    def render_author_name(author_elt):
        """Get a displayable name for an author, if possible
        
        Based on TextWriter.render_author_name() from xml2rfc. If fullname is present, uses that.
        If not, uses either initials + surname or just surname. Finally, returns None because this
        author is evidently an organization, not a person.
        
        Does not involve ascii* attributes because rfc7991 requires fullname if any of those are
        present.
        """
        # Use fullname attribute, if present
        fullname = author_elt.attrib.get("fullname", "").strip()
        if fullname:
            return fullname
        surname = author_elt.attrib.get("surname", "").strip()
        initials = author_elt.attrib.get("initials", "").strip()
        if surname or initials:
            # This allows the possibility that only initials are used, which is a bit nonsensical
            # but seems to be technically allowed by RFC 7991.
            return f"{initials} {surname}".strip()
        return None
        
    def get_author_list(self):
        """Get detailed author list

        Returns a list of dicts with the following keys:
            name, first_name, middle_initial, last_name,
            name_suffix, email, country, affiliation
        Values will be None if not available
        """
        result = []
        empty_author = {
            k: None for k in [
                'name', 'first_name', 'middle_initial', 'last_name',
                'name_suffix', 'email', 'country', 'affiliation',
            ]
        }

        for author in self.xmlroot.findall('front/author'):
            info = {
                'name': self.render_author_name(author),
                'email': author.findtext('address/email'),
                'affiliation': author.findtext('organization'),
            }
            elem = author.find('address/postal/country')
            if elem is not None:
                ascii_country = elem.get('ascii', None)
                info['country'] = ascii_country if ascii_country else elem.text
            for item in info:
                if info[item]:
                    info[item] = info[item].strip()
            result.append(empty_author | info)  # merge, preferring info
        return result

    def get_refs(self):
        """Extract references from the draft"""
        refs = {}
        # accept nested <references> sections
        for section in self.xmlroot.findall("back//references"):
            ref_type = self._reference_section_type(
                self._reference_section_name(section)
            )
            for ref in (
                section.findall("./reference")
                + section.findall("./referencegroup")
                + section.findall(
                    "./xi:include", {"xi": "http://www.w3.org/2001/XInclude"}
                )
            ):
                name = self._document_name(ref)
                if name:
                    refs[name] = ref_type
        return refs


class XMLParseError(Exception):
    """An error occurred while parsing"""
    def __init__(self, out: str, err: str, *args):
        super().__init__(*args)
        self._out = out
        self._err = err

    def parser_msgs(self):
        return self._out.splitlines() + self._err.splitlines()


class InvalidXMLError(Exception):
    """File is not valid XML"""
    pass


class InvalidMetadataError(Exception):
    """XML is well-formed but has invalid metadata"""
