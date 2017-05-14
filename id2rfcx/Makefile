
version := $(shell id2xml --version | awk '{print $$2}' )

testfiles= \
	draft-baba-iot-problems-03.txt				\
	draft-ietf-6man-rfc2460bis-11.txt			\
	draft-ietf-httpbis-header-structure-01.txt		\
	draft-ietf-i2nsf-client-facing-interface-req-01.txt	\
	draft-ietf-mip4-multiple-tunnel-support-07.txt		\
	draft-ietf-netmod-revised-datastores-02.txt		\
	draft-ietf-ospf-encapsulation-cap-02.txt		\
	draft-ietf-perc-dtls-tunnel-01.txt			\
	draft-ietf-v6ops-rfc7084-bis-01.txt			\
	draft-miek-test.txt					\
	draft-sparks-genarea-review-tracker-03.txt		\
	rfc5661.txt						\
	rfc7629.txt						\
	rfc7842.txt

textfiles= $(addprefix test/in/, $(testfiles))
resfiles = $(addprefix test/out/, $(testfiles))
xmlfiles = $(addsuffix .xml, $(basename $(resfiles)))
tests    = $(addsuffix .test, $(basename $(resfiles)))


all: id2xml/id2xml.1.gz install upload

%.1: id2xml/parser.py
	./$< -h | sed -r -e 's/^optional arguments:/OPTIONS/' \
			-e 's/^usage:/SYNOPSIS\n/' \
			-e '$!N;s/\n                        /  /' \
			-e 's/positional arguments:/ARGUMENTS/' \
			-e 's/^  -/\n  -/' \
		| txt2man -s1 -r'RFC Format Tools' -t $< > $@

%.1.gz:	%.1
	gzip < $< > $@

pyflakes:
	pyflakes id2xml

	
install:
	python setup.py -q install

env/bin/id2xml:	id2xml/parser.py
	python setup.py -q install

# ------------------------------------------------------------------------
# test

test:	env/bin/id2xml $(resfiles) $(tests) 

infiles: $(textfiles)

test/in/draft-%.txt:
	wget -q -N -P test/in/ https://tools.ietf.org/id/$(notdir $@)

test/in/rfc%.txt:
	wget -q -N -P test/in/ https://tools.ietf.org/rfc/$(notdir $@)

test/out/%.test:	test/ok/%.diff test/out/%.diff
#	cp $(word 2,$^) $(word 1,$^)
	test `wc -l < $(word 1,$^)` -ge `wc -l < $(word 2,$^)`

test/in/%.raw: test/in/%.txt
	id2xml --strip-only $< -o $@

test/out/%.raw: test/out/%.txt
	id2xml --strip-only $< -o $@

test/out/%.diff:	test/in/%.raw test/out/%.raw 
	diff $(word 1,$^) $(word 2,$^) > $@ || true

test/out/%.txt:	test/out/%.xml
	xml2rfc $< -o $@

test/out/%.xml:	test/in/%.txt id2xml/parser.py
	@echo ""
	id2xml $< -o $@

# ------------------------------------------------------------------------

dist:	id2xml/*
	python setup.py -q sdist
	gpg --detach-sign -a dist/id2xml-$(version).tar.gz
	python setup.py -q bdist_wheel --python-tag py27
	gpg --detach-sign -a dist/id2xml-$(version)-py27-none-any.whl


upload:	dist
	twine upload dist/id2xml-$(version)* -r pypi
