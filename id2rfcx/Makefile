
all: id2xml/id2xml.1.gz

%.1: id2xml/parser.py
	./$< -h | sed -r -e 's/^optional arguments:/OPTIONS/' \
			-e 's/^usage:/SYNOPSIS\n/' \
			-e '$!N;s/\n                        /  /' \
			-e 's/positional arguments:/ARGUMENTS/' \
			-e 's/^  -/\n  -/' \
		| txt2man -s1 -r'RFC Format Tools' -t $< > $@

%.1.gz:	%.1
	gzip < $< > $@
