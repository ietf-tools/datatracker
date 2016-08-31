
#
# You will need to set this to the directory that the Olson timezone data
# files are in.
#
OLSON_DIR = /usr/share/olson


# This is used as the PRODID property on the iCalendar files output.
# It identifies the product which created the iCalendar objects.
# So you need to substitute your own organization name and product.
PRODUCT_ID = -//IETF Tools//NONSGML ietf-agenda-ical 1.03//EN

# This is what libical-evolution uses.
#PRODUCT_ID = -//Ximian//NONSGML Evolution Olson-VTIMEZONE Converter//EN


# This is used to create unique IDs for each VTIMEZONE component.
# The prefix is put before each timezone city name. It should start and end
# with a '/'. The first part, i.e. 'myorganization.org' below, should be
# a unique vendor ID, e.g. use a hostname. The part after that can be
# anything you want. We use a date and version number for libical. The %D
# gets expanded to today's date. There is also a vzic-merge.pl which can be
# used to merge changes into a master set of VTIMEZONEs. If a VTIMEZONE has
# changed, it bumps the version number on the end of this prefix. */
#TZID_PREFIX = /tools.ietf.org/Olson_%D_1/
TZID_PREFIX = 

# This is what libical-evolution uses.
#TZID_PREFIX = /softwarestudio.org/Olson_%D_1/


# Set any -I include directories to find the libical header files, and the
# libical library to link with. You only need these if you want to run the
# tests. You may need to change the '#include <ical.h>' line at the top of
# test-vzic.c as well.
LIBICAL_CFLAGS =
LIBICAL_LDADD = -lical-evolution


#
# You shouldn't need to change the rest of the file.
#

GLIB_CFLAGS = `pkg-config --cflags glib-2.0`
GLIB_LDADD = `pkg-config --libs glib-2.0`

CFLAGS = -g -DOLSON_DIR=\"$(OLSON_DIR)\" -DPRODUCT_ID='"$(PRODUCT_ID)"' -DTZID_PREFIX='"$(TZID_PREFIX)"' $(GLIB_CFLAGS) $(LIBICAL_CFLAGS)

OBJECTS = vzic.o vzic-parse.o vzic-dump.o vzic-output.o

all: vzic zoneinfo

vzic: $(OBJECTS)
	$(CC) $(OBJECTS) $(GLIB_LDADD) -o vzic

test-vzic: test-vzic.o
	$(CC) test-vzic.o $(LIBICAL_LDADD) -o test-vzic

zoneinfo: vzic
	mkdir -p tzdata
	cd tzdata; wget -N http://www.ietf.org/timezones/tzdata-latest.tar.gz
	cd tzdata; tar xzf tzdata-latest.tar.gz
	./vzic --olson-dir tzdata --pure

# Dependencies.
$(OBJECTS): vzic.h
vzic.o vzic-parse.o: vzic-parse.h
vzic.o vzic-dump.o: vzic-dump.h
vzic.o vzic-output.o: vzic-output.h

test-parse: vzic
	./vzic-dump.pl $(OLSON_DIR)
	./vzic --dump --pure
	@echo
	@echo "#"
	@echo "# If either of these diff commands outputs anything there may be a problem."
	@echo "#"
	diff -ru zoneinfo/ZonesPerl zoneinfo/ZonesVzic
	diff -ru zoneinfo/RulesPerl zoneinfo/RulesVzic

test-changes: vzic test-vzic
	./test-vzic --dump-changes
	./vzic --dump-changes --pure
	@echo
	@echo "#"
	@echo "# If this diff command outputs anything there may be a problem."
	@echo "#"
	diff -ru zoneinfo/ChangesVzic test-output

clean:
	-rm -rf vzic $(OBJECTS) *~ ChangesVzic RulesVzic ZonesVzic RulesPerl ZonesPerl test-vzic test-vzic.o tzdata

.PHONY: clean perl-dump test-parse
