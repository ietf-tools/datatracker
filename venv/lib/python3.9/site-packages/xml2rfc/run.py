#!/usr/bin/env python

from __future__ import print_function, unicode_literals

import platformdirs
import configargparse
import datetime
import io
import json
import lxml.etree
import os
import pycountry
import sys

# If this script is renamed to 'xml2rfc.py' on a Windows system, the import
# of the real xml2rfc module will break.  In order to handle this, we remove
# the directory of the script file from the python system path:
script_dir = os.path.dirname(os.path.realpath(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)

import xml2rfc

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass


def get_missing_pdf_libs():
    missing = ""
    if not xml2rfc.HAVE_WEASYPRINT:
        missing += "\nCould not import weasyprint"
    if not xml2rfc.HAVE_PANGO:
        missing += "\nCould not find the pango lib"
    return missing


def print_pi_help(options, parser):
    pis = xml2rfc.parser.XmlRfc(None, None).pis.items()
    pis.sort()
    print("Available processing instructions (PIs), with defaults:\n")
    for k, v in pis:
        if isinstance(v, type('')):
            print('    %-20s  "%s"' % (k,v))
        else:
            print('    %-20s  %s' % (k,v))
    sys.exit()


def print_country_help(options, parser):
    from xml2rfc.util.postal import country_alias
    country_ids = {}
    for c in list(pycountry.countries):
        key = c.alpha_2
        country_ids[key] = []
        for a in ['alpha_2', 'alpha_3', 'name', 'official_name', ]:
            if hasattr(c, a):
                v = getattr(c, a)
                if not v in country_ids[key]:
                    country_ids[key].append(v)
    for k, v in country_alias.items():
        c = pycountry.countries.lookup(v)
        if not k in country_ids[c.alpha_2]:
            country_ids[c.alpha_2].append(k)
    ids = list(country_ids.values())
    ids.sort()
    print('Known country codes and country names for use with <country>:\n')
    print(('\n'.join([ '  '+'  -  '.join(v) for v in ids])))
    sys.exit()


def get_pdf_help(missing_libs=""):
    pdf_requirements_info = """
    In order to generate PDFs, xml2rfc uses the WeasyPrint library, which
    depends on external libraries that must be installed as native packages.

    1. First, install the Pango, and other required libraries on your
    system.  See installation instructions on the WeasyPrint Docs:
    
        https://doc.courtbouillon.org/weasyprint/stable/first_steps.html

    2. Next, install weasyprint python modules using pip.

        pip install "xml2rfc[pdf]"

    3. Finally, install the required fonts:
       * Download latest fonts from xml2rfc-fonts.
         https://github.com/ietf-tools/xml2rfc-fonts/releases/latest

       * In the "Assets" section, download either the tar.gz or
         the zip archive.

       * Extract the contents of the downloaded xml2rfc-fonts archive.

       * Install the fonts found in the noto and roboto_mono directories
         to your operating system.

    With these libraries, modules, and fonts installed and available to
    xml2rfc, the --pdf switch will be enabled.
    """
    return pdf_requirements_info + missing_libs


def print_pdf_help(options, parser):
    print(get_pdf_help())
    sys.exit()


def print_version(options, parser):
    versions = xml2rfc.get_versions()
    print('%s %s' % versions[0])
    if options.verbose:
        for item in versions[1:]:
            print('  %s %s' % item)

def print_values(options, parser, config_paths):
    print("\n"
          + parser.format_values()
          + "%s\n  %s" % ('Config file search path:', config_paths))
    

def extract_anchor_info(xml):
    info = {
        'version': 1,
        'sections': {},
        }
    for item in xml.xpath('./middle//section'):
        anchor = item.get('anchor')
        label  = item.get('pn')
        if anchor and label and not anchor.startswith('anchor-'):
            info['sections'][anchor] = label.replace('section-','')
    return info

optionparser = None

def main():
    global optionparser
    # Populate options
    config_paths = ['/etc/xml2rfc.conf', '~/.xml2rfc.conf']
    user_conf = os.path.join(platformdirs.user_config_dir(), 'xml2rfc.conf')
    if not user_conf in config_paths:
        config_paths.append(user_conf)

    optionparser = configargparse.ArgumentParser(usage='xml2rfc [OPTIONS] SOURCE [OPTIONS]'
                                        '...\nExample: xml2rfc '
                                        'draft.xml -b draft-foo-19 --text --html',
                                        add_help=False,
                                        add_config_file_help=False,
                                        default_config_files=config_paths,
                                    )
    input_options = optionparser.add_argument_group('Positional arguments')
    input_options.add_argument('source', nargs='?', help="Input XML file to render to one or more of the available formats.")

    help_options = optionparser.add_argument_group('Documentation options',
                    'Some options to generate built-in documentation.')
    help_options.add_argument('-h', '--help', action='help',
                           help='show a help message and exit')
    help_options.add_argument('--docfile', action='store_true',
                           help='generate a documentation XML file ready for formatting')
    help_options.add_argument('--manpage', action='store_true',
                           help='show paged text documentation')
    help_options.add_argument('--country-help', action="store_true",
                            help='show the recognized <country> strings')
    help_options.add_argument('--pdf-help', action="store_true",
                            help='show pdf generation requirements')
#     help_options.add_argument('--pi-help', action="store_true",
#                             help='show the names and default values of PIs (for v2)')
    help_options.add_argument('--template-dir', 
                            help='directory to pull the doc.xml and doc.yaml templates from.  '
                                 'The default is the "templates" directory of the xml2rfc package')
    help_options.add_argument('--values', action='store_true', 
                            help='show option values and from where they come')
    help_options.add_argument('-V', '--version', action='store_true', 
                            help='display the version number and exit')
    help_options.add_argument('--warn-bare-unicode', action='store_true', default=False,
                            help='Warn use of bare Unicode in tags where bare use of Unicode should be closely inspected')

    formatgroup = optionparser.add_argument_group('Format selection',
                            'One or more of the following output formats may be specified. '
                            'The default is --text. The destination filename will be based '
                            'on the input filename, unless --out=FILE or --basename=BASE '
                            'is used.')
    formatgroup.add_argument('--text', action='store_true',
                           help='outputs formatted text to file, with proper page breaks')
    formatgroup.add_argument('--html', action='store_true',
                           help='outputs formatted HTML to file')
    formatgroup.add_argument('--nroff', action='store_true',
                           help='outputs formatted nroff to file (only v2 input)')
    if xml2rfc.HAVE_PANGO:
        formatgroup.add_argument('--pdf', action='store_true',
                               help='outputs formatted PDF to file')
    else:
        formatgroup.add_argument('--pdf', action='store_true',
                               help='(unavailable due to missing external library)')
    formatgroup.add_argument('--raw', action='store_true',
                           help='outputs formatted text to file, unpaginated (only v2 input)')
    formatgroup.add_argument('--expand', action='store_true',
                           help='outputs XML to file with all references expanded')
    formatgroup.add_argument('--use-bib', action='store_true',
                           help='update all datatracker references with bib.ietf.org')
    formatgroup.add_argument('--v2v3', action='store_true',
                           help='convert vocabulary version 2 XML to version 3')
    formatgroup.add_argument('--preptool', action='store_true',
                           help='run preptool on the input')
    formatgroup.add_argument('--unprep', action='store_true',
                           help='reduce prepped xml to unprepped')
    formatgroup.add_argument('--info', action='store_true',
                           help='generate a JSON file with anchor to section lookup information')


    plain_options = optionparser.add_argument_group('Generic Switch Options')
    plain_options.add_argument('-C', '--clear-cache', action='store_true', default=False,
                            help='purge the cache and exit')
    plain_options.add_argument(      '--debug', action='store_true',
                            help='Show debugging output')
    plain_options.add_argument('-n', '--no-dtd', action='store_true',
                            help='disable DTD validation step')
    plain_options.add_argument('-N', '--no-network', action='store_true', default=False,
                            help='don\'t use the network to resolve references')
    plain_options.add_argument('-O', '--no-org-info', dest='first_page_author_org', action='store_false', default=True,
                            help='don\'t show author organization info on page one (legacy only)')
    plain_options.add_argument('-q', '--quiet', action='store_true',
                            help="don't print anything while working")
    plain_options.add_argument('--skip-config-files', action="store_true", default=False,
                            help='ignore config file settings')
    plain_options.add_argument('--allow-local-file-access', action="store_true", default=False,
                            help='Allow local file system references')
    plain_options.add_argument('-r', '--remove-pis', action='store_true', default=False,
                            help='Remove XML processing instructions')
    plain_options.add_argument('-u', '--utf8', action='store_true',
                            help='generate utf8 output')
    plain_options.add_argument('-v', '--verbose', action='store_true',
                            help='print extra information')


    value_options = optionparser.add_argument_group('Generic Options with Values')
    value_options.add_argument('-b', '--basename', dest='basename', metavar='NAME',
                            help='specify the base name for output files')
    value_options.add_argument('-c', '--cache', dest='cache', metavar='PATH',
                            help='specify a primary cache directory to write to; default: try [ %s ]'%', '.join(xml2rfc.CACHES) )
    value_options.add_argument(      '--config-file', dest="config_file", metavar='FILE', is_config_file_arg=True,
                            help='specify a configuration file')
    value_options.add_argument('-d', '--dtd', dest='dtd', metavar='DTDFILE', help='specify an alternate dtd file')
    value_options.add_argument('-D', '--date', dest='datestring', metavar='DATE', default=None,
                            help="run as if the date is DATE (format: yyyy-mm-dd).  Default: Today's date")
    value_options.add_argument('-f', '--filename', dest='filename', metavar='FILE',
                            help='Deprecated.  The same as -o')
    value_options.add_argument('-i', '--indent', type=int, default=2, metavar='INDENT',
                            help='With some v3 formatters: Indentation to use when pretty-printing XML')
    value_options.add_argument('-o', '--out', dest='output_filename', metavar='FILE',
                            help='specify an explicit output filename')
    value_options.add_argument('-p', '--path', dest='output_path', metavar='PATH',
                            help='specify the directory path for output files')
    value_options.add_argument('-s', '--silence', action='append', type=str, metavar='STRING',
                            help="Silence any warning beginning with the given string")

    formatoptions = optionparser.add_argument_group('Generic Format Options')
    formatoptions.add_argument('--v3', action='store_true', default=True,
                           help='with --text and --html: use the v3 formatter, rather than the legacy one')
    formatoptions.add_argument('--legacy', '--v2', dest='v3', action='store_false',
                           help='with --text and --html: use the legacy output formatters, rather than the v3 ones')
    formatoptions.add_argument('--id-is-work-in-progress', default=True, action='store_true',
                           help='in references, refer to Internet-Drafts as "Work in Progress"')

    textoptions = optionparser.add_argument_group('Text Format Options')
    textoptions.add_argument('--no-headers', dest='omit_headers', action='store_true',
                           help='calculate page breaks, and emit form feeds and page top'
                           ' spacing, but omit headers and footers from the paginated format')
    textoptions.add_argument('--legacy-list-symbols', default=False, action='store_true',
                           help='use the legacy list bullet symbols, rather than the new ones')
    textoptions.add_argument('--legacy-date-format', default=False, action='store_true',
                           help='use the legacy date format, rather than the new one')
    textoptions.add_argument('--no-legacy-date-format', dest='legacy_date_format', action='store_false',
                           help="don't use the legacy date format")
    textoptions.add_argument('--list-symbols', metavar='4*CHAR',
                           help='use the characters given as list bullet symbols')
    textoptions.add_argument('--bom', '--BOM', action='store_true', default=False,
                           help='Add a BOM (unicode byte order mark) to the start of text files')
    textoptions.add_argument('--paginate', '--pagination', dest='pagination', action='store_true', default=None,
                            help='do pagination')
    textoptions.add_argument('-P', '--no-pagination', dest='pagination', action='store_false', default=None,
                            help='don\'t do pagination of v3 draft text format')
    textoptions.add_argument('--table-hyphen-breaks', action='store_true', default=False,
                            help='More easily do line breaks after hyphens in table cells to give a more compact table')
    textoptions.add_argument('--table-borders', default='full', choices=['full', 'light', 'minimal', 'min', ],
                            help='The style of table borders to use for text output; one of full/light/minimal')
    textoptions.add_argument('--rfc-html-archive-url', default="https://www.rfc-editor.org/rfc/",
                           help='URL for HTML file archive of RFCs')
    textoptions.add_argument('--id-html-archive-url', default="https://www.ietf.org/archive/id/",
                           help='URL for HTML file archive Internet-Drafts')

    htmloptions = optionparser.add_argument_group('Html Format Options')
    htmloptions.add_argument('--css', default=None, metavar="FILE",
                           help='Use the given CSS file instead of the builtin')
    htmloptions.add_argument('--external-css', action='store_true', default=False,
                           help='place css in external files')
    htmloptions.add_argument('--no-external-css', dest='external_css', action='store_false',
                           help='place css in external files')
    htmloptions.add_argument('--external-js', action='store_true', default=False,
                           help='place js in external files')
    htmloptions.add_argument('--no-external-js', dest='external_js', action='store_false',
                           help='place js in external files')
    htmloptions.add_argument('--rfc-base-url', default="https://www.rfc-editor.org/rfc/",
                           help='Base URL for RFC links')
    htmloptions.add_argument('--id-base-url', default="https://datatracker.ietf.org/doc/html/",
                           help='Base URL for Internet-Draft links')
    htmloptions.add_argument('--rfc-reference-base-url', default="https://rfc-editor.org/rfc/",
                           help='Base URL for RFC reference targets, replacing the target="..." value given in the reference entry')
    htmloptions.add_argument('--id-reference-base-url', default="https://datatracker.ietf.org/doc/html/",
                           help='Base URL for I-D reference targets')
    htmloptions.add_argument('--metadata-js-url', default="metadata.min.js",
                           help='URL for the metadata script')
    htmloptions.add_argument('--inline-version-info', action='store_true', default=True,
                           help=configargparse.SUPPRESS),
    htmloptions.add_argument('--no-inline-version-info', action='store_false', dest="inline_version_info",
                           help=configargparse.SUPPRESS),
    htmloptions.add_argument('--no-rfc-local', action='store_false', dest='rfc_local', default=True,
                             help='Do not link to rfc-local.css')

    v2v3options = optionparser.add_argument_group('V2-V3 Converter Options')
    v2v3options.add_argument('--add-xinclude', action='store_true',
                           help='replace reference elements with RFC and Internet-Draft'
                           ' seriesInfo with the appropriate XInclude element')
    v2v3options.add_argument('--draft-revisions', '--draft-revs', action='store_true', default=False, dest='draft_revisions',
                           help="Reference explicit draft revisions when inserting XIncludes for draft references")
    v2v3options.add_argument('--strict', action='store_true',
                           help='be strict about stripping some deprecated attributes')

    preptooloptions = optionparser.add_argument_group('Preptool Options')
    preptooloptions.add_argument('--accept-prepped', action='store_true',
                           help='accept already prepped input')


    # --- Parse arguments ---------------------------------

    from xml2rfc.writers.base import default_options    


    options = optionparser.parse_args()
    # This is a bit wasteful, but we need to parse options first,
    # in order to know if we should ignore config files
    if options.skip_config_files:
        options = optionparser.parse_args(config_file_contents='')
    args = [ options.source ]
    # Some additional values not exposed as options
    options.doi_base_url = "https://doi.org/"
    options.no_css = False

    # --- Set default values ---------------------------------

    # Check that the default_options have values for all options, for people
    # calling xml2rfc library functions, rather than the command-line
    for key in options.__dict__:
        if not key in default_options.__dict__:
            sys.stderr.write("  Option missing from base.default_options: %s\n" % key)
            sys.exit(2)
    for key in default_options.__dict__:
        if not key in options.__dict__:
            setattr(options, key, getattr(default_options, key))

    # --- Help options ---------------------------------        

    if options.country_help:
        print_country_help(options, optionparser)
        sys.exit()

    if options.pdf_help:
        print_pdf_help(options, optionparser)
        sys.exit()

    if options.pi_help:
        print_pi_help(options, optionparser)
        sys.exit()

    # Show option values
    if options.values:
        print_values(options, optionparser, config_paths)
        sys.exit()

    # Show version information, then exit
    if options.version:
        print_version(options, optionparser)
        sys.exit()

    # --- Parse and validate arguments ---------------------------------
    # template_dir
    options.template_dir = options.template_dir or default_options.template_dir

    if (options.docfile or options.manpage) and not options.list_symbols:
        options.list_symbols = default_options.list_symbols

    if not options.silence:
        options.silence = default_options.silence

    if options.docfile:
        filename = options.output_filename
        if not filename:
            filename = 'xml2rfc-doc-%s.xml' % xml2rfc.__version__
            options.output_filename = filename
        writer = xml2rfc.DocWriter(None, options=options, date=options.date)
        writer.write(filename)
        sys.exit()

    if options.manpage:
        writer = xml2rfc.DocWriter(None, options=options, date=options.date)
        writer.manpage()
        sys.exit()

    # Clear cache and exit if requested
    if options.clear_cache:
        xml2rfc.parser.XmlRfcParser('').delete_cache(path=options.cache)
        sys.exit(0)

    if len(args) < 1:
        optionparser.print_help()
        sys.exit(2)

    if options.pdf:
        header = """    Cannot generate PDF due to missing external libraries.
    ------------------------------------------------------
    """
        missing_libs = get_missing_pdf_libs()
        if missing_libs:
            pdf_requirements_info = get_pdf_help(missing_libs)
            sys.exit(header+pdf_requirements_info)

    source = args[0]
    if not source:
        sys.exit('No source file given')
    if not os.path.exists(source):
        sys.exit('No such file: ' + source)
    
    options.legacy = not options.v3
    # Default (this may change over time):
    options.vocabulary = 'v2' if options.legacy else 'v3'
    # Option constraints
    if sys.argv[0].endswith('v2v3'):
        options.v2v3 = True
        options.utf8 = True
    #
    if options.preptool:
        options.vocabulary = 'v3'
        options.no_dtd = True
    else:
        if options.accept_prepped:
            sys.exit("You can only use --accept-prepped together with --preptool.")            
    if options.v2v3:
        options.vocabulary = 'v2'
        options.no_dtd = True
    #
    if options.basename:
        if options.output_path:
            sys.exit('--path and --basename has the same functionality, please use only --path')
        else:
            options.output_path = options.basename
            options.basename = None
    #
    num_formats = len([ o for o in [options.raw, options.text, options.nroff, options.html, options.expand, options.use_bib, options.v2v3, options.preptool, options.info, options.pdf, options.unprep ] if o])
    if num_formats > 1 and (options.filename or options.output_filename):
        sys.exit('Cannot use an explicit output filename when generating more than one format, '
                 'use --path instead.')
    if num_formats < 1:
        # Default to paginated text output
        options.text = True
    if options.debug:
        options.verbose = True
    #
    if options.cache:
        if not os.path.exists(options.cache):
            try:
                os.makedirs(options.cache)
                xml2rfc.log.note('Created cache directory at', options.cache)
            except OSError as e:
                print('Unable to make cache directory: %s ' % options.cache)
                print(e)
                sys.exit(1)
        else:
            if not os.access(options.cache, os.W_OK):
                print('Cache directory is not writable: %s' % options.cache)
                sys.exit(1)
    #
    if options.datestring is not None:
        options.date = datetime.datetime.strptime(options.datestring, "%Y-%m-%d").date()
    else:
        # Use today by default. Even though date = None is later translated to today(), set it
        # explicitly to ensure there's no date skew between instance inits if we happen to be run
        # exactly at midnight.
        options.date = datetime.date.today()

    if options.omit_headers and not options.text:
        sys.exit("You can only use --no-headers with paginated text output.")
    #
    if options.utf8:
        xml2rfc.log.warn("The --utf8 switch is deprecated.  Use the new unicode insertion element <u> to refer to unicode values in a protocol specification.")

    if options.rfc_reference_base_url:
        if not options.rfc_reference_base_url.endswith('/'):
            options.rfc_reference_base_url += '/'
    if options.id_reference_base_url:
        if not options.id_reference_base_url.endswith('/'):
            options.id_reference_base_url += '/'

    # ------------------------------------------------------------------

    # Setup warnings module
    # xml2rfc.log.warn_error = options.warn_error and True or False
    xml2rfc.log.quiet = options.quiet and True or False
    xml2rfc.log.verbose = options.verbose

    # Parse the document into an xmlrfc tree instance
    parser = xml2rfc.XmlRfcParser(source,
                                  options=options,
                                  templates_path=options.template_dir,
                              )
    try:
        xmlrfc = parser.parse(remove_pis=options.remove_pis, normalize=True)
    except xml2rfc.parser.XmlRfcError as e:
        xml2rfc.log.exception('Unable to parse the XML document: ' + args[0], e)
        sys.exit(1)
    except lxml.etree.XMLSyntaxError as e:
        # Give the lxml.etree.XmlSyntaxError exception a line attribute which
        # matches lxml.etree._LogEntry, so we can use the same logging function
        xml2rfc.log.exception('Unable to parse the XML document: ' + args[0], e.error_log)
        sys.exit(1)
    # check doctype
    if xmlrfc.tree.docinfo and xmlrfc.tree.docinfo.system_url:
        version = xmlrfc.tree.getroot().get('version', '2')
        if version == '3' and xmlrfc.tree.docinfo.system_url.lower() == 'rfc2629.dtd':
            sys.exit('Incompatible schema information: found "rfc2629.dtd" in <DOCTYPE> of a version 3 file')

    # Remember if we're building an RFC
    options.rfc = xmlrfc.tree.getroot().get('number')

    # Use the right pagination default, depending on RFC or not
    if options.pagination == None:
        options.pagination = False if options.rfc else True

    # Check if we've received a version="3" document, and adjust accordingly
    if xmlrfc.tree.getroot().get('version') == '3':
        options.legacy = False
        options.no_dtd = True
        options.vocabulary = 'v3'

    # ------------------------------------------------------------------
    # Additional option checks that depend on the option.legacy setting which
    # we may have adjusted as a result of the <rfc version="..."> setting:
    if options.text and not options.legacy:
        if options.legacy_list_symbols and options.list_symbols:
            sys.exit("You cannot specify both --list-symbols and --legacy_list_symbols.")
        if options.list_symbols:
            options.list_symbols = tuple(list(options.list_symbols))
        elif options.legacy_list_symbols:
            options.list_symbols = ('o', '*', '+', '-')
        else:
            options.list_symbols = ('*', '-', 'o', '+')
    else:
        if options.legacy_list_symbols:
            sys.exit("You can only use --legacy-list-symbols with v3 text output.")
        if options.list_symbols:
            sys.exit("You can only use --list-symbols with v3 text output.")

    if not options.legacy:
        # I.e., V3 formatter
        options.no_dtd = True        
        if options.nroff:
            sys.exit("You can only use --nroff in legacy mode")
        if options.raw:
            sys.exit("You can only use --raw in legacy mode")

    # ------------------------------------------------------------------
    # Validate the document unless disabled
    if not options.no_dtd:
        ok, errors = xmlrfc.validate(dtd_path=options.dtd)
        if not ok:
            xml2rfc.log.exception('Unable to validate the XML document: ' + args[0], errors)
            sys.exit(1)

    if options.filename:
        xml2rfc.log.warn("The -f and --filename options are deprecated and will"
                        " go away in version 3.0 of xml2rfc.  Use -o instead")
        if options.output_filename and options.filename != options.output_filename:
            xml2rfc.log.warn("You should not specify conflicting -f and -o options.  Using -o %s"
                        % options.output_filename)
        if not options.output_filename:
            options.output_filename = options.filename

    # Execute any writers specified
    try:
        source_path, source_base = os.path.split(source)
        source_name, source_ext  = os.path.splitext(source_base)
        if options.output_path:
            if os.path.isdir(options.output_path):
                basename = os.path.join(options.output_path, source_name)
            else:
                sys.exit("The given output path '%s' is not a directory, cannot place output files there" % (options.output_path, ))
        else:
            # Create basename based on input
            basename = os.path.join(source_path, source_name)

        if options.expand and options.legacy:
            # Expanded XML writer needs a separate tree instance with
            # all comments and PI's preserved.  We can assume there are no
            # parse errors at this point since we didnt call sys.exit() during
            # parsing.
            filename = options.output_filename
            if not filename:
                filename = basename + '.exp.xml'
                options.output_filename = filename
            new_xmlrfc = parser.parse(remove_comments=False, quiet=True, normalize=False)
            expwriter = xml2rfc.ExpandedXmlWriter(new_xmlrfc,
                                                  options=options,
                                                  date=options.date)
            expwriter.write(filename)
            options.output_filename = None

        if options.html and options.legacy:
            filename = options.output_filename
            if not filename:
                filename = basename + '.html'
                options.output_filename = filename
            htmlwriter = xml2rfc.HtmlRfcWriter(xmlrfc,
                                               options=options,
                                               date=options.date,
                                               templates_dir=options.template_dir or None)
            htmlwriter.write(filename)
            options.output_filename = None

        if options.raw:
            filename = options.output_filename
            if not filename:
                filename = basename + '.raw.txt'
                options.output_filename = filename
            rawwriter = xml2rfc.RawTextRfcWriter(xmlrfc,
                                                 options=options,
                                                 date=options.date)
            rawwriter.write(filename)
            options.output_filename = None

        if options.text and options.legacy:
            filename = options.output_filename
            if not filename:
                filename = basename + '.txt'
                options.output_filename = filename
            pagedwriter = xml2rfc.PaginatedTextRfcWriter(xmlrfc,
                                                         options=options,
                                                         date=options.date,
                                                         omit_headers=options.omit_headers,
                                                     )
            pagedwriter.write(filename)
            options.output_filename = None

        if options.nroff:
            filename = options.output_filename
            if not filename:
                filename = basename + '.nroff'
                options.output_filename = filename
            nroffwriter = xml2rfc.NroffRfcWriter(xmlrfc,
                                                 options=options,
                                                 date=options.date)
            nroffwriter.write(filename)
            options.output_filename = None

        # --- End of legacy formatter invocations ---
        if options.use_bib:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, normalize=False, strip_cdata=False, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.bib.xml'
                options.output_filename = filename
            expander = xml2rfc.DatatrackerToBibConverter(xmlrfc, options=options, date=options.date)
            expander.write(filename)
            options.output_filename = None

        if options.expand and not options.legacy:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, normalize=False, strip_cdata=False, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.exp.xml'
                options.output_filename = filename
            #v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
            #xmlrfc.tree = v2v3.convert2to3()
            expander = xml2rfc.ExpandV3XmlWriter(xmlrfc, options=options, date=options.date)
            expander.write(filename)
            options.output_filename = None

        if options.v2v3:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, normalize=False, strip_cdata=False, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.v2v3.xml'
                options.output_filename = filename
            v2v3writer = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
            v2v3writer.write(filename)
            options.output_filename = None

        if options.preptool:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.prepped.xml'
                options.output_filename = filename
            v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
            xmlrfc.tree = v2v3.convert2to3()
            preptool = xml2rfc.PrepToolWriter(xmlrfc, options=options, date=options.date)
            preptool.write(filename)
            options.output_filename = None

        if options.unprep:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename.replace('.prepped','') + '.plain.xml'
                options.output_filename = filename
            unprep = xml2rfc.UnPrepWriter(xmlrfc, options=options, date=options.date)
            unprep.write(filename)
            options.output_filename = None

        if options.text and not options.legacy:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.txt'
                options.output_filename = filename
            if not xmlrfc.tree.getroot().get('prepTime'):
                v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
                xmlrfc.tree = v2v3.convert2to3()
                prep = xml2rfc.PrepToolWriter(xmlrfc, options=options, date=options.date, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
                xmlrfc.tree = prep.prep()
            if xmlrfc.tree:
                writer = xml2rfc.TextWriter(xmlrfc, options=options, date=options.date)
                writer.write(filename)
                options.output_filename = None

        if options.html and not options.legacy:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.html'
                options.output_filename = filename
            if not xmlrfc.tree.getroot().get('prepTime'):
                v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
                xmlrfc.tree = v2v3.convert2to3()
                prep = xml2rfc.PrepToolWriter(xmlrfc, options=options, date=options.date, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
                xmlrfc.tree = prep.prep()
            if xmlrfc.tree:
                writer = xml2rfc.HtmlWriter(xmlrfc, options=options, date=options.date)
                writer.write(filename)
                options.output_filename = None

        if options.pdf:
            xmlrfc = parser.parse(remove_comments=False, quiet=True, add_xmlns=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.pdf'
                options.output_filename = filename
            if not xmlrfc.tree.getroot().get('prepTime'):
                v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
                xmlrfc.tree = v2v3.convert2to3()
                prep = xml2rfc.PrepToolWriter(xmlrfc, options=options, date=options.date, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
                xmlrfc.tree = prep.prep()
            if xmlrfc.tree:
                writer = xml2rfc.PdfWriter(xmlrfc, options=options, date=options.date)
                writer.write(filename)
                options.output_filename = None

        if options.info:
            xmlrfc = parser.parse(remove_comments=False, quiet=True)
            filename = options.output_filename
            if not filename:
                filename = basename + '.json'
                options.output_filename = filename
            v2v3 = xml2rfc.V2v3XmlWriter(xmlrfc, options=options, date=options.date)
            xmlrfc.tree = v2v3.convert2to3()
            prep = xml2rfc.PrepToolWriter(xmlrfc, options=options, date=options.date, liberal=True, keep_pis=[xml2rfc.V3_PI_TARGET])
            xmlrfc.tree = prep.prep()
            if xmlrfc.tree:
                info = extract_anchor_info(xmlrfc.tree)
                with io.open(filename, 'w', encoding='utf-8') as fp:
                    json.dump(info, fp, indent=2, ensure_ascii=False)
                if not options.quiet:
                    xml2rfc.log.write('Created file', filename)


    except xml2rfc.RfcWriterError as e:
        xml2rfc.log.write(e.msg)
        xml2rfc.log.write('Unable to complete processing %s' % args[0])
        sys.exit(1)

if __name__ == '__main__':

    major, minor = sys.version_info[:2]
    if not (major == 2 and minor >= 6) and not major == 3:
        print ("")
        print ("The xml2rfc script requires python 2, with a version of 2.6 or higher, or python 3.")
        print ("Can't proceed, quitting.")
        exit()

    main()
