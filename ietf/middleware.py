
# From http://www.djangosnippets.org/snippets/172/
# Uses python-utidylib, http://utidylib.berlios.de/,
# which uses HTML Tidy, http://tidy.sourceforge.net/

import tidy

options = dict(
               output_xhtml=True,
#               add_xml_decl=True,
#               doctype='transitional',
               indent=True,
               tidy_mark=False,
#               hide_comments=True,
               wrap=100)


class PrettifyMiddleware(object):
    """Prettify middleware"""

    def process_response(self, request, response):
        if response.headers['Content-Type'].split(';', 1)[0] in ['text/html']:
            content = response.content
            content = str(tidy.parseString(content, **options))
            response.content = content
        return response
