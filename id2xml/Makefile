
version := $(shell python id2xml/parser.py --version | awk '{print $$2}' )

testfiles= \
	draft-baba-iot-problems-03.txt				\
	draft-ietf-6man-rfc2460bis-11.txt			\
	draft-ietf-curdle-cms-eddsa-signatures-05.txt		\
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
diffiles = $(addsuffix .diff, $(basename $(resfiles)))
tests    = $(addsuffix .test, $(basename $(resfiles)))


all: install upload

%.1: id2xml/parser.py id2xml/__init__.py
	id2xml -h | sed -e 's/^optional arguments:/OPTIONS/'	\
			-e 's/^usage:/SYNOPSIS\n/'		\
			-e 's/^positional arguments:/ARGUMENTS/'\
			-e 's/^  -/\n  -/'			\
		  | sed -e '/^  -/N;s/\n         */  /'		\
		  | txt2man -s1 -r'RFC Format Tools' -t $< > $@


%.1.gz:	%.1
	gzip < $< > $@

pyflakes:
	pyflakes id2xml

	
install: id2xml/id2xml.1.gz
	python setup.py -q install

env/bin/id2xml:	id2xml/parser.py
	python setup.py -q install

# ------------------------------------------------------------------------
# test

test:	env/bin/id2xml $(resfiles) $(diffiles) $(tests) 

infiles: $(textfiles)

test/in/draft-%.txt:
	wget -q -N -P test/in/ https://tools.ietf.org/id/$(notdir $@)

test/in/rfc%.txt:
	wget -q -N -P test/in/ https://tools.ietf.org/rfc/$(notdir $@)

test/out/%.test:	test/ok/%.diff test/out/%.diff
#	cp $(word 2,$^) $(word 1,$^)
	@oklen=`grep '^<' $(word 1,$^) | wc -l`; outlen=`grep '^<' $(word 2,$^) | wc -l`;	\
	totlen=`wc -l < test/in/$(basename $(@F)).txt`;			\
	ratio=$$(( outlen * 100 / totlen ));				\
	printf "Changed now/ok: %-48s %2s%%  %4s /%4s\n" $(basename $(@F)) $$ratio $$outlen $$oklen ; \
	test $$oklen -ge $$outlen || { diff -y $^ | less; }

test/in/%.raw: test/in/%.txt
	id2xml --strip-only $< -o - | sed -r -e '/[Tt]able [Oo]f [Cc]ontents?/,/^[0-9]+\./d' > $@

test/out/%.raw: test/out/%.txt
	id2xml --strip-only $< -o - | sed -r -e '/[Tt]able [Oo]f [Cc]ontents?/,/^[0-9]+\./d' > $@

test/out/%.diff:	test/in/%.raw test/out/%.raw 
	diff $(word 1,$^) $(word 2,$^) > $@ || true

test/out/%.txt:	test/out/%.xml
	xml2rfc $< -o $@

test/out/%.xml:	test/in/%.txt id2xml/parser.py
	@echo ""
	id2xml $< -o $@

# ------------------------------------------------------------------------

dist/id2xml-$(version).tar.gz: setup.py id2xml/*
	python setup.py -q sdist

dist/id2xml-$(version)-py27-none-any.whl: setup.py id2xml/*
	python setup.py -q bdist_wheel --python-tag py27

dist/%.asc: dist/%
	gpg --detach-sign -a $<

sdist:		dist/id2xml-$(version).tar.gz			dist/id2xml-$(version).tar.gz.asc
bdist_wheel:	dist/id2xml-$(version)-py27-none-any.whl	dist/id2xml-$(version)-py27-none-any.whl.asc

dist:	test sdist bdist_wheel

upload:	install test dist
	twine upload dist/id2xml-$(version)* -r pypi
