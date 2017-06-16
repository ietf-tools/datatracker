#!/usr/bin/perl -w

#
# Vzic - a program to convert Olson timezone database files into VZTIMEZONE
# files compatible with the iCalendar specification (RFC2445).
#
# Copyright (C) 2000-2001 Ximian, Inc.
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
# This reads the Olson timezone files, strips any comments, and outputs them
# in a very simple format with tab-separated fields. It is used to compare
# with the output of dump_zone_data() and dump_rule_data() to double-check
# that we have parsed the files correctly.
#

my $zones_fh = "zonesfile";
my $rules_fh = "rulesfile";

my %Rules;

if ($#ARGV != 0) {
    die "Usage: $0 <OlsonDirectory>";
}

my $OLSON_DIR = $ARGV[0];

# We place output in subdirectories of the current directory.
my $OUTPUT_DIR = "zoneinfo";

if (! -d "$OUTPUT_DIR") {
    mkdir ("$OUTPUT_DIR", 0777)
	|| die "Can't create directory: $OUTPUT_DIR";
}
if (! -d "$OUTPUT_DIR/ZonesPerl") {
    mkdir ("$OUTPUT_DIR/ZonesPerl", 0777)
	|| die "Can't create directory: $OUTPUT_DIR/ZonesPerl";
}
if (! -d "$OUTPUT_DIR/RulesPerl") {
    mkdir ("$OUTPUT_DIR/RulesPerl", 0777)
	|| die "Can't create directory: $OUTPUT_DIR/RulesPerl";
}


&ReadOlsonFile ("africa");
&ReadOlsonFile ("antarctica");
&ReadOlsonFile ("asia");
&ReadOlsonFile ("australasia");
&ReadOlsonFile ("europe");
&ReadOlsonFile ("northamerica");
&ReadOlsonFile ("southamerica");

# These are backwards-compatability and weird stuff.
#&ReadOlsonFile ("backward");
#&ReadOlsonFile ("etcetera");
#&ReadOlsonFile ("leapseconds");
#&ReadOlsonFile ("pacificnew");
#&ReadOlsonFile ("solar87");
#&ReadOlsonFile ("solar88");
#&ReadOlsonFile ("solar89");

# We don't do this one since it is not useful and the use of '"' in the Zone
# line messes up our split() command.
#&ReadOlsonFile ("factory");

# We don't do this since the vzic program can't do it.
#&ReadOlsonFile ("systemv");




1;


sub ReadOlsonFile {
    my ($file) = @_;

#    print ("Reading olson file: $file\n");

    open (OLSONFILE, "$OLSON_DIR/$file")
	|| die "Can't open file: $file";

    open ($zones_fh, ">$OUTPUT_DIR/ZonesPerl/$file")
	|| die "Can't open file: $OUTPUT_DIR/ZonesPerl/$file";

    open ($rules_fh, ">$OUTPUT_DIR/RulesPerl/$file")
	|| die "Can't open file: $OUTPUT_DIR/RulesPerl/$file";

    %Rules = ();

    my $zone_continues = 0;

    while (<OLSONFILE>) {
	next if (m/^#/);

	# '#' characters can appear in strings, but the Olson files don't use
	# that feature at present so we treat all '#' as comments for now.
	s/#.*//;

	next if (m/^\s*$/);

	if ($zone_continues) {
	    $zone_continues = &ReadZoneContinuationLine;

	} elsif (m/^Rule\s/) {
	    &ReadRuleLine;

	} elsif (m/^Zone\s/) {
	    $zone_continues = &ReadZoneLine;

	} elsif (m/^Link\s/) {
#	    print "Link: $link_from, $link_to\n";

	} elsif (m/^Leap\s/) {
#	    print "Leap\n";

	} else {
	    die "Invalid line: $_";
	}
    }

#    print ("Read olson file: $file\n");

    foreach $key (sort (keys (%Rules))) {
	print $rules_fh "$Rules{$key}"
    }

    close ($zones_fh);
    close ($rules_fh);
    close (OLSONFILE);
}


sub ReadZoneLine {
    my ($zone, $name, $gmtoff, $rules_save, $format,
	$until_year, $until_month, $until_day, $until_time, $remainder)
	= split ' ', $_, 10;

    return &ReadZoneLineCommon ($zone, $name, $gmtoff, $rules_save, $format,
				$until_year, $until_month, $until_day,
				$until_time);
}


sub ReadZoneContinuationLine {
    my ($gmtoff, $rules_save, $format,
	$until_year, $until_month, $until_day, $until_time, $remainder)
	= split ' ', $_, 8;

    return &ReadZoneLineCommon ("", "", $gmtoff, $rules_save, $format,
				$until_year, $until_month, $until_day,
				$until_time);
}


sub ReadZoneLineCommon {
    my ($zone, $name, $gmtoff, $rules_save, $format,
	$until_year, $until_month, $until_day, $until_time) = @_;

    if (!defined ($until_year)) { $until_year = ""; }
    if (!defined ($until_month)) { $until_month = ""; }
    if (!defined ($until_day)) { $until_day = ""; }
    if (!defined ($until_time)) { $until_time = ""; }

    # A few of the gmtoffsets have an unnecessary :00 seconds.
    $gmtoff =~ s/(\d+):(\d+):00/$1:$2/;

    # Make sure the gmtoff does have minutes.
    $gmtoff =~ s/^(-?\d+)$/$1:00/;

    # Fix a few other bits so they all use the same format.
    if ($gmtoff eq "0") { $gmtoff = "0:00"; }
    $until_time =~ s/^0(\d):/$1:/;
    if ($until_time eq "0:00") { $until_time = ""; }
    if ($until_day eq "1" && $until_time eq "") { $until_day = ""; }
    if ($until_month eq "Jan" && $until_day eq "" && $until_time eq "") {
	$until_month = "";
    }

    # For Zone continuation lines we need to insert an extra TAB.
    if (!$zone) { $zone = "\t" };

    print $zones_fh "$zone\t$name\t$gmtoff\t$rules_save\t$format\t$until_year\t$until_month\t$until_day\t$until_time\n";

    if (defined ($until_year) && $until_year) {
	return 1;
    } else {
	return 0;
    }
}


sub ReadRuleLine {
    my ($rule, $name, $from, $to, $type, $in, $on, $at, $save, $letter_s,
	$remainder) = split;

    $at =~ s/(\d+:\d+):00/$1/;
    $save =~ s/(\d+:\d+):00/$1/;
    if ($save eq "0:00") { $save = "0"; }

    $Rules{$name} .= "$rule\t$name\t$from\t$to\t$type\t$in\t$on\t$at\t$save\t$letter_s\n";

#    print $rules_fh "$rule\t$name\t$from\t$to\t$type\t$in\t$on\t$at\t$save\t$letter_s\n";
}

