# Copyright The IETF Trust 2007, All Rights Reserved

#from django.db import models

alphabet = [chr(65 + i) for i in range(0, 26)]
orgs_dict = {
	'iab': { 'name': 'IAB' },
	'iana': { 'name': 'IANA' },
	'iasa': { 'name': 'IASA' },
	'iesg': { 'name': 'IESG' },
	'irtf': { 'name': 'IRTF' },
	'proto': { 'name': 'PROTO' },
	'rfc-editor': { 'name': 'RFC Editor', 'prefixes': [ 'rfc-editor', 'rfced' ] },
	'tools': { 'name': 'Tools' },
}
orgs_keys = orgs_dict.keys()
for o in orgs_keys:
    orgs_dict[o]['key'] = o
orgs_keys.sort()
orgs = [orgs_dict[o] for o in orgs_keys]

