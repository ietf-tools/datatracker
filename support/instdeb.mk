include $(TOP)/common.mk

DIRS ?= $(shell find . -maxdepth 1 -type d | egrep -v '\.$$' | sed 's/\.\///')

all : deb

deb : $(DEB)

$(DEB) :
	@rm -rf tmp
	@mkdir -p tmp tmp/DEBIAN
	@make DESTDIR=`pwd`/tmp install
	@perl -p -e 's/\$$\(VER\)/$(VER)/g' <DEBIAN/control >tmp/DEBIAN/control
	@echo Packaging $(DEB)
	@fakeroot sh -c 'chown -R root tmp; dpkg-deb -b tmp $(DEB)'
	@rm -rf tmp

push : $(DEB)
	scp $(DEB) $(INCOMING)

clean::
	@rm -rf *.deb tmp

.PHONY : all deb push clean
