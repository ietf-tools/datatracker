
all: id2xml id2xml.1.gz

%.1:	%
	./$< | txt2man -s1 -r'RFC Format Tools' -t $< > $@

%.1.gz:	%.1
	gzip $<
