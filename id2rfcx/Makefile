
version := $(shell id2xml --version | awk '{print $$2}' )

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
	python setup.py install

dist:	id2xml/*
	python setup.py -q sdist
	gpg --detach-sign -a dist/id2xml-$(version).tar.gz
	python setup.py -q bdist_wheel --python-tag py27
	gpg --detach-sign -a dist/id2xml-$(version)-py27-none-any.whl


upload:	dist
	twine upload dist/id2xml-$(version)* -r pypi
