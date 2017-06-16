/*
 * Vzic - a program to convert Olson timezone database files into VZTIMEZONE
 * files compatible with the iCalendar specification (RFC2445).
 *
 * Copyright (C) 2000-2001 Ximian, Inc.
 * Copyright (C) 2003 Damon Chaplin.
 *
 * Author: Damon Chaplin <damon@gnome.org>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

/*
 * test-vzic.c - test vzic + libical against mktime() and friends.
 *
 * Note that when we output VCALENDAR data compatible with Outlook the
 * results aren't all correct.
 *
 * We have to modify some RRULEs which makes these timezones incorrect:
 *
 *   Africa/Cairo
 *   America/Godthab
 *   America/Santiago
 *   Antarctica/Palmer
 *   Asia/Baghdad
 *   Asia/Damascus
 *   Asia/Jerusalem
 *
 * Also, we can only output one RDATE or a pair of RRULEs which may make some
 * other timezones incorrect sometimes (e.g. if they change).
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

#include <ical.h>
/*#include <evolution/ical.h>*/

#define CHANGES_MAX_YEAR 2030

/* These are the years between which we test against the Unix timezone
   functions, inclusive. When using 'vzic --pure' you can test the full
   range from 1970 to 2037 and it should match against mktime() etc.
   (assuming you are using the same Olson timezone data for both).

   But when using VTIMEZONE's that are compatible with Outlook, it is only
   worth testing times in the future. There will be lots of differences in
   the past, since we can't include any historical changes in the files. */
#if 1
#define DUMP_START_YEAR 2003
#define DUMP_END_YEAR	2037
#else
#define DUMP_START_YEAR 1970
#define DUMP_END_YEAR	2037
#endif

/* The maximum size of any complete pathname. */
#define PATHNAME_BUFFER_SIZE	1024

#ifndef	FALSE
#define	FALSE	(0)
#endif

#ifndef	TRUE
#define	TRUE	(!FALSE)
#endif

int VzicDumpChanges		= FALSE;

/* We output beneath the current directory for now. */
char *directory = "test-output";

static void	usage				(void);
static int	parse_zone_name			(char		*name,
						 char	       **directory,
						 char	       **subdirectory,
						 char	       **filename);
static void	ensure_directory_exists		(char		*directory);
static void	dump_local_times		(icaltimezone	*zone,
						 FILE		*fp);


int main(int argc, char* argv[])
{
  icalarray *zones;
  icaltimezone *zone;
  char *zone_directory, *zone_subdirectory, *zone_filename, *location;
  char output_directory[PATHNAME_BUFFER_SIZE];
  char filename[PATHNAME_BUFFER_SIZE];
  FILE *fp;
  int i;
  int skipping = TRUE;

  /*
   * Command-Line Option Parsing.
   */
  for (i = 1; i < argc; i++) {
    /* --dump-changes: Dumps a list of times when each timezone changed,
       and the new local time offset from UTC. */
    if (!strcmp (argv[i], "--dump-changes"))
      VzicDumpChanges = TRUE;

    else
      usage ();
  }


  zones = icaltimezone_get_builtin_timezones ();

  ensure_directory_exists (directory);

  for (i = 0; i < zones->num_elements; i++) {
    zone = icalarray_element_at (zones, i);

    location = icaltimezone_get_location (zone);

#if 0
    /* Use this to start at a certain zone. */
    if (skipping && strcmp (location, "America/Boise"))
      continue;
#endif

    skipping = FALSE;

    /* Use this to only output data for certain timezones. */
#if 0
    if (strcmp (location, "America/Cancun")
	&& strcmp (location, "Asia/Baku")
	&& strcmp (location, "Asia/Nicosia")
	&& strcmp (location, "Asia/Novosibirsk")
	&& strcmp (location, "Asia/Samarkand")
	&& strcmp (location, "Asia/Tashkent")
	&& strcmp (location, "Asia/Tbilisi")
	&& strcmp (location, "Asia/Yerevan")
	&& strcmp (location, "Australia/Broken_Hill")
	&& strcmp (location, "Europe/Simferopol")
	&& strcmp (location, "Europe/Tallinn")
	&& strcmp (location, "Europe/Zaporozhye")
	)
      continue;
#endif

#if 0
    printf ("%s\n", location);
#endif

    parse_zone_name (location, &zone_directory, &zone_subdirectory,
		     &zone_filename);

    sprintf (output_directory, "%s/%s", directory, zone_directory);
    ensure_directory_exists (output_directory);
    sprintf (filename, "%s/%s", output_directory, zone_filename);

    if (zone_subdirectory) {
      sprintf (output_directory, "%s/%s/%s", directory, zone_directory,
	       zone_subdirectory);
      ensure_directory_exists (output_directory);
      sprintf (filename, "%s/%s", output_directory, zone_filename);
    }

    fp = fopen (filename, "w");
    if (!fp) {
      fprintf (stderr, "Couldn't create file: %s\n", filename);
      exit (1);
    }

    /* We can run 2 different tests - output all changes for each zone, or
       test against mktime()/localtime(). Should have a command-line option
       or something. */
    if (VzicDumpChanges)
      icaltimezone_dump_changes (zone, CHANGES_MAX_YEAR, fp);
    else
      dump_local_times (zone, fp);

    if (ferror (fp)) {
      fprintf (stderr, "Error writing file: %s\n", filename);
      exit (1);
    }

    fclose (fp);
  }

  return 0;
}


static void
usage				(void)
{
  fprintf (stderr, "Usage: test-vzic [--dump-changes]\n");

  exit (1);
}


/* This checks that the Zone name only uses the characters in [-+_/a-zA-Z0-9],
   and outputs a warning if it isn't. */
static int
parse_zone_name			(char		*name,
				 char	       **directory,
				 char	       **subdirectory,
				 char	       **filename)
{
  static int invalid_zone_num = 1;

  char *p, ch, *first_slash_pos = NULL, *second_slash_pos = NULL;
  int invalid = FALSE;

  for (p = name; (ch = *p) != 0; p++) {
    if ((ch < 'a' || ch > 'z') && (ch < 'A' || ch > 'Z')
	&& (ch < '0' || ch > '9') && ch != '/' && ch != '_'
	&& ch != '-' && ch != '+') {
      fprintf (stderr, "Warning: Unusual Zone name: %s\n", name);
      invalid = TRUE;
      break;
    }

    if (ch == '/') {
      if (!first_slash_pos) {
	first_slash_pos = p;
      } else if (!second_slash_pos) {
	second_slash_pos = p;
      } else {
	fprintf (stderr, "Warning: More than 2 '/' characters in Zone name: %s\n", name);
	invalid = TRUE;
	break;
      }
    }
  }

  if (!first_slash_pos) {
	fprintf (stderr, "No '/' character in Zone name: %s. Skipping.\n", name);
	return FALSE;
  }

  if (invalid) {
    fprintf (stderr, "Invalid zone name: %s\n", name);
    exit (0);
  } else {
    *first_slash_pos = '\0';
    *directory = icalmemory_strdup (name);
    *first_slash_pos = '/';

    if (second_slash_pos) {
      *second_slash_pos = '\0';
      *subdirectory = icalmemory_strdup (first_slash_pos + 1);
      *second_slash_pos = '/';

      *filename = icalmemory_strdup (second_slash_pos + 1);
    } else {
      *subdirectory = NULL;
      *filename = icalmemory_strdup (first_slash_pos + 1);
    }
  }
}


static void
ensure_directory_exists		(char		*directory)
{
  struct stat filestat;

  if (stat (directory, &filestat) != 0) {
    /* If the directory doesn't exist, try to create it. */
    if (errno == ENOENT) {
      if (mkdir (directory, 0777) != 0) {
	fprintf (stderr, "Can't create directory: %s\n", directory);
	exit (1);
      }
    } else {
      fprintf (stderr, "Error calling stat() on directory: %s\n", directory);
      exit (1);
    }
  } else if (!S_ISDIR (filestat.st_mode)) {
    fprintf (stderr, "Can't create directory, already exists: %s\n",
	     directory);
    exit (1);
  }
}


static void
dump_local_times (icaltimezone *zone, FILE *fp)
{
  static char *months[] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
			    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
  icaltimezone *utc_timezone;
  struct icaltimetype tt, tt_copy;
  struct tm tm, local_tm;
  time_t t;
  char tzstring[256], *location;
  int last_year_output = 0;
  int total_error = 0, total_error2 = 0;

  utc_timezone = icaltimezone_get_utc_timezone ();

  /* This is our UTC time that we will use to iterate over the period. */
  tt.year = DUMP_START_YEAR;
  tt.month = 1;
  tt.day = 1;
  tt.hour = 0;
  tt.minute = 0;
  tt.second = 0;
  tt.is_utc = 0;
  tt.is_date = 0;
  tt.zone = "";

  tm.tm_year = tt.year - 1900;
  tm.tm_mon = tt.month - 1;
  tm.tm_mday = tt.day;
  tm.tm_hour = tt.hour;
  tm.tm_min = tt.minute;
  tm.tm_sec = tt.second;
  tm.tm_isdst = -1;

  /* Convert it to a time_t by saying it is in UTC. */
  putenv ("TZ=UTC");
  t = mktime (&tm);

  location = icaltimezone_get_location (zone);
  sprintf (tzstring, "TZ=%s", location);

  /*printf ("Zone: %s\n", location);*/
  putenv (tzstring);

  /* Loop around converting the UTC time to local time, outputting it, and
     then adding on 15 minutes to the UTC time. */
  while (tt.year <= DUMP_END_YEAR) {
    if (tt.year > last_year_output) {
      last_year_output = tt.year;
#if 0
      printf ("  %i\n", last_year_output);
      fprintf (fp, "  %i\n", last_year_output);
#endif
    }

#if 1
    /* First use the Unix functions. */
    /* Now convert it to a local time in the given timezone. */
    local_tm = *localtime (&t);
#endif

#if 1
    /* Now use libical. */
    tt_copy = tt;
    icaltimezone_convert_time (&tt_copy, utc_timezone, zone);
#endif

#if 1
    if (local_tm.tm_year + 1900 != tt_copy.year
	|| local_tm.tm_mon + 1 != tt_copy.month
	|| local_tm.tm_mday != tt_copy.day
	|| local_tm.tm_hour != tt_copy.hour
	|| local_tm.tm_min != tt_copy.minute
	|| local_tm.tm_sec != tt_copy.second) {

      /* The error format is:

     ERROR: Original-UTC-Time  Local-Time-From-mktime  Local-Time-From-Libical

      */

      total_error++;

      fprintf (fp, "ERROR:%2i %s %04i %2i:%02i:%02i UTC",
	       tt.day, months[tt.month - 1], tt.year,
	       tt.hour, tt.minute, tt.second);
      fprintf (fp, " ->%2i %s %04i %2i:%02i:%02i",
	       local_tm.tm_mday, months[local_tm.tm_mon],
	       local_tm.tm_year + 1900,
	       local_tm.tm_hour, local_tm.tm_min, local_tm.tm_sec);
      fprintf (fp, " Us:%2i %s %04i %2i:%02i:%02i\n",
	       tt_copy.day, months[tt_copy.month - 1], tt_copy.year,
	       tt_copy.hour, tt_copy.minute, tt_copy.second);
    }
#endif

    /* Now convert it back, and check we get the original time. */
    icaltimezone_convert_time (&tt_copy, zone, utc_timezone);
    if (tt.year != tt_copy.year
	|| tt.month != tt_copy.month
	|| tt.day != tt_copy.day
	|| tt.hour != tt_copy.hour
	|| tt.minute != tt_copy.minute
	|| tt.second != tt_copy.second) {

      total_error2++;

      fprintf (fp, "ERROR 2: %2i %s %04i %2i:%02i:%02i UTC",
	       tt.day, months[tt.month - 1], tt.year,
	       tt.hour, tt.minute, tt.second);
      fprintf (fp, " Us:%2i %s %04i %2i:%02i:%02i UTC\n",
	       tt_copy.day, months[tt_copy.month - 1], tt_copy.year,
	       tt_copy.hour, tt_copy.minute, tt_copy.second);
    }


    /* Increment the time. */
    icaltime_adjust (&tt, 0, 0, 15, 0);

    /* We assume leap seconds are not included in time_t values, which should
       be true on POSIX systems. */
    t += 15 * 60;
  }

  printf ("Zone: %40s  Errors: %i (%i)\n", icaltimezone_get_location (zone),
	  total_error, total_error2);
}
