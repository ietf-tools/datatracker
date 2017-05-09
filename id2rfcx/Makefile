
version := $(shell id2xml --version | awk '{print $$2}' )

all: id2xml/id2xml.1.gz upload

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

dist:	id2xml/*
	python setup.py sdist
	python setup.py bdist_wheel --python-tag py27

upload:	dist
	twine upload dist/id2xml-$(version)* -r testpypi
