import xml.parsers.expat

NC_NS_URI ="urn:ietf:params:xml:ns:netconf:base:1.0"
CAPABILITIES = {
    "urn:ietf:params:xml:ns:netconf:base:1.0" : "base",
    "urn:ietf:params:netconf:base:1.1" : "base",
    "urn:ietf:params:netconf:capability:writable-running:1.0" : "writable-running",
    "urn:ietf:params:netconf:capability:candidate:1.0" : "candidate",
    "urn:ietf:params:netconf:capability:startup:1.0" : "startup",
    "urn:ietf:params:netconf:capability:url:1.0" : "url",
    "urn:ietf:params:netconf:capability:xpath:1.0" : "xpath",
    "urn:ietf:params:netconf:capability:notification:1.0" : "notification",
    "urn:ietf:params:netconf:capability:with-defaults:1.0" : "with-defaults",
    }

class Capability:

    def __init__(self, uri):
        self.parameters = {}
        if "?" in uri:
            id_, pars = uri.split("?")
            self.parse_pars(pars)
        else:
            id_ = uri
        self.id = id_

    def parse_pars(self,pars):
        for p in pars.split("&"):
            name, value=p.split("=")
            self.parameters[name] = value

class HelloParser:

    def __init__(self):
        self.capabilities = []
        self.depth = self.state = 0
        self.buffer = ""
        self.parser = xml.parsers.expat.ParserCreate(namespace_separator=' ')
        self.parser.CharacterDataHandler = self.handleCharData
        self.parser.StartElementHandler = self.handleStartElement
        self.parser.EndElementHandler = self.handleEndElement

    def handleCharData(self, data):
        if self.state == self.depth == 3:
            self.buffer += data

    def handleStartElement(self, data, attrs):
        ns_uri, tag = data.split()
        if ns_uri == NC_NS_URI:
            if self.state == self.depth == 0 and tag == "hello":
                self.state = 1
            elif self.state == self.depth == 1 and tag == "capabilities":
                self.state = 2
            elif self.state == self.depth == 2 and tag == "capability":
                self.state = 3
        self.depth += 1

    def handleEndElement(self, data):
        ns_uri, tag = data.split()
        if ns_uri == NC_NS_URI:
            if self.state == self.depth == 1 and tag == "hello":
                self.state = 0
            elif self.state == self.depth == 2 and tag == "capabilities":
                self.state = 1
            elif self.state == self.depth == 3 and tag == "capability":
                self.capabilities.append(Capability(self.buffer))
                self.buffer = ""
                self.state = 2
        self.depth -= 1

    def parse(self, fd):
        self.parser.ParseFile(fd)
        return self

    def yang_modules(self):
        """
        Return a list of advertised YANG module names with revisions.

        Avoid repeated modules.
        """
        res = {}
        for c in self.capabilities:
            m = c.parameters.get("module")
            if m is None or m in res.keys():
                continue
            res[m] = c.parameters.get("revision")
        return res.items()
    
    def yang_implicit_deviation_modules(self):
        """
        Return an iterable of deviations to YANG modules which are referenced
        but not explicitly advertised as a module.
        """
        deviations = set()
        advertised_modules = set(dict(self.yang_modules()).keys())
        for c in self.capabilities:
            deviation_string = c.parameters.get("deviations")
            if not deviation_string:
                continue
            for deviation in deviation_string.split(","):
                if not deviation or deviation in advertised_modules:
                    continue
                deviations.add(deviation)
        return deviations

    def get_features(self, yam):
        """Return list of features declared for module `yam`."""
        mcap = [ c for c in self.capabilities
                 if c.parameters.get("module", None) == yam ][0]
        features = mcap.parameters.get("features")
        return features.split(",") if features else []

    def registered_capabilities(self):
        """Return dictionary of non-YANG capabilities.

        Only capabilities from the `CAPABILITIES` dictionary are taken
        into account.
        """
        return dict ([ (CAPABILITIES[c.id],c) for c in self.capabilities
                 if c.id in CAPABILITIES ])
