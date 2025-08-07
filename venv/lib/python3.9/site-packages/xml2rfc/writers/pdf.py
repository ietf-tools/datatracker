# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

import io
import logging
import os
import re


try:
    import weasyprint
    import_error = None
except (ImportError, OSError, ValueError) as e:
    import_error = e
    weasyprint = False


import xml2rfc
from xml2rfc.writers.base import default_options, BaseV3Writer
from xml2rfc.writers.html import HtmlWriter
from xml2rfc.util.fonts import get_noto_serif_family_for_script


try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass


NOTO_SYMBOLS = ["NotoSansSymbols2", "NotoSansMath",]


class PdfWriter(BaseV3Writer):

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None):
        super(PdfWriter, self).__init__(xmlrfc, quiet=quiet, options=options, date=date)
        if not weasyprint:
            self.err(None, "Cannot run PDF formatter: %s" % import_error)
            return

        logging.basicConfig(level=logging.INFO)

        loggers = []
        loggers.append(logging.getLogger("weasyprint"))
        loggers.append(logging.getLogger("fontTools.subset"))
        loggers.append(logging.getLogger("fontTools.ttLib"))
        loggers.append(logging.getLogger("fontTools.varlib"))
        for _logger in loggers:
            if   self.options.quiet:
                _logger.setLevel(logging.CRITICAL)
            elif self.options.verbose:
                _logger.setLevel(logging.WARNING)
            elif self.options.debug:
                _logger.setLevel(logging.DEBUG)
            else:
                _logger.setLevel(logging.ERROR)

    def pdf(self):
        if not weasyprint:
            return None

        if not self.root.get('prepTime'):
            prep = xml2rfc.PrepToolWriter(self.xmlrfc, options=self.options, date=self.options.date, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
            tree = prep.prep()
            self.tree = tree
            self.root = self.tree.getroot()

        self.options.no_css = True
        self.options.pdf = True
        htmlwriter = HtmlWriter(self.xmlrfc, quiet=True, options=self.options, date=self.date)
        html = htmlwriter.html()

        html = self.flatten_unicode_spans(html)

        writer = weasyprint.HTML(string=html, base_url="")

        cssin  = self.options.css or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'xml2rfc.css')
        css = weasyprint.CSS(cssin)

        # fonts and page info
        fonts = self.get_serif_fonts()
        mono_fonts = self.get_mono_fonts()
        page_info = {
            'top-left': self.page_top_left(),
            'top-center': self.full_page_top_center(),
            'top-right': self.page_top_right(),
            'bottom-left': self.page_bottom_left(),
            'bottom-center': self.page_bottom_center(),
            'fonts': ', '.join(fonts),
            'mono-fonts': ', '.join(mono_fonts),
        }
        for (k,v) in page_info.items():
            page_info[k] = v.replace("'", r"\'")
        page_css_text = page_css_template.format(**page_info)
        page_css = weasyprint.CSS(string=page_css_text)

        pdf = writer.write_pdf(None, stylesheets=[ css, page_css ], presentational_hints=True)

        return pdf


    def write(self, filename):
        if not weasyprint:
            return

        self.filename = filename

        pdf = self.pdf()
        if pdf:
            with io.open(filename, 'bw') as file:
                file.write(pdf)
            
            if not self.options.quiet:
                self.log(' Created file %s' % filename)
        else:
            self.err(None, 'PDF creation failed')

    def get_serif_fonts(self):
        fonts = set()
        scripts = self.root.get("scripts").split(",")
        noto_serif = "Noto Serif"
        for script in scripts:
            family = get_noto_serif_family_for_script(script)
            fonts.add("%s" % family)
        fonts -= set([ noto_serif, ])
        fonts = [noto_serif,] + NOTO_SYMBOLS + list(fonts)
        self.note(None, "Found installed font: %s" % ", ".join(fonts))
        return fonts

    def get_mono_fonts(self):
        fonts = set()
        scripts = self.root.get('scripts').split(',')
        roboto_mono = "Roboto Mono"
        noto_sans_mono = "Noto Sans Mono"
        for script in scripts:
            family = get_noto_serif_family_for_script(script)
            fonts.add("%s" % family)
        fonts = [ roboto_mono, noto_sans_mono, ] + NOTO_SYMBOLS + list(fonts)
        self.note(None, "Found installed font: %s" % ', '.join(fonts))
        return fonts

    def flatten_unicode_spans(self, html):
        # This is a fix for bug in WeasyPrint that doesn't handle RTL unicode
        # content correctly.
        # See #873 & Kozea/WeasyPrint#1711
        return re.sub(r'<span class="unicode">(?P<unicode_content>.*?)</span>',
                      r'\g<unicode_content>',
                      html)


page_css_template = """
@media print {{
  body {{
    font-family: {fonts};
    width: 100%;
  }}
  tt, code, pre {{
    font-family: {mono-fonts};
  }}
  sup {{
    line-height: 0;
  }}
  @page {{
    size: A4;
    font-size: 12px; /* needed for the page header and footer text */
    font-family: {fonts};

    border-top: solid 1px #ccc;
    padding-top: 18px;

    padding-bottom: 24px;
    border-bottom: solid 1px #ccc;
    margin-bottom: 45mm;

    @top-left {{
      content: '{top-left}';
      vertical-align: bottom;
      border-bottom: 0px;
      margin-bottom: 1em;
    }}
    @top-center {{
      content: '{top-center}';
      vertical-align: bottom;
      border-bottom: 0px;
      margin-bottom: 1em;
    }}
    @top-right {{
      content: '{top-right}';
      vertical-align: bottom;
      border-bottom: 0px;
      margin-bottom: 1em;
    }}
    @bottom-left {{
      content: '{bottom-left}';
      vertical-align: top;
      border-top: 0px;
      margin-top: 1em;
    }}
    @bottom-center {{
      content: '{bottom-center}';
      vertical-align: top;
      border-top: 0px;
      margin-top: 1em;
    }}
    @bottom-right {{
      content: 'Page ' counter(page);
      vertical-align: top;
      border-top: 0px;
      margin-top: 1em;
    }}
  }}
  #toc nav ul li p a:nth-child(2)::after {{
    content: target-counter(attr(href), page);
    position: absolute;
    right: 0px;
    text-indent: 0px;
  }}
}}
"""


