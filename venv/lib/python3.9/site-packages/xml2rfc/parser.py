# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

""" Public XML parser module """

import base64
import hashlib
import io
import lxml.etree
import os
import re
import requests
import shutil
import time
import xml2rfc.log
import xml2rfc.utils

from xml2rfc.writers import base
from xml2rfc.util.file import can_access, FileAccessError

try:
    from urllib.parse import urlparse, urljoin, urlsplit
except ImportError:
    from urlparse import urlparse, urljoin, urlsplit

try:
    from xml2rfc import debug
    assert debug
except ImportError:
    pass

__all__ = ['XmlRfcParser', 'XmlRfc', 'XmlRfcError']

class XmlRfcError(Exception):
    """ Application XML errors with positional information
    
        This class attempts to mirror the API of lxml's error class
    """
    def __init__(self, msg, filename=None, line_no=0):
        self.msg = msg
        # This mirrors lxml error behavior, but we can't capture column
        self.position = (line_no, 0)
        # Also match lxml.etree._LogEntry attributes:
        self.message = msg
        self.filename = filename
        self.line = line_no

    def __str__(self):
        return self.msg

class CachingResolver(lxml.etree.Resolver):
    """ Custom ENTITY request handler that uses a local cache """
    def __init__(self, cache_path=None, library_dirs=None, source=None,
                 templates_path=base.default_options.template_dir, verbose=None, quiet=None,
                 no_network=None, network_locs= [
                     'https://bib.ietf.org/public/rfc/',
                 ],
                 rfc_number=None, options=base.default_options):
        self.quiet = quiet if quiet != None else options.quiet
        self.verbose = verbose if verbose != None else options.verbose
        self.no_network = no_network if no_network != None else options.no_network
        self.cache_path = cache_path or options.cache
        self.source = source 
        self.library_dirs = library_dirs
        self.templates_path = templates_path
        self.network_locs = network_locs
        self.include = False
        self.rfc_number = rfc_number
        self.cache_refresh_secs = (60*60*24*14) # 14 days
        self.options = options

        # Get directory of source
        if self.source:
            if isinstance(self.source, str):
                self.source_dir = os.path.abspath(os.path.dirname(self.source))
            else:
                self.source_dir = os.path.abspath(os.path.dirname(self.source.name))                
        else:
            self.source_dir = None

        # Determine cache directories to read/write to
        self.read_caches = [ os.path.expanduser(path) for path in xml2rfc.CACHES ]
        self.write_cache = None
        if self.cache_path:
            # Explicit directory given, set as first directory in read_caches
            self.read_caches.insert(0, self.cache_path)
        # Try to find a valid directory to write to by stepping through
        # Read caches one by one
        for dir in self.read_caches:
            if os.path.exists(dir) and os.access(dir, os.W_OK):
                self.write_cache = dir
                break
            else:
                try:
                    os.makedirs(dir)
                    xml2rfc.log.note('Created cache directory at', dir)
                    self.write_cache = dir
                except OSError:
                    # Can't write to this directory, try the next one
                    pass
        if not self.write_cache:
            xml2rfc.log.warn('Unable to find a suitable cache directory to '
                            'write to, trying the following directories:\n ',
                            '\n  '.join(self.read_caches),
                            '\nTry giving a specific directory with --cache.')
        else:
            # Create the prefix directory if it doesnt exist
            pdir = os.path.join(self.write_cache, xml2rfc.CACHE_PREFIX)
            if not os.path.exists(pdir):
                os.makedirs(pdir)
                
        self.sessions = {}

    def delete_cache(self, path=None):
        # Explicit path given?
        caches = path and [path] or self.read_caches
        for dir in caches:
            path = os.path.join(dir, xml2rfc.CACHE_PREFIX)
            if os.access(path, os.W_OK):
                shutil.rmtree(path)
                xml2rfc.log.note('Deleted cache directory at', path)

                
    def resolve(self, request, public_id, context):
        """ Called internally by lxml """
        if not request:
            # Not sure why but sometimes LXML will ask for an empty request,
            # So lets give it an empty response.
            return None
        # If the source itself is requested, return as-is
        if request == self.source:
            return self.resolve_filename(request, context)
        if request == u"internal:/rfc.number":
            if self.rfc_number:
                return self.resolve_string(self.rfc_number, context)
            return self.resolve_string("XXXX", context)
        # Warn if .ent file is referred.
        if request.endswith('.ent'):
            xml2rfc.log.warn('{} is no longer needed as the special processing of non-ASCII characters has been superseded by direct support for non-ASCII characters in RFCXML.'.format(request))
        url = urlparse(request)
        if not url.netloc or url.scheme == 'file':
            if request.startswith("file://"):
                request = request[7:]
            try:
                can_access(self.options,
                           self.source,
                           self.getReferenceRequest(request),
                           access_templates=True)
            except FileAccessError as error:
                raise XmlRfcError(str(error))
        try:
            path = self.getReferenceRequest(request)
            return self.resolve_filename(path, context)
        except Exception as e:
            xml2rfc.log.error(str(e))
            return None

    
    def getReferenceRequest(self, request, include=False, line_no=0):
        """ Returns the correct and most efficient path for an external request

            To determine the path, the following algorithm is consulted:

            If REQUEST ends with '.dtd' or '.ent' then
              If REQUEST is an absolute path (local or network) then
                Return REQUEST
              Else
                Try TEMPLATE_DIR + REQUEST, otherwise
                Return SOURCE_DIR + REQUEST
            Else
              If REQUEST doesn't end with '.xml' then
                append '.xml'
              If REQUEST is an absolute path (local or network) then
                Return REQUEST
              Else
                If REQUEST contains intermediate directories then
                  Try each directory in LOCAL_LIB_DIRS + REQUEST, otherwise
                  Try NETWORK + REQUEST
                Else (REQUEST is simply a filename)
                  [Recursively] Try each directory in LOCAL_LIB_DIRS + REQUEST, otherwise
                  Try each explicit (bibxml, bibxml2...) subdirectory in NETWORK + REQUEST

            Finally if the path returned is a network URL, use the cached
            version or create a new cache.
           
            - REQUEST refers to the full string of the file asked for,
            - TEMPLATE_DIR refers to the applications 'templates' directory,
            - SOURCE_DIR refers to the directory of the XML file being parsed
            - LOCAL_LIB_DIRS refers to a list of local directories to consult,
              on the CLI this is set by $XML_LIBRARY, defaulting to 
              ['/usr/share/xml2rfc'].  On the GUI this can be configured
              manually but has the same initial defaults.
            - NETWORK refers to the online citation library.

            The caches in read_dirs are consulted in sequence order to find the
            request.  If not found, the request will be cached at write_dir.

            This method will throw an lxml.etree.XMLSyntaxError to be handled
            by the application if the reference or referencegroup cannot be
            properly resolved
        """
        self.include = include # include state
        tried_cache = False
        attempts = []  # Store the attempts
        original = request  # Used for the error message only
        result = None  # Our proper path
        if request.endswith('.dtd') or request.endswith('.ent'):
            if os.path.isabs(request) and os.path.exists(request):
                # Absolute request, return as-is if it exists
                attempts.append(request)
                result = request
            elif urlparse(request).netloc:
                # Network request, return as-is
                attempts.append(request)
                result = request
            else:
                basename = os.path.basename(request)
                # Look for dtd in templates directory
                attempt = os.path.join(self.templates_path, basename)
                attempts.append(attempt)
                if os.path.exists(attempt):
                    result = attempt
                else:
                    # Default to source directory
                    result = os.path.join(self.source_dir, basename)
                    attempts.append(result)
        else:
            if not request.endswith('.xml'):
                paths = [ request + '.xml', request ]
            else:
                paths = [ request ]
            if os.path.isabs(paths[0]):
                # Absolute path, return as-is
                for path in paths:
                    attempts.append(path)
                    result = path
                    if os.path.exists(path):
                        break
            elif urlparse(paths[0]).netloc:
                # URL requested, cache it
                origloc = urlparse(paths[0]).netloc
                if True in [ urlparse(loc).netloc == urlparse(paths[0]).netloc for loc in self.network_locs ]:
                    for loc in self.network_locs:
                        newloc = urlparse(loc).netloc
                        for path in paths:
                            path = path.replace(origloc, newloc)
                            attempts.append(path)
                            result = self.cache(path)
                            if result:
                                break
                        if result:
                            break
                else:
                    for path in paths:
                        attempts.append(path)
                        result = self.cache(path)
                        if result:
                            break
                if not result:
                    if self.options.vocabulary == 'v3' and not request.endswith('.xml'):
                        xml2rfc.log.warn("The v3 formatters require full explicit URLs of external resources.  Did you forget to add '.xml' (or some other extension)?")
                    if self.no_network:
                        xml2rfc.log.warn("Document not found in cache, and --no-network specified -- couldn't resolve %s" % request)
                tried_cache = True
            else:
                if os.path.dirname(paths[0]):
                    # Intermediate directories, only do flat searches
                    for dir in self.library_dirs:
                        # Try local library directories
                        for path in paths:
                            attempt = os.path.join(dir, path)
                            attempts.append(attempt)
                            if os.path.exists(attempt):
                                result = attempt
                                break
                    if not result:
                        # Try network location
                        for loc in self.network_locs:
                            for path in paths:
                                url = urljoin(loc, path)
                                attempts.append(url)
                                result = self.cache(url)
                                if result:
                                    break
                            if result:
                                break
                        tried_cache = True
                        if not result and self.no_network:
                            xml2rfc.log.warn("Document not found in cache, and --no-network specified -- couldn't resolve %s" % request)

                        # if not result:
                        #     # Document didn't exist, default to source dir
                        #     result = os.path.join(self.source_dir, request)
                        #     attempts.append(result)
                else:
                    for dir in self.library_dirs:
                        # NOTE: Recursion can be implemented here
                        # Try local library directories
                        for path in paths:
                            attempt = os.path.join(dir, path)
                            attempts.append(attempt)
                            if os.path.exists(attempt):
                                result = attempt
                                break
                    if not result:
                        # Try network subdirs
                        for subdir in xml2rfc.NET_SUBDIRS:
                            for loc in self.network_locs:
                                for path in paths:
                                    url = urljoin(loc, subdir + '/' + path)
                                    attempts.append(url)
                                    result = self.cache(url)
                                    if result:
                                        break
                                if result:
                                    break
                            tried_cache = True
                            if result:
                                break
                        if not result and self.no_network:
                            xml2rfc.log.warn("Document not found in cache, and --no-network specified -- couldn't resolve %s" % request)
                    # if not result:
                    #     # Default to source dir
                    #     result = os.path.join(self.source_dir, request)
                    #     attempts.append(result)

        # Verify the result -- either raise exception or return it
        if not result or (not os.path.exists(result) and not urlparse(original).netloc):
            if os.path.isabs(original):
                xml2rfc.log.warn('A reference was requested with an absolute path: "%s", but not found '
                    'in that location.  Removing the path component will cause xml2rfc to look for '
                    'the file automatically in standard locations.' % original)
            # Couldn't resolve.  Throw an exception
            error = XmlRfcError('Unable to resolve external request: '
                                      + '"' + original + '"', line_no=line_no, filename=self.source)
            if self.verbose and len(attempts) > 1:
                # Reveal attemps
                error.msg += ', trying the following location(s):\n    ' + \
                             '\n    '.join(attempts)
            raise error
        else:
            if not tried_cache:
                # Haven't printed a verbose message yet
                typename = self.include and 'include' or 'entity'
                xml2rfc.log.note('Resolving ' + typename + '...', result)
            return result

    def cache(self, url):
        """ Return the path to a cached URL

            Checks for the existence of the cache and creates it if necessary.
        """
        scheme, netloc, path, query, fragment = urlsplit(url)
        root, ext = os.path.splitext(path)
        hash = '-'+base64.urlsafe_b64encode(hashlib.sha1(query.encode()).digest()).decode() if query else ''
        basename = os.path.basename(root+hash+ext)
        typename = self.include and 'include' or 'entity'
        # Try to load the URL from each cache in `read_cache`
        for dir in self.read_caches:
            cached_path = os.path.join(dir, xml2rfc.CACHE_PREFIX, basename)
            if os.path.exists(cached_path):
                if os.path.getmtime(cached_path) < (time.time() - self.cache_refresh_secs) and not self.no_network:
                    xml2rfc.log.note('Cached version at %s too old; will refresh cache for %s %s' % (cached_path, typename, url))
                    break
                else:
                    xml2rfc.log.note('Resolving ' + typename + '...', url)
                    xml2rfc.log.note('Loaded from cache', cached_path)
                    xml = lxml.etree.parse(cached_path)
                    if xml.getroot().tag == 'reference':
                        if self.validate_ref(xml):
                            return cached_path
                        else:
                            xml2rfc.log.error('Failure validating reference xml from %s' % cached_path )
                            os.path.unlink(cached_path)
                            return url
                    elif xml.getroot().tag == 'referencegroup':
                        if self.validate_ref_group(xml):
                            return cached_path
                        else:
                            xml2rfc.log.error('Failure validating referencegroup xml from %s' % cached_path )
                            os.path.unlink(cached_path)
                    else:
                        return cached_path

        xml2rfc.log.note('Resolving ' + typename + '...', url)
        if not netloc in self.sessions:
            self.sessions[netloc] = requests.Session()
        session = self.sessions[netloc]
        exc = None
        for i in range(4):
            try:
                r = session.get(url)
                break
            except requests.exceptions.ConnectionError as e:
                exc = e
                xml2rfc.log.note('  retrying %s (%s)' % (url, e.args[0].args[0]))
        else:
            xml2rfc.log.error('Failure fetching URL %s (%s)' % (url, exc.args[0].args[0]))
            return ''
        for rr in r.history + [r, ]:
            xml2rfc.log.note(' ... %s %s' % (rr.status_code, rr.url))
        if r.status_code == 200:
            if self.write_cache:
                try:
                    xml = lxml.etree.fromstring(r.text.encode('utf8'))
                    if xml.tag == 'reference':
                        if self.validate_ref(xml):
                            return self.add_to_cache(r.url, xml, basename)
                        else:
                            xml2rfc.log.error('Failure validating reference xml from %s' % url )
                            return url
                    elif xml.tag == 'referencegroup':
                        if self.validate_ref_group(xml):
                            return self.add_to_cache(r.url, xml, basename)
                        else:
                            xml2rfc.log.error('Failure validating referencegroup xml from %s' % url )
                            return url
                    else:
                        return url
                except Exception as e:
                    xml2rfc.log.error(str(e))
                    return url
            else:
                return url
        else:
            # Invalid URL -- Error will be displayed in getReferenceRequest
            xml2rfc.log.note("URL retrieval failed with status code %s for '%s'" % (r.status_code, r.url))
            return ''

    def validate_ref(self, xml):
        ref_rng_file = os.path.join(os.path.dirname(__file__), 'data', 'reference.rng')
        ref_rng = lxml.etree.RelaxNG(file=ref_rng_file)
        return ref_rng.validate(xml)

    def validate_ref_group(self, xml):
        ref_rng_file = os.path.join(os.path.dirname(__file__), 'data', 'referencegroup.rng')
        ref_rng = lxml.etree.RelaxNG(file=ref_rng_file)
        return ref_rng.validate(xml)

    def add_to_cache(self, url, xml, basename):
        xml.set('{%s}base'%xml2rfc.utils.namespaces['xml'], url)
        text = lxml.etree.tostring(xml, encoding='utf-8')
        write_path = os.path.join(self.write_cache,
                                  xml2rfc.CACHE_PREFIX, basename)
        with io.open(write_path, 'w', encoding='utf-8') as cache_file:
            cache_file.write(text.decode('utf-8'))
        xml2rfc.log.note('Added file to cache: ', write_path)
        return write_path

class AnnotatedElement(lxml.etree.ElementBase):
    pis = None
    page = None
    outdent = 0
    def get(self, key, default=None):
        value = super(AnnotatedElement, self).get(key, default)
        if value == default:
            return value
        else:
            return str(value)

class XmlRfcParser:

    nsmap = {
        b'xi':   b'http://www.w3.org/2001/XInclude',
    }


    """ XML parser container with callbacks to construct an RFC tree """
    def __init__(self, source, verbose=None, quiet=None, options=base.default_options,
                 cache_path=None, templates_path=base.default_options.template_dir, library_dirs=None, add_xmlns=False,
                 no_network=None, network_locs=[
                     'https://bib.ietf.org/public/rfc/',
                 ]
                 ):
        self.options = options
        self.quiet = quiet if quiet != None else options.quiet
        self.verbose = verbose if verbose != None else options.verbose
        self.no_network = no_network if no_network != None else options.no_network
        self.source = source
        self.cache_path = cache_path or options.cache
        self.network_locs = network_locs

        if self.source:
            with io.open(self.source, "rb", newline=None) as f:
                self.text = f.read()

        # Initialize templates directory
        self.templates_path = templates_path

        if options and options.vocabulary == 'v2':
            self.default_dtd_path = os.path.join(self.templates_path, 'rfc2629.dtd')
        else:
            self.default_dtd_path = None

        for prefix, value in self.nsmap.items():
            lxml.etree.register_namespace(prefix, value)

        # If library dirs werent explicitly set, like from the gui, then try:
        #   1. $XML_LIBRARY environment variable as a delimited list
        #   2. Default to /usr/share/xml2rfc
        # Split on colon or semi-colon delimiters
        if not library_dirs:
            library_dirs = os.environ.get('XML_LIBRARY', '/usr/share/xml2rfc')
        self.library_dirs = []
        srcdir = os.path.abspath(os.path.dirname(self.source)) if source else ''
        for raw_dir in re.split(':|;', library_dirs) + [ srcdir ]:
            # Convert empty directory to source dir
            if raw_dir == '': 
                raw_dir = srcdir
            else:
                raw_dir = os.path.normpath(os.path.expanduser(raw_dir))
            # Add dir if its unique
            if raw_dir not in self.library_dirs:
                self.library_dirs.append(raw_dir)

        # Initialize the caching system.  We'll replace this later if parsing.
        self.cachingResolver = CachingResolver(cache_path=self.cache_path,
                                        library_dirs=self.library_dirs,
                                        templates_path=self.templates_path,
                                        source=self.source,
                                        network_locs=self.network_locs,
                                        verbose=self.verbose,
                                        quiet=self.quiet,
                                        options=options,
                                    )

    def delete_cache(self, path=None):
        self.cachingResolver.delete_cache(path=path)

    def parse(self, remove_comments=True, remove_pis=False, quiet=False, strip_cdata=True, normalize=False, add_xmlns=False):
        """ Parses the source XML file and returns an XmlRfc instance """
        xml2rfc.log.note('Parsing file', self.source)

        # workaround for not being able to explicitly set namespaces on the
        # xml root element in lxml: Insert it before we parse:
        text = self.text
        if add_xmlns and not self.nsmap[b'xi'] in text:
            if re.search(b"""<rfc[^>]*(?P<xi>xmlns:xi=['"][^'"]+['"])""", text):
                xml2rfc.log.error('Namespace prefix "xi" is defined, but not as the XInclude namespace "%s".' % self.nsmap[b'xi'])
            else:
                text = text.replace(b'<rfc ', b'<rfc xmlns:%s="%s" ' % (b'xi', self.nsmap[b'xi']), 1)

        # Get an iterating parser object
        with io.BytesIO(text) as file:
            file.name = self.source
            context = lxml.etree.iterparse(file,
                                          dtd_validation=False,
                                          load_dtd=True,
                                          attribute_defaults=True,
                                          no_network=self.no_network,
                                          remove_comments=remove_comments,
                                          remove_pis=remove_pis,
                                          remove_blank_text=True,
                                          resolve_entities=False,
                                          strip_cdata=strip_cdata,
                                          events=("start",),
                                          tag="rfc",
                                      )
            # resolver without knowledge of rfc_number:
            caching_resolver = CachingResolver(cache_path=self.cache_path,
                                            library_dirs=self.library_dirs,
                                            templates_path=self.templates_path,
                                            source=self.source,
                                            no_network=self.no_network,
                                            network_locs=self.network_locs,
                                            verbose=self.verbose,
                                            quiet=self.quiet,
                                            options=self.options,
                                         )
            context.resolvers.add(caching_resolver)

            # Get hold of the rfc number (if any) in the rfc element, so we can
            # later resolve the "&rfc.number;" entity.
            self.rfc_number = None
            self.format_version = None
            for action, element in context:
                if element.tag == "rfc":
                    self.rfc_number = element.attrib.get("number", None)
                    self.format_version = element.attrib.get("version", None)
                    break
        if self.format_version == "3":
            self.default_dtd_path = None

        # now get a regular parser, and parse again, this time resolving entities
        parser = lxml.etree.XMLParser(dtd_validation=False,
                                      load_dtd=True,
                                      attribute_defaults=True,
                                      no_network=self.no_network,
                                      remove_comments=remove_comments,
                                      remove_pis=remove_pis,
                                      remove_blank_text=False,
                                      resolve_entities=True,
                                      strip_cdata=strip_cdata)

        # Initialize the caching system
        self.cachingResolver = CachingResolver(cache_path=self.cache_path,
                                        library_dirs=self.library_dirs,
                                        templates_path=self.templates_path,
                                        source=self.source,
                                        no_network=self.no_network,
                                        network_locs=self.network_locs,
                                        verbose=self.verbose,
                                        quiet=self.quiet,
                                        rfc_number = self.rfc_number,
                                        options=self.options,
                                    )

        # Add our custom resolver
        parser.resolvers.add(self.cachingResolver)

        # Use our custom element class, which holds the state of PI settings
        # at this point in the xml tree
        element_lookup = lxml.etree.ElementDefaultClassLookup(element=AnnotatedElement)
        parser.set_element_class_lookup(element_lookup)

        # Parse the XML file into a tree and create an rfc instance
        with io.BytesIO(text) as file:
            file.name = self.source
            tree = lxml.etree.parse(file, parser)
        xmlrfc = XmlRfc(tree, self.default_dtd_path, nsmap=self.nsmap)
        xmlrfc.source = self.source

        # Evaluate processing instructions before root element
        xmlrfc._eval_pre_pi()
        
        # Keep seen elements in a list, to force lxml to not discard (and
        # recreate) the elements, as this would cause loss of our custom
        # state, the PI settings at the time the element was parsed
        # (in element.pis)
        xmlrfc._elements_cache = []
        # Process PIs and expand 'include' instructions
        pis = xmlrfc.pis.copy()
        for element in xmlrfc.getroot().iterdescendants():
            if element.tag is lxml.etree.PI:
                pidict = xmlrfc.parse_pi(element)
                pis = xmlrfc.pis.copy() 
                if 'include' in pidict and pidict['include']:
                    request = pidict['include']
                    if xmlrfc.getroot().get('version', '3') in ['3', ]:
                        xml2rfc.log.warn(f'XInclude should be used instead of PI include for {request}')
                    path = self.cachingResolver.getReferenceRequest(request,
                           # Pass the line number in XML for error bubbling
                           include=True, line_no=getattr(element, 'sourceline', 0))
                    try:
                        # Parse the xml and attach it to the tree here
                        parser = lxml.etree.XMLParser(load_dtd=False,
                                                      no_network=False,
                                                      remove_comments=remove_comments,
                                                      remove_pis=remove_pis,
                                                      remove_blank_text=False,
                                                      resolve_entities=True,
                                                      strip_cdata=strip_cdata)
                        parser.set_element_class_lookup(element_lookup)
                        # parser.resolvers.add(self.cachingResolver) --- should this be done?
                        ref_root = lxml.etree.parse(path, parser).getroot()
                        ref_root.pis = pis
                        xmlrfc._elements_cache.append(ref_root)
                        for e in ref_root.iterdescendants():
                            e.pis = pis
                            xmlrfc._elements_cache.append(e)
                        parent = element.getparent()
                        parent.replace(element, ref_root)
                    except (lxml.etree.XMLSyntaxError, IOError) as e:
                        if e is lxml.etree.XMLSyntaxError:
                            xml2rfc.log.warn('The include file at', path,
                                             'contained an XML error and was '\
                                             'not expanded:', e.msg)
                        else:
                            xml2rfc.log.warn('Unable to load the include file at',
                                              path)
            else:
                if isinstance(element, AnnotatedElement):
                    element.pis = pis
                    xmlrfc._elements_cache.append(element)                    

        # Finally, do any extra formatting on the RFC before returning
        if normalize:
            xmlrfc._format_whitespace()

        return xmlrfc

class XmlRfc(object):
    """ Internal representation of an RFC document

        Contains an lxml.etree.ElementTree, with some additional helper
        methods to prepare the tree for output.

        Accessing the rfc tree is done by getting the root node from getroot()
    """

    pis = {}
    source = "(unknown source)"

    def __init__(self, tree, default_dtd_path, source=None, nsmap={}):
        self.default_dtd_path = default_dtd_path
        self.tree = tree
        self.nsmap = nsmap
        if source:
            self.source = source
        # Pi default values
        self.pis = {
            "artworkdelimiter":	None,
            "artworklines":	"0",
            "authorship":	"yes",
            "autobreaks":	"yes",
            "background":	"" ,
            "colonspace":	"no" ,
            "comments":		"no" ,
            "docmapping":	"no",
            "editing":		"no",
            #"emoticonic":	"no",
            #"footer":		Unset
            "figurecount":      "no",
            #"header":		Unset
            "inline":		"no",
            #"iprnotified":	"no",
            "linkmailto":	"yes",
            #"linefile":	Unset
            "needLines":        None,
            "multiple-initials":"no",
            #"notedraftinprogress": "yes",
            "orphanlimit":      "2",
            "private":		"",
            "refparent":	"References",
            "rfcedstyle":	"no",
            #"rfcprocack":	"no",
            "sectionorphan":    "4",
            #"slides":		"no",
            "sortrefs":		"yes",
            #"strict":		"no",
            "symrefs":		"yes",
            "tablecount":       "no",
            "text-list-symbols": "o*+-",
            "toc":		"no",
            "tocappendix":	"yes",
            "tocdepth":		"3",
            "tocindent":	"yes",
            "tocnarrow":	"yes",
            #"tocompact":	"yes",
            "tocpagebreak":     "no",
            "topblock":		"yes",
            #"typeout":		Unset
            #"useobject":	"no" ,
            "widowlimit":       "2",
        }
        # Special cases:
        self.pis["compact"] = self.pis["rfcedstyle"]
        self.pis["subcompact"] = self.pis["compact"]

    def getroot(self):
        """ Wrapper method to get the root of the XML tree"""
        return self.tree.getroot()

    def getpis(self):
        """ Returns a list of the XML processing instructions """
        return self.pis.copy()
    
    def validate(self, dtd_path=None):
        """ Validate the document with its default dtd, or an optional one 
        
            Return a success bool along with a list of any errors
        """
        # Load dtd from alternate path, if it was specified
        if dtd_path:
            if os.path.exists(dtd_path):
                try:
                    dtd = lxml.etree.DTD(dtd_path)
                except lxml.etree.DTDParseError as e:
                    # The DTD itself has errors
                    xml2rfc.log.error('Could not parse the dtd file:',
                                      dtd_path + '\n  ', e.message)
                    return False, []
            else:
                # Invalid path given
                xml2rfc.log.error('DTD file does not exist:', dtd_path)
                return False, []
            
        # Otherwise, use document's DTD declaration
        else:
            dtd = self.tree.docinfo.externalDTD
            
        if not dtd and self.default_dtd_path:
            # No explicit DTD filename OR declaration in document!
            xml2rfc.log.warn('No DTD given, defaulting to', self.default_dtd_path)
            return self.validate(dtd_path=self.default_dtd_path)

        if not dtd or dtd.validate(self.getroot()):
            # The document was valid
            return True, []
        else:
            if len(dtd.error_log) == 0:
                return True, []
            else:
                # The document was not valid
                return False, dtd.error_log

    def parse_pi(self, pi):
        return xml2rfc.utils.parse_pi(pi, self.pis)

    def _eval_pre_pi(self):
        """ Evaluate pre-document processing instructions
        
            This will look at all processing instructions before the root node
            for initial document settings.
        """
        # Grab processing instructions from xml tree
        element = self.tree.getroot().getprevious()
        while element is not None:
            if element.tag is lxml.etree.PI:
                self.parse_pi(element)
            element = element.getprevious()

    def _format_whitespace(self):
        xml2rfc.utils.formatXmlWhitespace(self.getroot())
