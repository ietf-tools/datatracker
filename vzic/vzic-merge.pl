#!/usr/bin/perl -w

#
# Vzic - a program to convert Olson timezone database files into VZTIMEZONE
# files compatible with the iCalendar specification (RFC2445).
#
# Copyright (C) 2001 Ximian, Inc.
# Copyright (C) 2003 Damon Chaplin.
#
# Author: Damon Chaplin <damon@gnome.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#

#
# This merges in a new set of VTIMEZONE files with the 'master' set. It only
# updates the files in the master set if the VTIMEZONE component has really
# been changes. Note that the TZID normally includes the date the VTIMEZONE
# file was generated on, so we have to ignore this when comparing the files.
#

# Set these to the toplevel directories of the 2 sets of VTIMEZONE files.
#$MASTER_ZONEINFO_DIR = "/home/damon/cvs/libical/zoneinfo";
$MASTER_ZONEINFO_DIR = "/usr/share/libical-evolution/zoneinfo";
$NEW_ZONEINFO_DIR = "/home/damon/src/vzic-1.0/zoneinfo";

# Set this to 1 if you have version numbers in the TZID like libical.
$LIBICAL_VERSIONING = 1;

# Set this to 0 for dry-runs, and 1 to actually update.
$DO_UPDATES = 1;

# Save this so we can restore it later.
$input_record_separator = $/;

chdir $NEW_ZONEINFO_DIR
    || die "Can't cd to $NEW_ZONEINFO_DIR";

foreach $new_file (`find -name "*.ics"`) {
    # Get rid of './' at start and whitespace at end.
    $new_file =~ s/^\.\///;
    $new_file =~ s/\s+$//;

#    print "File: $new_file\n";

    open (NEWZONEFILE, "$new_file")
	|| die "Can't open file: $NEW_ZONEINFO_DIR/$new_file";
    undef $/;
    $new_contents = <NEWZONEFILE>;
    $/ = $input_record_separator;
    close (NEWZONEFILE);

    $master_file = $MASTER_ZONEINFO_DIR . "/$new_file";

#    print "Master File: $master_file\n";

    $copy_to_master = 0;

    # If the ics file exists in the master copy we have to compare them,
    # otherwise we can just copy the new file into the master directory.
    if (-e $master_file) {
	open (MASTERZONEFILE, "$master_file")
	    || die "Can't open file: $master_file";
	undef $/;
	$master_contents = <MASTERZONEFILE>;
	$/ = $input_record_separator;
	close (MASTERZONEFILE);
	
	$new_contents_copy = $new_contents;

	# Strip the TZID from both contents.
	$new_contents_copy =~ s/^TZID:\S+$//m;
	$new_tzid = $&;
	$master_contents =~ s/^TZID:\S+$//m;
	$master_tzid = $&;

#	print "Matched: $master_tzid\n";


	if ($new_contents_copy ne $master_contents) {
	    print "$new_file has changed. Updating...\n";
	    $copy_to_master = 1;

	    if ($LIBICAL_VERSIONING) {
		# We bump the version number in the new file.
		$master_tzid =~ m%_(\d+)/%;
		$version_num = $1;
#		print "Version: $version_num\n";

		$version_num++;
		$new_tzid =~ s%_(\d+)/%_$version_num/%;

#		print "New TZID: $new_tzid\n";
		$new_contents =~ s/^TZID:\S+$/$new_tzid/m;
	    }
	}

    } else {
	print "$new_file doesn't exist in master directory. Copying...\n";
	$copy_to_master = 1;
    }

    if ($copy_to_master) {
#	print "Updating: $new_file\n";

	if ($DO_UPDATES) {
	    open (MASTERZONEFILE, ">$master_file")
		|| die "Can't create file: $master_file";
	    print MASTERZONEFILE $new_contents;
	    close (MASTERZONEFILE);
	}
    }

}

