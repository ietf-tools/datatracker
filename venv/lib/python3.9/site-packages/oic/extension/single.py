class SingleService(object):
    def __init__(self, host):
        self.host = host
        self.endpoints = {}  # type: ignore


class SingleClient(object):
    def __init__(self, host):
        self.host = host
        self.requests = {}  # type: ignore
