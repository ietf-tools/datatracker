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
# This outputs an iCalendar file containing one event in each timezone,
# as well as all the VTIMEZONEs. We use it for testing compatability with
# other iCalendar apps like Outlook, by trying to import it there.
#
# Currently we have 377 timezones (with tzdata2001d).
#

# Set this to the toplevel directory of the VTIMEZONE files.
$ZONEINFO_DIR = "/home/damon/src/zoneinfo";

$output_file = "calendar.ics";


# Save this so we can restore it later.
$input_record_separator = $/;

chdir $ZONEINFO_DIR
    || die "Can't cd to $ZONEINFO_DIR";

# Create the output file, to contain all the VEVENTs & VTIMEZONEs.
open (OUTPUTFILE, ">$output_file")
    || die "Can't create file: $output_file";

# Output the standard header.
    print OUTPUTFILE <<EOF;
BEGIN:VCALENDAR
PRODID:-//Ximian//NONSGML Vzic Test//EN
VERSION:2.0
METHOD:PUBLISH
EOF

$zone_num = 0;

# 365 days in a non-leap year.
@days_in_month = ( 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 );

foreach $file (`find -name "*.ics"`) {
    # Get rid of './' at start and whitespace at end.
    $file =~ s/^\.\///;
    $file =~ s/\s+$//;

    if ($file eq $output_file) {
	next;
    }

#    print "File: $file\n";

    # Get the VTIMEZONE data.
    open (ZONEFILE, "$file")
	|| die "Can't open file: $ZONEINFO_DIR/$file";
    undef $/;
    $vtimezone = <ZONEFILE>;
    $/ = $input_record_separator;
    close (ZONEFILE);

    # Strip the stuff before and after the VTIMEZONE component
    $vtimezone =~ s/^.*BEGIN:VTIMEZONE/BEGIN:VTIMEZONE/s;
    $vtimezone =~ s/END:VTIMEZONE.*$/END:VTIMEZONE\n/s;

    print OUTPUTFILE $vtimezone;

    # Find the TZID.
    $vtimezone =~ m/TZID:(.*)/;
    $tzid = $1;
#    print "TZID: $tzid\n";

    # Find the location.
    $file =~ m/(.*)\.ics/;
    $location = $1;
#    print "LOCATION: $location\n";

    # Try to find the current UTC offset that Outlook will use.
    # If there is an RRULE, we look for the first 2 TZOFFSETTO properties,
    # else we just get the first one.
    if ($vtimezone =~ m/RRULE/) {
	$vtimezone =~ m/TZOFFSETTO:([+-]?\d+)/;
	$tzoffsetto = $1;
	$vtimezone =~ m/TZOFFSETFROM:([+-]?\d+)/;
	$tzoffsetfrom = $1;
	$tzoffset = "$tzoffsetfrom/$tzoffsetto";
    } else {
	$vtimezone =~ m/TZOFFSETTO:([+-]?\d+)/s;
	$tzoffset = $1;
    }
#    print "TZOFFSET: $tzoffset\n";

    # We put each event on a separate day in 2001 and Jan 2002.
    $day_num = $zone_num;
    if ($day_num >= 365) {
	$year = 2002;
	$day_num -= 365;
    } else {
	$year = 2001;
    }
    $month = -1;
    for ($i = 0; $i < 12; $i++) {
	if ($day_num < $days_in_month[$i]) {
	    $month = $i;
	    last;
	}
	$day_num -= $days_in_month[$i]
    }
    if ($month == -1) {
	die "month = -1";
    }

    $month++;
    $day_num++;
    $date = sprintf ("%i%02i%02i", $year, $month, $day_num);
#    print "Date: $date\n";

    # Output a VEVENT using the timezone.
    print OUTPUTFILE <<EOF;
BEGIN:VEVENT
UID:vzic-test-${zone_num}
DTSTAMP:20010101T000000Z
DTSTART;TZID=${tzid}:${date}T120000
DTEND;TZID=${tzid}:${date}T130000
RRULE:FREQ=MONTHLY;BYMONTHDAY=${day_num}
SUMMARY:($tzoffset) ${location} 12:00-13:00 UTC 
SEQUENCE:1
END:VEVENT
EOF

    $zone_num++;

    # Use this to stop after a certain number.
#    last if ($zone_num == 100);
}

# Output the standard footer.
    print OUTPUTFILE <<EOF;
END:VCALENDAR
EOF

close (OUTPUTFILE);

