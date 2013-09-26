include $(TOP)/common.mk

DIRS ?= $(shell find . -maxdepth 1 -type d | grep -v tests | egrep -v '\.$$' | sed 's/\.\///')
SOURCEFILES ?= $(shell find $(DIRS) -type f)

all : deb

deb:: $(DEB)

info :
	@echo VER=$(VER)
	@echo REV=$(REV)
	@echo PKG=$(PKG)
	@echo DEB=$(DEB)
	@echo GENFILES=$(GENFILES)
	@echo DIRS=$(DIRS)
	@echo SOURCEFILES=$(SOURCEFILES) | fold -s

$(DEB):: ${GENFILES}
	@rm -rf tmp
	@mkdir -p tmp
	@cp -r $(DIRS) tmp
	@perl -pi \
		-e 's/\$$\(VER\)/'$(VER)'/g;' \
		-e 's/\$$\(WEEK\)/'$(WEEK)'/g;' \
		-e 's/\$$\(REVISION\)/'$(REVISION)'/g;' \
		tmp/DEBIAN/control
	@echo Packaging $(DEB)
	@fakeroot -u sh -c 'chown -f -R root tmp; dpkg-deb -b tmp $(DEB)'
	@rm -rf tmp

push:: $(DEB)
	@scp $(DEB) $(INCOMING)
	@if [ -n "$(INCOMING2)" ]; then scp $(DEB) $(INCOMING2); fi
	@echo $(DEB) '->' $(INCOMING) $(INCOMING2)

divert :
	perl $(TOP)/tools/divert $(PKG)

clean::
	@rm -rf *.deb tmp

.PHONY : all deb push divert clean
