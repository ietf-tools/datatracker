import re
from tzparse import tzparse
from datetime import datetime as Datetime

def parse_date(dstr):
    formats = [
        "%d %b %Y %H:%M:%S %Z",         # standard logfile format
        "%d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M %Z",
        "%d %b %Y %H:%M",
        "%d %b %Y %Z",        
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d_%H:%M:%S %Z",
        "%Y-%m-%d_%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%Z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M %Z",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        ]
    for format in formats:
        try:
            t = tzparse(dstr, format)
            return t
        except Exception:
            pass
    raise Exception("Couldn't parse the date string '%s'" % dstr)
            
class ChangeLogEntry:
    package = ""
    version = ""
    logentry = ""
    author = ""
    email = ""
    date = ""
    time = ""

def parse(logfile):
    ver_line = "^(\w+) \((\S+)\) (\S+;)? (?:urgency=(\S+))?$"
    sig_line = "^ -- ([^<]+) <([^>]+)>  (.*?) *$"

    entries = []
    if type(logfile) == type(''):
        logfile = open(logfile)
    entry = None
    for line in logfile:
        if re.match(ver_line, line):
            package, version, distribution, urgency = re.match(ver_line, line).groups()
            entry = ChangeLogEntry()
            entry.package = package
            entry.version = version
            entry.logentry = ""
        elif re.match(sig_line, line):
            author, email, date = re.match(sig_line, line).groups()
            entry.author = author
            entry.email = email
            entry.date = date
            entry.time = parse_date(date)
            entry.logentry = entry.logentry.rstrip()
            entries += [ entry ]
        elif entry:
            entry.logentry += line
        else:
            print "Unexpected line: '%s'" % line
    return entries