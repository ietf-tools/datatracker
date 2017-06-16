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

/* ALGORITHM:
 *
 * First we expand all the Rule arrays, so that each element only represents 1
 * year. If a Rule extends to infinity we expand it up to a few years past the
 * maximum UNTIL year used in any of the timezones. We do this to make sure
 * that the last of the expanded Rules (which may be infinite) is only used
 * in the last of the time periods (i.e. the last Zone line).
 *
 * The Rule arrays are also sorted by the start time (FROM + IN + ON + AT).
 * Doing all this makes it much easier to find which rules apply to which
 * periods.
 *
 * For each timezone (i.e. ZoneData element), we step through each of the
 * time periods, the ZoneLineData elements (which represent each Zone line
 * from the Olson file.)
 *
 * We calculate the start & end time of the period.
 * - For the first line the start time is -infinity.
 * - For the last line the end time is +infinity.
 * - The end time of each line is also the start time of the next.
 * 
 * We create an array of time changes which occur in this period, including
 * the one implied by the Zone line itself (though this is later taken out
 * if it is found to be at exactly the same time as the first Rule).
 *
 * Now we iterate over the time changes, outputting them as STANDARD or
 * DAYLIGHT components. We also try to merge them together into RRULEs or
 * use RDATEs.
 */


#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>

#include "vzic.h"
#include "vzic-output.h"

#include "vzic-dump.h"


/* These come from the Makefile. See the comments there. */
char *ProductID = PRODUCT_ID;
char *TZIDPrefix = TZID_PREFIX;

/* We expand the TZIDPrefix, replacing %D with the date, in here. */
char TZIDPrefixExpanded[1024];


/* We only use RRULEs if there are at least MIN_RRULE_OCCURRENCES occurrences,
   since otherwise RDATEs are more efficient. Actually, I've set this high
   so we only use RRULEs for infinite recurrences. Since expanding RRULEs is
   very time-consuming, this seems sensible. */
#define MIN_RRULE_OCCURRENCES	100


/* The year we go up to when dumping the list of timezone changes (used
   for testing & debugging). */
#define MAX_CHANGES_YEAR	2030

/* This is the maximum year that time_t value can typically hold on 32-bit
   systems. */
#define MAX_TIME_T_YEAR		2037


/* The year we use to start RRULEs. */
#define RRULE_START_YEAR	1970

/* The year we use for RDATEs. */
#define RDATE_YEAR		1970


static char *WeekDays[] = { "SU", "MO", "TU", "WE", "TH", "FR", "SA" };
static int DaysInMonth[] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };

char *CurrentZoneName;


typedef struct _VzicTime VzicTime;
struct _VzicTime
{
  /* Normal years, e.g. 2001. */
  int year;

  /* 0 (Jan) to 11 (Dec). */
  int month;

  /* The day, either a simple month day number, 1-31, or a rule such as
     the last Sunday, or the first Monday on or after the 8th. */
  DayCode	day_code;
  int		day_number;		/* 1 to 31. */
  int		day_weekday;		/* 0 (Sun) to 6 (Sat). */

  /* The time, in seconds from midnight. The code specifies whether the
     time is a wall clock time, local standard time, or universal time. */
  int		time_seconds;
  TimeCode	time_code;

  /* The offset from UTC for local standard time. */
  int		stdoff;

  /* The offset from UTC for local wall clock time. If this is different to
     stdoff then this is a DAYLIGHT component. This is TZOFFSETTO. */
  int		walloff;

  /* TRUE if the time change recurs every year to infinity. */
  gboolean	is_infinite;

  /* TRUE if the change has already been output. */
  gboolean	output;

  /* These are the offsets of the previous VzicTime, and are used when
     calculating the time of the change. We place them here in
     output_zone_components() to simplify the output code. */
  int		prev_stdoff;
  int		prev_walloff;

  /* The abbreviated form of the timezone name. Note that this may not be
     unique. */
  char	       *tzname;
};


static void	expand_and_sort_rule_array	(gpointer	 key,
						 gpointer	 value,
						 gpointer	 data);
static int	rule_sort_func			(const void	*arg1,
						 const void	*arg2);
static void	output_zone			(char		*directory,
						 ZoneData	*zone,
						 char		*zone_name,
						 GHashTable	*rule_data);
static gboolean	parse_zone_name			(char		*name,
						 char	       **directory,
						 char	       **subdirectory,
						 char	       **filename);
static void	output_zone_to_files		(ZoneData	*zone,
						 char		*zone_name,
						 GHashTable	*rule_data,
						 FILE		*fp,
						 FILE		*changes_fp);
static gboolean	add_rule_changes		(ZoneLineData	*zone_line,
						 char		*zone_name,
						 GArray		*changes,
						 GHashTable	*rule_data,
						 VzicTime	*start,
						 VzicTime	*end,
						 char	       **start_letter_s,
						 int		*save_seconds);
static char*	expand_tzname			(char		*zone_name,
						 char		*format,
						 gboolean	 have_letter_s,
						 char		*letter_s,
						 gboolean	 is_daylight);
static int	compare_times			(VzicTime	*time1,
						 int		 stdoff1,
						 int		 walloff1,
						 VzicTime	*time2,
						 int		 stdoff2,
						 int		 walloff2);
static gboolean times_match			(VzicTime	*time1,
						 int		 stdoff1,
						 int		 walloff1,
						 VzicTime	*time2,
						 int		 stdoff2,
						 int		 walloff2);
static void	output_zone_components		(FILE		*fp,
						 char		*name,
						 GArray		*changes);
static void	set_previous_offsets		(GArray		*changes);
static gboolean	check_for_recurrence		(FILE		*fp,
						 GArray		*changes,
						 int		 idx);
static void	check_for_rdates		(FILE		*fp,
						 GArray		*changes,
						 int		 idx);
static gboolean	timezones_match			(char		*tzname1,
						 char		*tzname2);
static int	output_component_start		(char		*buffer,
						 VzicTime	*vzictime,
						 gboolean	 output_rdate,
						 gboolean	 use_same_tz_offset);
static void	output_component_end		(FILE		*fp,
						 VzicTime	*vzictime);

static void	vzictime_init			(VzicTime	*vzictime);
static int	calculate_actual_time		(VzicTime	*vzictime,
						 TimeCode	 time_code,
						 int		 stdoff,
						 int		 walloff);
static int	calculate_wall_time		(int		 time,
						 TimeCode	 time_code,
						 int		 stdoff,
						 int		 walloff,
						 int		*day_offset);
static int	calculate_until_time		(int		 time,
						 TimeCode	 time_code,
						 int		 stdoff,
						 int		 walloff,
						 int		*year,
						 int		*month,
						 int		*day);
static void	fix_time_overflow		(int		*year,
						 int		*month,
						 int		*day,
						 int		 day_offset);

static char*	format_time			(int		 year,
						 int		 month,
						 int		 day,
						 int		 time);
static char*	format_tz_offset		(int		 tz_offset,
						 gboolean	 round_seconds);
static gboolean output_rrule			(char	        *rrule_buffer,
						 int		 month,
						 DayCode	 day_code,
						 int		 day_number,
						 int		 day_weekday,
						 int		 day_offset,
						 char		*until);
static gboolean	output_rrule_2			(char		*buffer,
						 int		 month,
						 int		 day_number,
						 int		 day_weekday);

static char*	format_vzictime			(VzicTime	*vzictime);

static void	dump_changes			(FILE		*fp,
						 char		*zone_name,
						 GArray		*changes);
static void	dump_change			(FILE		*fp,
						 char		*zone_name,
						 VzicTime	*vzictime,
						 int		 year);

static void	expand_tzid_prefix		(void);


void
output_vtimezone_files		(char		*directory,
				 GArray		*zone_data,
				 GHashTable	*rule_data,
				 GHashTable	*link_data,
				 int		 max_until_year)
{
  ZoneData *zone;
  GList *links;
  char *link_to;
  int i;

  /* Insert today's date into the TZIDs we output. */
  expand_tzid_prefix ();

  /* Expand the rule data so that each entry specifies only one year, and
     sort it so we can easily find the rules applicable to each Zone span. */
  g_hash_table_foreach (rule_data, expand_and_sort_rule_array,
			GINT_TO_POINTER (max_until_year));

  /* Output each timezone. */
  for (i = 0; i < zone_data->len; i++) {
    zone = &g_array_index (zone_data, ZoneData, i);
    output_zone (directory, zone, zone->zone_name, rule_data);

    /* Look for any links from this zone. */
    links = g_hash_table_lookup (link_data, zone->zone_name);

    while (links) {
      link_to = links->data;

      /* We ignore Links that don't have a '/' in them (things like 'EST5EDT').
       */
      if (strchr (link_to, '/')) {
	output_zone (directory, zone, link_to, rule_data);
      }

      links = links->next;
    }
  }
}


static void
expand_and_sort_rule_array	(gpointer	 key,
				 gpointer	 value,
				 gpointer	 data)
{
  char *name = key;
  GArray *rule_array = value;
  RuleData *rule, tmp_rule;
  int len, max_year, i, from, to, year;
  gboolean is_infinite;

  /* We expand the rule data to a year greater than any year used in a Zone
     UNTIL value. This is so that we can easily get parts of the array to
     use for each Zone line. */
  max_year = GPOINTER_TO_INT (data) + 2;

  /* If any of the rules apply to several years, we turn it into a single rule
     for each year. If the Rule is infinite we go up to max_year.
     We change the FROM field in the copies of the Rule, setting it to each
     of the years, and set TO to FROM, except if TO was YEAR_MAXIMUM we set
     the last TO to YEAR_MAXIMUM, so we still know the Rule is infinite. */
  len = rule_array->len;
  for (i = 0; i < len; i++) {
    rule = &g_array_index (rule_array, RuleData, i);

    /* None of the Rules currently use the TYPE field, but we'd better check.
     */
    if (rule->type) {
      fprintf (stderr, "Rules %s has a TYPE: %s\n", name, rule->type);
      exit (1);
    }

    if (rule->from_year != rule->to_year) {
      from = rule->from_year;
      to = rule->to_year;

      tmp_rule = *rule;

      /* Flag that this is a shallow copy so we don't free anything twice. */
      tmp_rule.is_shallow_copy = TRUE;

      /* See if it is an infinite Rule. */
      if (to == YEAR_MAXIMUM) {
	is_infinite = TRUE;
	to = max_year;
	if (from < to)
	  rule->to_year = rule->from_year;
      } else {
	is_infinite = FALSE;
      }

      /* Create a copy of the Rule for each year. */
      for (year = from + 1; year <= to; year++) {
	tmp_rule.from_year = year;

	/* If the Rule is infinite, mark the last copy as infinite. */
	if (year == to && is_infinite)
	  tmp_rule.to_year = YEAR_MAXIMUM;
	else
	  tmp_rule.to_year = year;

	g_array_append_val (rule_array, tmp_rule);
      }
    }
  }

  /* Now sort the rules. */
  qsort (rule_array->data, rule_array->len, sizeof (RuleData), rule_sort_func);

#if 0
  dump_rule_array (name, rule_array, stdout);
#endif
}


/* This is used to sort the rules, after the rules have all been expanded so
   that each one is only for one year. */
static int
rule_sort_func			(const void	*arg1,
				 const void	*arg2)
{
  RuleData *rule1, *rule2;
  int time1_year, time1_month, time1_day;
  int time2_year, time2_month, time2_day;
  int month_diff, result;
  VzicTime t1, t2;

  rule1 = (RuleData*) arg1;
  rule2 = (RuleData*) arg2;

  time1_year = rule1->from_year;
  time1_month = rule1->in_month;
  time2_year = rule2->from_year;
  time2_month = rule2->in_month;

  /* If there is more that one month difference we don't need to calculate
     the day or time. */
  month_diff = (time1_year - time2_year) * 12 + time1_month - time2_month;

  if (month_diff > 1)
    return 1;
  if (month_diff < -1)
    return -1;

  /* Now we have to calculate the day and time of the Rule start and the
     VzicTime, using the given offsets. */
  t1.year = time1_year;
  t1.month = time1_month;
  t1.day_code = rule1->on_day_code;
  t1.day_number = rule1->on_day_number;
  t1.day_weekday = rule1->on_day_weekday;
  t1.time_code = rule1->at_time_code;
  t1.time_seconds = rule1->at_time_seconds;

  t2.year = time2_year;
  t2.month = time2_month;
  t2.day_code = rule2->on_day_code;
  t2.day_number = rule2->on_day_number;
  t2.day_weekday = rule2->on_day_weekday;
  t2.time_code = rule2->at_time_code;
  t2.time_seconds = rule2->at_time_seconds;

  /* FIXME: We don't know the offsets yet, but I don't think any Rules are
     close enough together that the offsets can make a difference. Should
     check this. */
  calculate_actual_time (&t1, TIME_WALL, 0, 0);
  calculate_actual_time (&t2, TIME_WALL, 0, 0);

  /* Now we can compare the entire time. */
  if (t1.year > t2.year)
    result = 1;
  else if (t1.year < t2.year)
    result = -1;

  else if (t1.month > t2.month)
    result = 1;
  else if (t1.month < t2.month)
    result = -1;

  else if (t1.day_number > t2.day_number)
    result = 1;
  else if (t1.day_number < t2.day_number)
    result = -1;

  else if (t1.time_seconds > t2.time_seconds)
    result = 1;
  else if (t1.time_seconds < t2.time_seconds)
    result = -1;

  else {
    printf ("WARNING: Rule dates matched.\n");
    result = 0;
  }

  return result;
}


static void
output_zone			(char		*directory,
				 ZoneData	*zone,
				 char		*zone_name,
				 GHashTable	*rule_data)
{
  FILE *fp, *changes_fp = NULL;
  char output_directory[PATHNAME_BUFFER_SIZE];
  char filename[PATHNAME_BUFFER_SIZE];
  char changes_filename[PATHNAME_BUFFER_SIZE];
  char *zone_directory, *zone_subdirectory, *zone_filename;

  /* Set a global for the zone_name, to be used only for debug messages. */
  CurrentZoneName = zone_name;

  /* Use this to only output a particular zone. */
#if 0
  if (strcmp (zone_name, "Atlantic/Azores"))
    return;
#endif

#if 0
  printf ("Outputting Zone: %s\n", zone_name);
#endif

  if (!parse_zone_name (zone_name, &zone_directory, &zone_subdirectory,
			&zone_filename))
    return;

  if (VzicDumpZoneNamesAndCoords) {
    VzicTimeZoneNames = g_list_prepend (VzicTimeZoneNames,
					g_strdup (zone_name));
  }

  sprintf (output_directory, "%s/%s", directory, zone_directory);
  ensure_directory_exists (output_directory);
  sprintf (filename, "%s/%s.ics", output_directory, zone_filename);

  if (VzicDumpChanges) {
    sprintf (output_directory, "%s/ChangesVzic/%s", directory, zone_directory);
    ensure_directory_exists (output_directory);
    sprintf (changes_filename, "%s/%s", output_directory, zone_filename);
  }

  if (zone_subdirectory) {
    sprintf (output_directory, "%s/%s/%s", directory, zone_directory,
	     zone_subdirectory);
    ensure_directory_exists (output_directory);
    sprintf (filename, "%s/%s.ics", output_directory, zone_filename);

    if (VzicDumpChanges) {
      sprintf (output_directory, "%s/ChangesVzic/%s/%s", directory,
	       zone_directory, zone_subdirectory);
      ensure_directory_exists (output_directory);
      sprintf (changes_filename, "%s/%s", output_directory, zone_filename);
    }
  }

  /* Create the files. */
  fp = fopen (filename, "w");
  if (!fp) {
    fprintf (stderr, "Couldn't create file: %s\n", filename);
    exit (1);
  }

  if (VzicDumpChanges) {
    changes_fp = fopen (changes_filename, "w");
    if (!changes_fp) {
      fprintf (stderr, "Couldn't create file: %s\n", changes_filename);
      exit (1);
    }
  }

  fprintf (fp, "BEGIN:VCALENDAR\nPRODID:%s\nVERSION:2.0\n", ProductID);

  output_zone_to_files (zone, zone_name, rule_data, fp, changes_fp);

  if (ferror (fp)) {
    fprintf (stderr, "Error writing file: %s\n", filename);
    exit (1);
  }

  fprintf (fp, "END:VCALENDAR\n");

  fclose (fp);

  g_free (zone_directory);
  g_free (zone_subdirectory);
  g_free (zone_filename);
}


/* This checks that the Zone name only uses the characters in [-+_/a-zA-Z0-9],
   and outputs a warning if it isn't. */
static gboolean
parse_zone_name			(char		*name,
				 char	       **directory,
				 char	       **subdirectory,
				 char	       **filename)
{
  static int invalid_zone_num = 1;

  char *p, ch, *first_slash_pos = NULL, *second_slash_pos = NULL;
  gboolean invalid = FALSE;

  for (p = name; (ch = *p) != 0; p++) {
    if ((ch < 'a' || ch > 'z') && (ch < 'A' || ch > 'Z')
	&& (ch < '0' || ch > '9') && ch != '/' && ch != '_'
	&& ch != '-' && ch != '+') {
      fprintf (stderr, "WARNING: Unusual Zone name: %s\n", name);
      invalid = TRUE;
      break;
    }

    if (ch == '/') {
      if (!first_slash_pos) {
	first_slash_pos = p;
      } else if (!second_slash_pos) {
	second_slash_pos = p;
      } else {
	fprintf (stderr, "WARNING: More than 2 '/' characters in Zone name: %s\n", name);
	invalid = TRUE;
	break;
      }
    }
  }

  if (!first_slash_pos) {
#if 0
	fprintf (stderr, "No '/' character in Zone name: %s. Skipping.\n", name);
#endif
	return FALSE;
  }

  if (invalid) {
    *directory = g_strdup ("Invalid");
    *filename = g_strdup_printf ("Zone%i", invalid_zone_num++);
  } else {
    *first_slash_pos = '\0';
    *directory = g_strdup (name);
    *first_slash_pos = '/';

    if (second_slash_pos) {
      *second_slash_pos = '\0';
      *subdirectory = g_strdup (first_slash_pos + 1);
      *second_slash_pos = '/';

      *filename = g_strdup (second_slash_pos + 1);
    } else {
      *subdirectory = NULL;
      *filename = g_strdup (first_slash_pos + 1);
    }
  }

  return invalid ? FALSE : TRUE;
}


static void
output_zone_to_files		(ZoneData	*zone,
				 char		*zone_name,
				 GHashTable	*rule_data,
				 FILE		*fp,
				 FILE		*changes_fp)
{
  ZoneLineData *zone_line;
  GArray *changes;
  int i, stdoff, walloff, start_index, save_seconds;
  VzicTime start, end, *vzictime_start, *vzictime, *vzictime_first_rule_change;
  gboolean is_daylight, found_letter_s;
  char *start_letter_s;

  changes = g_array_new (FALSE, FALSE, sizeof (VzicTime));

  vzictime_init (&start);
  vzictime_init (&end);

  /* The first period starts at -infinity. */
  start.year = YEAR_MINIMUM;

  for (i = 0; i < zone->zone_line_data->len; i++) {
    zone_line = &g_array_index (zone->zone_line_data, ZoneLineData, i);

    /* This is the local standard time offset from GMT for this period. */
    start.stdoff = stdoff = zone_line->stdoff_seconds;
    start.walloff = walloff = stdoff + zone_line->save_seconds;

    if (zone_line->until_set) {
      end.year = zone_line->until_year;
      end.month = zone_line->until_month;
      end.day_code = zone_line->until_day_code;
      end.day_number = zone_line->until_day_number;
      end.day_weekday = zone_line->until_day_weekday;
      end.time_seconds = zone_line->until_time_seconds;
      end.time_code = zone_line->until_time_code;
    } else {
      /* The last period ends at +infinity. */
      end.year = YEAR_MAXIMUM;
    }

    /* Add a time change for the start of the period. This may be removed
       later if one of the rules expands to exactly the same time. */
    start_index = changes->len;
    g_array_append_val (changes, start);

    /* If there are Rules associated with this period, add all the relevant
       time changes. */
    save_seconds = 0;
    if (zone_line->rules)
      found_letter_s = add_rule_changes (zone_line, zone_name, changes,
					 rule_data, &start, &end,
					 &start_letter_s, &save_seconds);
    else
      found_letter_s = FALSE;

    /* FIXME: I'm not really sure what to do about finding a LETTER_S for the
       first part of the period (i.e. before the first Rule comes into effect).
       Currently we try to use the same LETTER_S as the first Rule of the
       period which is in local standard time. */
    if (zone_line->save_seconds)
      save_seconds = zone_line->save_seconds;
    is_daylight = save_seconds ? TRUE : FALSE;
    vzictime_start = &g_array_index (changes, VzicTime, start_index);
    walloff = vzictime_start->walloff = stdoff + save_seconds;

    /* TEST: See if the first Rule time is exactly the same as the change from
       the Zone line. In which case we can remove the Zone line change. */
    if (changes->len > start_index + 1) {
      int prev_stdoff, prev_walloff;

      if (start_index > 0) {
	VzicTime *v = &g_array_index (changes, VzicTime, start_index - 1);
	prev_stdoff = v->stdoff;
	prev_walloff = v->walloff;
      } else {
	prev_stdoff = 0;
	prev_walloff = 0;
      }
      vzictime_first_rule_change = &g_array_index (changes, VzicTime,
						   start_index + 1);
      if (times_match (vzictime_start, prev_stdoff, prev_walloff,
		       vzictime_first_rule_change, stdoff, walloff)) {
#if 0
	printf ("Removing zone-line change (using new offsets)\n");
#endif
	g_array_remove_index (changes, start_index);
	vzictime_start = NULL;
      } else if (times_match (vzictime_start, prev_stdoff, prev_walloff,
			      vzictime_first_rule_change, prev_stdoff, prev_walloff)) {
#if 0
	printf ("Removing zone-line change (using previous offsets)\n");
#endif
	g_array_remove_index (changes, start_index);
	vzictime_start = NULL;
      }
    }


    if (vzictime_start) {
      vzictime_start->tzname = expand_tzname (zone_name, zone_line->format,
					      found_letter_s,
					      start_letter_s, is_daylight);
    }

    /* The start of the next Zone line is the end time of this one. */
    start = end;
  }

  set_previous_offsets (changes);

  output_zone_components (fp, zone_name, changes);

  if (VzicDumpChanges)
    dump_changes (changes_fp, zone_name, changes);

  /* Free all the TZNAME fields. */
  for (i = 0; i < changes->len; i++) {
    vzictime = &g_array_index (changes, VzicTime, i);
    g_free (vzictime->tzname);
  }

  g_array_free (changes, TRUE);
}


/* This appends any timezone changes specified by the rules associated with
   the timezone, that happen between the start and end times.
   It returns the letter_s field of the first STANDARD rule found in the
   search. We need this to fill in any %s in the FORMAT field of the first
   component of the time period (the Zone line). */
static gboolean
add_rule_changes			(ZoneLineData	*zone_line,
					 char		*zone_name,
					 GArray		*changes,
					 GHashTable	*rule_data,
					 VzicTime	*start,
					 VzicTime	*end,
					 char	       **start_letter_s,
					 int		*save_seconds)
{
  GArray *rule_array;
  RuleData *rule, *prev_rule = NULL;
  int stdoff, walloff, i, prev_stdoff, prev_walloff;
  VzicTime vzictime;
  gboolean is_daylight, found_start_letter_s = FALSE;
  gboolean checked_for_previous = FALSE;

  *save_seconds = 0;

  rule_array = g_hash_table_lookup (rule_data, zone_line->rules);
  if (!rule_array) {
    fprintf (stderr, "Couldn't access rules: %s\n", zone_line->rules);
    exit (1);
  }

  /* The stdoff is the same for all the rules. */
  stdoff = start->stdoff;

  /* The walloff changes as we go through the rules. */
  walloff = start->walloff;

  /* Get the stdoff & walloff from the last change before this period. */
  if (changes->len >= 2) {
    VzicTime *change = &g_array_index (changes, VzicTime, changes->len - 2);
    prev_stdoff = change->stdoff;
    prev_walloff = change->walloff;
  } else {
    prev_stdoff = prev_walloff = 0;
  }


  for (i = 0; i < rule_array->len; i++) {
    rule = &g_array_index (rule_array, RuleData, i);

    is_daylight = rule->save_seconds != 0 ? TRUE : FALSE;

    vzictime_init (&vzictime);
    vzictime.year = rule->from_year;
    vzictime.month = rule->in_month;
    vzictime.day_code = rule->on_day_code;
    vzictime.day_number = rule->on_day_number;
    vzictime.day_weekday = rule->on_day_weekday;
    vzictime.time_seconds = rule->at_time_seconds;
    vzictime.time_code = rule->at_time_code;
    vzictime.stdoff = stdoff;
    vzictime.walloff = stdoff + rule->save_seconds;
    vzictime.is_infinite = (rule->to_year == YEAR_MAXIMUM) ? TRUE : FALSE;

    /* If the rule time is before the given start time, skip it. */
    if (compare_times (&vzictime, stdoff, walloff,
		       start, prev_stdoff, prev_walloff) < 0)
      continue;

    /* If the previous Rule was a daylight Rule, then we may want to use the
       walloff from that. */
    if (!checked_for_previous) {
      checked_for_previous = TRUE;
      if (i > 0) {
	prev_rule = &g_array_index (rule_array, RuleData, i - 1);
	if (prev_rule->save_seconds) {
	  walloff = start->walloff = stdoff + prev_rule->save_seconds;
	  *save_seconds = prev_rule->save_seconds;
	  found_start_letter_s = TRUE;
	  *start_letter_s = prev_rule->letter_s;
#if 0
	  printf ("Could use save_seconds from previous Rule: %s\n",
		  zone_name);
#endif
	}
      }
    }

    /* If an end time has been given, then if the rule time is on or after it
       break out of the loop. */
    if (end->year != YEAR_MAXIMUM
	&& compare_times (&vzictime, stdoff, walloff,
			  end, stdoff, walloff) >= 0)
      break;

    vzictime.tzname = expand_tzname (zone_name, zone_line->format, TRUE,
				     rule->letter_s, is_daylight);

    g_array_append_val (changes, vzictime);

    /* When we find the first STANDARD time we set letter_s. */
    if (!found_start_letter_s && !is_daylight) {
      found_start_letter_s = TRUE;
      *start_letter_s = rule->letter_s;
    }

    /* Now that we have added the Rule, the new walloff comes into effect
       for any following Rules. */
    walloff = vzictime.walloff;
  }

  return found_start_letter_s;
}


/* This expands the Zone line FORMAT field, using the given LETTER_S from a
   Rule line. There are 3 types of FORMAT field:
   1. a string with an %s in, e.g. "WE%sT". The %s is replaced with LETTER_S.
   2. a string with an '/' in, e.g. "CAT/CAWT". The first part is used for
      standard time and the second part for when daylight-saving is in effect.
   3. a plain string, e.g. "LMT", which we leave as-is.
   Note that (1) is the only type in which letter_s is required.
*/
static char*
expand_tzname				(char		*zone_name,
					 char		*format,
					 gboolean	 have_letter_s,
					 char		*letter_s,
					 gboolean	 is_daylight)
{
  char *p, buffer[256], *guess = NULL;
  int len;

#if 0
  printf ("Expanding %s with %s\n", format, letter_s);
#endif

  if (!format || !format[0]) {
    fprintf (stderr, "Missing FORMAT\n");
    exit (1);
  }

  /* 1. Look for a "%s". */
  p = strchr (format, '%');
  if (p && *(p + 1) == 's') {
    if (!have_letter_s) {

      /* NOTE: These are a few hard-coded TZNAMEs that I've looked up myself.
	 These are needed in a few places where a Zone line comes into effect
	 but no Rule has been found, so we have no LETTER_S to use.
	 I've tried to use whatever is the normal LETTER_S in the Rules for
	 the particular zone, in local standard time. */
      if (!strcmp (zone_name, "Asia/Macao")
	  && !strcmp (format, "C%sT"))
	guess = "CST";
      else if (!strcmp (zone_name, "Asia/Macau")
	       && !strcmp (format, "C%sT"))
	guess = "CST";
      else if (!strcmp (zone_name, "Asia/Ashgabat")
	       && !strcmp (format, "ASH%sT"))
	guess = "ASHT";
      else if (!strcmp (zone_name, "Asia/Ashgabat")
	       && !strcmp (format, "TM%sT"))
	guess = "TMT";
      else if (!strcmp (zone_name, "Asia/Samarkand")
	       && !strcmp (format, "TAS%sT"))
	guess = "TAST";
      else if (!strcmp (zone_name, "Atlantic/Azores")
	       && !strcmp (format, "WE%sT"))
	guess = "WET";
      else if (!strcmp (zone_name, "Europe/Paris")
	       && !strcmp (format, "WE%sT"))
	guess = "WET";
      else if (!strcmp (zone_name, "Europe/Warsaw")
	       && !strcmp (format, "CE%sT"))
	guess = "CET";
      else if (!strcmp (zone_name, "America/Phoenix")
	       && !strcmp (format, "M%sT"))
	guess = "MST";
      else if (!strcmp (zone_name, "America/Nome")
	       && !strcmp (format, "Y%sT"))
	guess = "YST";

      if (guess) {
#if 0
	fprintf (stderr,
		 "WARNING: Couldn't find a LETTER_S to use in FORMAT: %s in Zone: %s Guessing: %s\n",
		 format, zone_name, guess);
#endif
	return g_strdup (guess);
      }

#if 1
      fprintf (stderr,
	       "WARNING: Couldn't find a LETTER_S to use in FORMAT: %s in Zone: %s Leaving TZNAME empty\n",
	       format, zone_name);
#endif

#if 0
      /* This is useful to spot exactly which component had a problem. */
      sprintf (buffer, "FIXME: %s", format);
      return g_strdup (buffer);
#else
      /* We give up and don't output a TZNAME. */
      return NULL;
#endif
    }

    sprintf (buffer, format, letter_s ? letter_s : "");
    return g_strdup (buffer);
  }

  /* 2. Look for a "/". */
  p = strchr (format, '/');
  if (p) {
    if (is_daylight) {
      return g_strdup (p + 1);
    } else {
      len = p - format;
      strncpy (buffer, format, len);
      buffer[len] = '\0';
      return g_strdup (buffer);
    }
  }

  /* 3. Just use format as it is. */
  return g_strdup (format);
}


/* Compares 2 VzicTimes, returning strcmp()-like values, i.e. 0 if equal, 
   1 if the 1st is after the 2nd and -1 if the 1st is before the 2nd. */
static int
compare_times				(VzicTime	*time1,
					 int		 stdoff1,
					 int		 walloff1,
					 VzicTime	*time2,
					 int		 stdoff2,
					 int		 walloff2)
{
  VzicTime t1, t2;
  int result;

  t1 = *time1;
  t2 = *time2;

  calculate_actual_time (&t1, TIME_UNIVERSAL, stdoff1, walloff1);
  calculate_actual_time (&t2, TIME_UNIVERSAL, stdoff2, walloff2);

  /* Now we can compare the entire time. */
  if (t1.year > t2.year)
    result = 1;
  else if (t1.year < t2.year)
    result = -1;

  else if (t1.month > t2.month)
    result = 1;
  else if (t1.month < t2.month)
    result = -1;

  else if (t1.day_number > t2.day_number)
    result = 1;
  else if (t1.day_number < t2.day_number)
    result = -1;

  else if (t1.time_seconds > t2.time_seconds)
    result = 1;
  else if (t1.time_seconds < t2.time_seconds)
    result = -1;

  else
    result = 0;

#if 0
  printf ("%i/%i/%i %i <=> %i/%i/%i %i  -> %i\n",
	  t1.day_number, t1.month + 1, t1.year, t1.time_seconds,
	  t2.day_number, t2.month + 1, t2.year, t2.time_seconds,
	  result);
#endif

  return result;
}


/* Returns TRUE if the 2 times are exactly the same. It will calculate the
   actual day, but doesn't convert times. */
static gboolean
times_match				(VzicTime	*time1,
					 int		 stdoff1,
					 int		 walloff1,
					 VzicTime	*time2,
					 int		 stdoff2,
					 int		 walloff2)
{
  VzicTime t1, t2;

  t1 = *time1;
  t2 = *time2;

  calculate_actual_time (&t1, TIME_UNIVERSAL, stdoff1, walloff1);
  calculate_actual_time (&t2, TIME_UNIVERSAL, stdoff2, walloff2);

  if (t1.year == t2.year
      && t1.month == t2.month
      && t1.day_number == t2.day_number
      && t1.time_seconds == t2.time_seconds)
    return TRUE;

  return FALSE;
}


static void
output_zone_components			(FILE		*fp,
					 char		*name,
					 GArray		*changes)
{
  VzicTime *vzictime;
  int i, start_index = 0;
  gboolean only_one_change = FALSE;
  char start_buffer[1024];

  fprintf (fp, "BEGIN:VTIMEZONE\nTZID:%s%s\n", TZIDPrefixExpanded, name);

  if (VzicUrlPrefix != NULL)
      fprintf (fp, "TZURL:%s/%s\n", VzicUrlPrefix, name);

  /* We use an 'X-' property to place the city name in. */
  fprintf (fp, "X-LIC-LOCATION:%s\n", name);

  /* We try to find any recurring components first, or they may get output
     as lots of RDATES instead. */
  if (!VzicNoRRules) {
    int num_rrules_output = 0;

    for (i = 1; i < changes->len; i++) {
      if (check_for_recurrence (fp, changes, i)) {
	num_rrules_output++;
      }
    }

#if 0
    printf ("Zone: %s had %i infinite RRULEs\n", CurrentZoneName,
	    num_rrules_output);
#endif

    if (!VzicPureOutput && num_rrules_output == 2) {
#if 0
      printf ("Zone: %s using 2 RRULEs\n", CurrentZoneName);
#endif
      fprintf (fp, "END:VTIMEZONE\n");
      return;
    }
  }

  /* We skip the first change, which starts at -infinity, unless it is the only
     change for the timezone. */
  if (changes->len > 1)
    start_index = 1;
  else
    only_one_change = TRUE;

  /* For pure output, we start at the start of the array and step through it
     outputting RDATEs. For Outlook-compatible output we start at the end
     and step backwards to find the first STANDARD time to output. */
  if (VzicPureOutput)
    i = start_index - 1;
  else
    i = changes->len;

  for (;;) {
    if (VzicPureOutput)
      i++;
    else
      i--;

    if (VzicPureOutput) {
      if (i >= changes->len)
	break;
    } else {
      if (i < start_index)
	break;
    }

    vzictime = &g_array_index (changes, VzicTime, i);

    /* If we have already output this component as part of an RRULE or RDATE,
       then we skip it. */
    if (vzictime->output)
      continue;

    /* For Outlook-compatible output we only want to output the last STANDARD
       time as a DTSTART, so skip any DAYLIGHT changes. */
    if (!VzicPureOutput && vzictime->stdoff != vzictime->walloff) {
      printf ("Skipping DAYLIGHT change\n");
      continue;
    }

#if 0
    printf ("Zone: %s using DTSTART Year: %i\n", CurrentZoneName,
	    vzictime->year);
#endif

    if (VzicPureOutput) {
      output_component_start (start_buffer, vzictime, TRUE, only_one_change);
    } else {
    /* For Outlook compatability we don't output the RDATE and use the same
       TZOFFSET for TZOFFSETFROM and TZOFFSETTO. */
      vzictime->year         = RDATE_YEAR;
      vzictime->month        = 0;
      vzictime->day_code     = DAY_SIMPLE;
      vzictime->day_number   = 1;
      vzictime->time_code    = TIME_WALL;
      vzictime->time_seconds = 0;

      output_component_start (start_buffer, vzictime, FALSE, TRUE);
    }

    fprintf (fp, "%s", start_buffer);

    /* This will look for matching components and output them as RDATEs
       instead of separate components. */
    if (VzicPureOutput && !VzicNoRDates)
      check_for_rdates (fp, changes, i);

    output_component_end (fp, vzictime);

    vzictime->output = TRUE;

    if (!VzicPureOutput)
      break;
  }

  fprintf (fp, "END:VTIMEZONE\n");
}


/* This sets the prev_stdoff and prev_walloff (i.e. the TZOFFSETFROM) of each
   VzicTime, using the stdoff and walloff of the previous VzicTime. It makes
   the rest of the code much simpler. */
static void
set_previous_offsets		(GArray		*changes)
{
  VzicTime *vzictime, *prev_vzictime;
  int i;

  prev_vzictime = &g_array_index (changes, VzicTime, 0);
  prev_vzictime->prev_stdoff = 0;
  prev_vzictime->prev_walloff = 0;

  for (i = 1; i < changes->len; i++) {
    vzictime = &g_array_index (changes, VzicTime, i);

    vzictime->prev_stdoff = prev_vzictime->stdoff;
    vzictime->prev_walloff = prev_vzictime->walloff;

    prev_vzictime = vzictime;
  }
}


/* Returns TRUE if we output an infinite recurrence. */
static gboolean
check_for_recurrence		(FILE		*fp,
				 GArray		*changes,
				 int		 idx)
{
  VzicTime *vzictime_start, *vzictime, vzictime_start_copy;
  gboolean is_daylight_start, is_daylight;
  int last_match, i, next_year, day_offset;
  char until[256], rrule_buffer[2048], start_buffer[1024];
  GList *matching_elements = NULL, *elem;

  vzictime_start = &g_array_index (changes, VzicTime, idx);

  /* If this change has already been output, skip it. */
  if (vzictime_start->output)
    return FALSE;

  /* There can't possibly be an RRULE starting from YEAR_MINIMUM. */
  if (vzictime_start->year == YEAR_MINIMUM)
    return FALSE;

  is_daylight_start = (vzictime_start->stdoff != vzictime_start->walloff)
    ? TRUE : FALSE;

#if 0
  printf ("\nChecking: %s OFFSETFROM: %i %s\n",
	  format_vzictime (vzictime_start), vzictime_start->prev_walloff,
	  is_daylight_start ? "DAYLIGHT" : "");
#endif

  /* If this is an infinitely recurring change, output the RRULE and return.
     There won't be any changes after it that we could merge. */
  if (vzictime_start->is_infinite) {

    /* Change the year to our minimum start year. */
    vzictime_start_copy = *vzictime_start;
    if (!VzicPureOutput)
      vzictime_start_copy.year = RRULE_START_YEAR;

    day_offset = output_component_start (start_buffer, &vzictime_start_copy,
					 FALSE, FALSE);

    if (!output_rrule (rrule_buffer, vzictime_start_copy.month,
		       vzictime_start_copy.day_code,
		       vzictime_start_copy.day_number,
		       vzictime_start_copy.day_weekday, day_offset, "")) {
      if (vzictime_start->year != MAX_TIME_T_YEAR) {
	fprintf (stderr, "WARNING: Failed to output infinite recurrence with start year: %i\n", vzictime_start->year);
      }
      return TRUE;
    }

    fprintf (fp, "%s%s", start_buffer, rrule_buffer);
    output_component_end (fp, vzictime_start);
    vzictime_start->output = TRUE;
    return TRUE;
  }

  last_match = idx;
  next_year = vzictime_start->year + 1;
  for (i = idx + 1; i < changes->len; i++) {
    vzictime = &g_array_index (changes, VzicTime, i);

    is_daylight = (vzictime->stdoff != vzictime->walloff) ? TRUE : FALSE;

    if (vzictime->output)
      continue;

#if 0
    printf ("          %s OFFSETFROM: %i %s\n",
	    format_vzictime (vzictime), vzictime->prev_walloff,
	    is_daylight ? "DAYLIGHT" : "");
#endif

    /* If it is more than one year ahead, we are finished, since we want
       consecutive years. */
    if (vzictime->year > next_year) {
      break;
    }

    /* It must be the same type of component - STANDARD or DAYLIGHT. */
    if (is_daylight != is_daylight_start) {
      continue;
    }

    /* It must be the following year, with the same month, day & time.
       It is possible that the time has a different code but does in fact
       match when normalized, but we don't care (for now at least). */
    if (vzictime->year != next_year
	|| vzictime->month != vzictime_start->month
	|| vzictime->day_code != vzictime_start->day_code
	|| vzictime->day_number != vzictime_start->day_number
	|| vzictime->day_weekday != vzictime_start->day_weekday
	|| vzictime->time_seconds != vzictime_start->time_seconds
	|| vzictime->time_code != vzictime_start->time_code) {
      continue;
    }

    /* The TZOFFSETFROM and TZOFFSETTO must match. */
    if (vzictime->prev_walloff != vzictime_start->prev_walloff) {
      continue;
    }

    if (vzictime->walloff != vzictime_start->walloff) {
      continue;
    }

    /* TZNAME must match. */
    if (!timezones_match (vzictime->tzname, vzictime_start->tzname)) {
      continue;
    }

    /* We have a match. */
    last_match = i;
    next_year = vzictime->year + 1;

    matching_elements = g_list_prepend (matching_elements, vzictime);
  }

  if (last_match == idx)
    return FALSE;

#if 0
  printf ("Found recurrence %i - %i!!!\n", vzictime_start->year,
	  next_year - 1);
#endif

  vzictime = &g_array_index (changes, VzicTime, last_match);

/* We only use RRULEs if there are at least MIN_RRULE_OCCURRENCES occurrences,
   since otherwise RDATEs are more efficient. */
  if (!vzictime->is_infinite) {
    int years = vzictime->year - vzictime_start->year + 1;
#if 0
    printf ("RRULE Years: %i\n", years);
#endif
    if (years < MIN_RRULE_OCCURRENCES)
      return FALSE;
  }

  if (vzictime->is_infinite) {
    until[0] = '\0';
  } else {
    VzicTime t1 = *vzictime;

    printf ("RRULE with UNTIL - aborting\n");
    abort ();

    calculate_actual_time (&t1, TIME_UNIVERSAL, vzictime->prev_stdoff,
			   vzictime->prev_walloff);

    /* Output UNTIL, in UTC. */
    sprintf (until, ";UNTIL=%sZ", format_time (t1.year, t1.month,
					       t1.day_number,
					       t1.time_seconds));
  }

  /* Change the year to our minimum start year. */
  vzictime_start_copy = *vzictime_start;
  if (!VzicPureOutput)
    vzictime_start_copy.year = RRULE_START_YEAR;

  day_offset = output_component_start (start_buffer, &vzictime_start_copy,
				       FALSE, FALSE);
  if (output_rrule (rrule_buffer, vzictime_start_copy.month,
		    vzictime_start_copy.day_code,
		    vzictime_start_copy.day_number,
		    vzictime_start_copy.day_weekday, day_offset, until)) {
    fprintf (fp, "%s%s", start_buffer, rrule_buffer);
    output_component_end (fp, vzictime_start);

    /* Mark all the changes as output. */
    vzictime_start->output = TRUE;
    for (elem = matching_elements; elem; elem = elem->next) {
      vzictime = elem->data;
      vzictime->output = TRUE;
    }
  }

  g_list_free (matching_elements);

  return TRUE;
}


static void
check_for_rdates		(FILE		*fp,
				 GArray		*changes,
				 int		 idx)
{
  VzicTime *vzictime_start, *vzictime, tmp_vzictime;
  gboolean is_daylight_start, is_daylight;
  int i, year, month, day, time;

  vzictime_start = &g_array_index (changes, VzicTime, idx);

  is_daylight_start = (vzictime_start->stdoff != vzictime_start->walloff)
    ? TRUE : FALSE;

#if 0
  printf ("\nChecking: %s OFFSETFROM: %i %s\n",
	  format_vzictime (vzictime_start), vzictime_start->prev_walloff,
	  is_daylight_start ? "DAYLIGHT" : "");
#endif

  /* We want to go backwards through the array now, for Outlook compatability.
     (It only looks at the first DTSTART/RDATE.) */
  for (i = idx + 1; i < changes->len; i++) {
    vzictime = &g_array_index (changes, VzicTime, i);

    is_daylight = (vzictime->stdoff != vzictime->walloff) ? TRUE : FALSE;

    if (vzictime->output)
      continue;

#if 0
    printf ("          %s OFFSETFROM: %i %s\n", format_vzictime (vzictime),
	    vzictime->prev_walloff, is_daylight ? "DAYLIGHT" : "");
#endif

    /* It must be the same type of component - STANDARD or DAYLIGHT. */
    if (is_daylight != is_daylight_start) {
      continue;
    }

    /* The TZOFFSETFROM and TZOFFSETTO must match. */
    if (vzictime->prev_walloff != vzictime_start->prev_walloff) {
      continue;
    }

    if (vzictime->walloff != vzictime_start->walloff) {
      continue;
    }

    /* TZNAME must match. */
    if (!timezones_match (vzictime->tzname, vzictime_start->tzname)) {
      continue;
    }

    /* We have a match. */
    
    tmp_vzictime = *vzictime;
    calculate_actual_time (&tmp_vzictime, TIME_WALL, vzictime->prev_stdoff,
			   vzictime->prev_walloff);

    fprintf (fp, "RDATE:%s\n", format_time (tmp_vzictime.year,
					    tmp_vzictime.month,
					    tmp_vzictime.day_number,
					    tmp_vzictime.time_seconds));

    vzictime->output = TRUE;
  }
}


static gboolean
timezones_match				(char		*tzname1,
					 char		*tzname2)
{
  if (tzname1 && tzname2 && !strcmp (tzname1, tzname2))
    return TRUE;

  if (!tzname1 && !tzname2)
    return TRUE;

  return FALSE;
}


/* Outputs the start of a VTIMEZONE component, with the BEGIN line,
   the DTSTART, TZOFFSETFROM, TZOFFSETTO & TZNAME properties. */
static int
output_component_start			(char		*buffer,
					 VzicTime	*vzictime,
					 gboolean	 output_rdate,
					 gboolean	 use_same_tz_offset)
{
  gboolean is_daylight, skip_day_offset = FALSE;
  gint year, month, day, time, day_offset = 0;
  GDate old_date, new_date;
  char *formatted_time;
  char line1[1024], line2[1024], line3[1024];
  char line4[1024], line5[1024], line6[1024];
  VzicTime tmp_vzictime;
  int prev_walloff;

  is_daylight = (vzictime->stdoff != vzictime->walloff) ? TRUE : FALSE;

  tmp_vzictime = *vzictime;
  day_offset = calculate_actual_time (&tmp_vzictime, TIME_WALL,
				      vzictime->prev_stdoff,
				      vzictime->prev_walloff);

  sprintf (line1, "BEGIN:%s\n", is_daylight ? "DAYLIGHT" : "STANDARD");

  /* If the timezone only has one change, that means it uses the same offset
     forever, so we use the same TZOFFSETFROM as the TZOFFSETTO. (If the zone
     has more than one change, we don't output the first one.) */
  if (use_same_tz_offset)
    prev_walloff = vzictime->walloff;
  else
    prev_walloff = vzictime->prev_walloff;

  sprintf (line2, "TZOFFSETFROM:%s\n",
	   format_tz_offset (prev_walloff, !VzicPureOutput));

  sprintf (line3, "TZOFFSETTO:%s\n",
	   format_tz_offset (vzictime->walloff, !VzicPureOutput));

  if (vzictime->tzname)
    sprintf (line4, "TZNAME:%s\n", vzictime->tzname);
  else
    line4[0] = '\0';

  formatted_time = format_time (tmp_vzictime.year, tmp_vzictime.month,
				tmp_vzictime.day_number,
				tmp_vzictime.time_seconds);
  sprintf (line5, "DTSTART:%s\n", formatted_time);
  if (output_rdate)
    sprintf (line6, "RDATE:%s\n", formatted_time);
  else
    line6[0] = '\0';

  sprintf (buffer, "%s%s%s%s%s%s", line1, line2, line3, line4, line5, line6);

  return day_offset;
}


/* Outputs the END line of the VTIMEZONE component. */
static void
output_component_end			(FILE		*fp,
					 VzicTime	*vzictime)
{
  gboolean is_daylight;

  is_daylight = (vzictime->stdoff != vzictime->walloff) ? TRUE : FALSE;

  fprintf (fp, "END:%s\n", is_daylight ? "DAYLIGHT" : "STANDARD");
}


/* Initializes a VzicTime to 1st Jan in YEAR_MINIMUM at midnight, with all
   offsets set to 0. */
static void
vzictime_init				(VzicTime	*vzictime)
{
  vzictime->year = YEAR_MINIMUM;
  vzictime->month = 0;
  vzictime->day_code = DAY_SIMPLE;
  vzictime->day_number = 1;
  vzictime->day_weekday = 0;
  vzictime->time_seconds = 0;
  vzictime->time_code = TIME_UNIVERSAL;
  vzictime->stdoff = 0;
  vzictime->walloff = 0;
  vzictime->is_infinite = FALSE;
  vzictime->output = FALSE;
  vzictime->prev_stdoff = 0;
  vzictime->prev_walloff = 0;
  vzictime->tzname = NULL;
}


/* This calculates the actual local time that a change will occur, given
   the offsets from standard and wall-clock time. It returns -1 or 1 if it
   had to move backwards or forwards one day while converting to local time.
   If it does this then we need to change the RRULEs we output. */
static int
calculate_actual_time		(VzicTime	*vzictime,
				 TimeCode	 time_code,
				 int		 stdoff,
				 int		 walloff)
{
  GDate date;
  gint day_offset, days_in_month, weekday, offset, result;

  vzictime->time_seconds = calculate_wall_time (vzictime->time_seconds,
						vzictime->time_code,
						stdoff, walloff, &day_offset);

  if (vzictime->day_code != DAY_SIMPLE) {
    if (vzictime->year == YEAR_MINIMUM || vzictime->year == YEAR_MAXIMUM) {
      fprintf (stderr, "In calculate_actual_time: invalid year\n");
      exit (0);
    }

    g_date_clear (&date, 1);
    days_in_month = g_date_days_in_month (vzictime->month + 1, vzictime->year);

  /* Note that the day_code refers to the date before we convert it to
     a wall-clock date and time. So we find the day it was referring to,
     then make any adjustments needed due to converting the time. */
    if (vzictime->day_code == DAY_LAST_WEEKDAY) {
      /* Find out what day the last day of the month is. */
      g_date_set_dmy (&date, days_in_month, vzictime->month + 1,
		      vzictime->year);
      weekday = g_date_weekday (&date) % 7;

      /* Calculate how many days we have to go back to get to day_weekday. */
      offset = (weekday + 7 - vzictime->day_weekday) % 7;

      vzictime->day_number = days_in_month - offset;
    } else {
      /* Find out what day day_number actually is. */
      g_date_set_dmy (&date, vzictime->day_number, vzictime->month + 1,
		      vzictime->year);
      weekday = g_date_weekday (&date) % 7;

      if (vzictime->day_code == DAY_WEEKDAY_ON_OR_AFTER)
	offset = (vzictime->day_weekday + 7 - weekday) % 7;
      else
	offset = - ((weekday + 7 - vzictime->day_weekday) % 7);

      vzictime->day_number = vzictime->day_number + offset;
    }

    vzictime->day_code = DAY_SIMPLE;

    if (vzictime->day_number <= 0 || vzictime->day_number > days_in_month) {
      fprintf (stderr, "Day overflow: %i\n", vzictime->day_number);
      exit (1);
    }
  }

#if 0
  fprintf (stderr, "%s -> %i/%i/%i\n",
	   dump_day_coded (vzictime->day_code, vzictime->day_number,
			   vzictime->day_weekday),
	   vzictime->day_number, vzictime->month + 1, vzictime->year);
#endif

  fix_time_overflow (&vzictime->year, &vzictime->month,
		     &vzictime->day_number, day_offset);

  /* If we want UTC time, we have to convert it now. */
  if (time_code == TIME_UNIVERSAL) {
    vzictime->time_seconds = calculate_until_time (vzictime->time_seconds,
						   TIME_WALL, stdoff, walloff,
						   &vzictime->year,
						   &vzictime->month,
						   &vzictime->day_number);
  }

  return day_offset;
}


/* This converts the given time into universal time (UTC), to be used in
   the UNTIL property. */
static int
calculate_until_time			(int		 time,
					 TimeCode	 time_code,
					 int		 stdoff,
					 int		 walloff,
					 int		*year,
					 int		*month,
					 int		*day)
{
  int result, day_offset;

  day_offset = 0;

  switch (time_code) {
  case TIME_WALL:
    result = time - walloff;
    break;
  case TIME_STANDARD:
    result = time - stdoff;
    break;
  case TIME_UNIVERSAL:
    return time;
  default:
    fprintf (stderr, "Invalid time code\n");
    exit (1);
  }

  if (result < 0) {
    result += 24 * 60 * 60;
    day_offset = -1;
  } else if (result >= 24 * 60 * 60) {
    result -= 24 * 60 * 60;
    day_offset = 1;
  }

  /* Sanity check - we shouldn't have an overflow any more. */
  if (result < 0 || result >= 24 * 60 * 60) {
    fprintf (stderr, "Time overflow: %i\n", result);
    abort ();
  }

  fix_time_overflow (year, month, day, day_offset);

  return result;
}


/* This converts the given time into wall clock time (the local standard time
   with any adjustment for daylight-saving). */
static int
calculate_wall_time			(int		 time,
					 TimeCode	 time_code,
					 int		 stdoff,
					 int		 walloff,
					 int		*day_offset)
{
  int result;

  *day_offset = 0;

  switch (time_code) {
  case TIME_WALL:
    return time;
  case TIME_STANDARD:
    /* We have a local standard time, so we have to subtract stdoff to get
       back to UTC, then add walloff to get wall time. */
    result = time - stdoff + walloff;
    break;
  case TIME_UNIVERSAL:
    result = time + walloff;
    break;
  default:
    fprintf (stderr, "Invalid time code\n");
    exit (1);
  }

  if (result < 0) {
    result += 24 * 60 * 60;
    *day_offset = -1;
  } else if (result >= 24 * 60 * 60) {
    result -= 24 * 60 * 60;
    *day_offset = 1;
  }

  /* Sanity check - we shouldn't have an overflow any more. */
  if (result < 0 || result >= 24 * 60 * 60) {
    fprintf (stderr, "Time overflow: %i\n", result);
    exit (1);
  }

#if 0
  printf ("%s -> ", dump_time (time, time_code, TRUE));
  printf ("%s (%i)\n", dump_time (result, TIME_WALL, TRUE), *day_offset);
#endif

  return result;
}


static void
fix_time_overflow			(int		*year,
					 int		*month,
					 int		*day,
					 int		 day_offset)
{
  if (day_offset == -1) {
    *day = *day - 1;

    if (*day == 0) {
      *month = *month - 1;
      if (*month == -1) {
	*month = 11;
	*year = *year - 1;
      }
      *day = g_date_days_in_month (*month + 1, *year);
    }
  } else if (day_offset == 1) {
    *day = *day + 1;

    if (*day > g_date_days_in_month (*month + 1, *year)) {
      *month = *month + 1;
      if (*month == 12) {
	*month = 0;
	*year = *year + 1;
      }
      *day = 1;
    }
  }
}


static char*
format_time				(int		 year,
					 int		 month,
					 int		 day,
					 int		 time)
{
  static char buffer[128];
  int hour, minute, second;

  /* When we are outputting the first component year will be YEAR_MINIMUM.
     We used to use 1 when outputting this, but Outlook doesn't like any years
     less that 1600, so we use 1600 instead. We don't output the first change
     for most zones now, so it doesn't matter too much. */
  if (year == YEAR_MINIMUM)
    year = 1601;

  /* We just use 9999 here, so we keep to 4 characters. But this should only
     be needed when debugging - it shouldn't be needed in the VTIMEZONEs. */
  if (year == YEAR_MAXIMUM) {
    fprintf (stderr, "format_time: YEAR_MAXIMUM used\n");
    year = 9999;
  }

  hour = time / 3600;
  minute = (time % 3600) / 60;
  second = time % 60;

  sprintf (buffer, "%04i%02i%02iT%02i%02i%02i",
	   year, month + 1, day, hour, minute, second);

  return buffer;
}


/* Outlook doesn't support 6-digit values, i.e. including the seconds, so
   we round to the nearest minute. No current offsets use the seconds value,
   so we aren't losing much. */
static char*
format_tz_offset			(int		 tz_offset,
					 gboolean	 round_seconds)
{
  static char buffer[128];
  char *sign = "+";
  int hours, minutes, seconds;

  if (tz_offset < 0) {
    tz_offset = -tz_offset;
    sign = "-";
  }

  if (round_seconds)
    tz_offset += 30;

  hours = tz_offset / 3600;
  minutes = (tz_offset % 3600) / 60;
  seconds = tz_offset % 60;

  if (round_seconds)
    seconds = 0;

  /* Sanity check. Standard timezone offsets shouldn't be much more than 12
     hours, and daylight saving shouldn't change it by more than a few hours.
     (The maximum offset is 15 hours 56 minutes at present.) */
  if (hours < 0 || hours >= 24 || minutes < 0 || minutes >= 60
      || seconds < 0 || seconds >= 60) {
    fprintf (stderr, "WARNING: Strange timezone offset: H:%i M:%i S:%i\n",
	     hours, minutes, seconds);
  }

  if (seconds == 0)
    sprintf (buffer, "%s%02i%02i", sign, hours, minutes);
  else
    sprintf (buffer, "%s%02i%02i%02i", sign, hours, minutes, seconds);

  return buffer;
}


static gboolean
output_rrule				(char	        *rrule_buffer,
					 int		 month,
					 DayCode	 day_code,
					 int		 day_number,
					 int		 day_weekday,
					 int		 day_offset,
					 char		*until)
{
  char buffer[1024], buffer2[1024];

  buffer[0] = '\0';

  if (day_offset > 1 || day_offset < -1) {
    fprintf (stderr, "Invalid day_offset: %i\n", day_offset);
      exit (0);
  }

  /* If the DTSTART time was moved to another day when converting to local
     time, we need to adjust the RRULE accordingly. e.g. If the original RRULE
     was on the 19th of the month, but DTSTART was moved 1 day forward, then
     we output the 20th of the month instead. */
  if (day_offset == 1) {
    if (day_code != DAY_LAST_WEEKDAY)
      day_number++;
    day_weekday = (day_weekday + 1) % 7;

    /* Check we don't use February 29th. */
    if (month == 1 && day_number > 28) {
      fprintf (stderr, "Can't format RRULE - out of bounds. Month: %i Day number: %i\n", month + 1, day_number);
      exit (0);
    }

    /* If we go past the end of the month, move to the next month. */
    if (day_code != DAY_LAST_WEEKDAY && day_number > DaysInMonth[month]) {
      month++;
      day_number = 1;
    }

  } else if (day_offset == -1) {
    if (day_code != DAY_LAST_WEEKDAY)
      day_number--;
    day_weekday = (day_weekday + 6) % 7;

    if (day_code != DAY_LAST_WEEKDAY && day_number < 1)
      fprintf (stderr, "Month: %i Day number: %i\n", month + 1, day_number);
  }

  switch (day_code) {
  case DAY_SIMPLE:
    /* Outlook (2000) will not parse the simple YEARLY RRULEs in VTIMEZONEs,
       or BYMONTHDAY, or BYYEARDAY, which makes this option difficult!
       Currently we use something like BYDAY=1SU, which will be incorrect
       at times. This only affects Asia/Baghdad, Asia/Gaza, Asia/Jerusalem &
       Asia/Damascus at present (and Jerusalem doesn't have specific rules
       at the moment anyway, so that isn't a big loss). */
    if (!VzicPureOutput) {
      if (day_number < 8) {
	printf ("WARNING: %s: Outputting BYDAY=1SU instead of BYMONTHDAY=1-7 for Outlook compatability\n", CurrentZoneName);
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=1SU",
		 month + 1);
      } else if (day_number < 15) {
	printf ("WARNING: %s: Outputting BYDAY=2SU instead of BYMONTHDAY=8-14 for Outlook compatability\n", CurrentZoneName);
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=2SU",
		 month + 1);
      } else if (day_number < 22) {
	printf ("WARNING: %s: Outputting BYDAY=3SU instead of BYMONTHDAY=15-21 for Outlook compatability\n", CurrentZoneName);
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=3SU",
		 month + 1);
      } else {
	printf ("ERROR: %s: Couldn't output RRULE (day=%i) compatible with Outlook\n", CurrentZoneName, day_number);
	exit (1);
      }
    } else {
	sprintf (buffer, "RRULE:FREQ=YEARLY");
    }
    break;

  case DAY_WEEKDAY_ON_OR_AFTER:
    if (day_number > DaysInMonth[month] - 6) {
      /* This isn't actually needed at present. */
#if 0
      fprintf (stderr, "DAY_WEEKDAY_ON_OR_AFTER: %i %i\n", day_number,
	       month + 1);
#endif

      if (!VzicPureOutput) {
	printf ("ERROR: %s: Couldn't output RRULE (day>=x) compatible with Outlook\n", CurrentZoneName);
	exit (1);
      } else {
	/* We do 6 days at the end of this month, and 1 at the start of the
	   next. We can't do this if we want Outlook compatability, as it
	   needs BYMONTHDAY, which Outlook doesn't support. */
	sprintf (buffer,
		 "RRULE:FREQ=YEARLY;BYMONTH=%i;BYMONTHDAY=%i,%i,%i,%i,%i,%i;BYDAY=%s",
		 month + 1,
		 day_number, day_number + 1, day_number + 2, day_number + 3,
		 day_number + 4, day_number + 5,
		 WeekDays[day_weekday]);

	sprintf (buffer2,
		 "RRULE:FREQ=YEARLY;BYMONTH=%i;BYMONTHDAY=1;BYDAY=%s",
		 (month + 1) % 12 + 1,
		 WeekDays[day_weekday]);

	sprintf (rrule_buffer, "%s%s\n%s%s\n",
		 buffer, until, buffer2, until);

	return TRUE;
      }
    }

    if (!output_rrule_2 (buffer, month, day_number, day_weekday))
      return FALSE;

    break;

  case DAY_WEEKDAY_ON_OR_BEFORE:
    if (day_number < 7) {
      /* FIXME: This is unimplemented, but it isn't needed at present anway. */
      fprintf (stderr, "DAY_WEEKDAY_ON_OR_BEFORE: %i. Unimplemented. Exiting...\n", day_number);
      exit (0);
    }

    if (!output_rrule_2 (buffer, month, day_number - 6, day_weekday))
      return FALSE;

    break;

  case DAY_LAST_WEEKDAY:
    if (day_offset == 1) {
      if (month == 1) {
	fprintf (stderr, "DAY_LAST_WEEKDAY - day moved, in February - can't fix\n");
	exit (0);
      }

      /* This is only used once at present, for Africa/Cairo. */
#if 0
      fprintf (stderr, "DAY_LAST_WEEKDAY - day moved\n");
#endif

      if (!VzicPureOutput) {
	printf ("WARNING: %s: Modifying RRULE (last weekday) for Outlook compatability\n", CurrentZoneName);
	sprintf (buffer,
		 "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=-1%s",
		 month + 1, WeekDays[day_weekday]);
	printf ("  Outputting: %s\n", buffer);
      } else {
	/* We do 6 days at the end of this month, and 1 at the start of the
	   next. We can't do this if we want Outlook compatability, as it needs
	   BYMONTHDAY, which Outlook doesn't support. */
	day_number = DaysInMonth[month];
	sprintf (buffer,
		 "RRULE:FREQ=YEARLY;BYMONTH=%i;BYMONTHDAY=%i,%i,%i,%i,%i,%i;BYDAY=%s",
		 month + 1,
		 day_number - 5, day_number - 4, day_number - 3,
		 day_number - 2, day_number - 1, day_number,
		 WeekDays[day_weekday]);

	sprintf (buffer2,
		 "RRULE:FREQ=YEARLY;BYMONTH=%i;BYMONTHDAY=1;BYDAY=%s",
		 (month + 1) % 12 + 1,
		 WeekDays[day_weekday]);

	sprintf (rrule_buffer, "%s%s\n%s%s\n",
		 buffer, until, buffer2, until);

	return TRUE;
      }

    } else if (day_offset == -1) {
      /* We do 7 days 1 day before the end of this month. */
      day_number = DaysInMonth[month];

      if (!output_rrule_2 (buffer, month, day_number - 7, day_weekday))
	return FALSE;

      sprintf (rrule_buffer, "%s%s\n", buffer, until);
      return TRUE;
    }

    sprintf (buffer,
	     "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=-1%s",
	     month + 1, WeekDays[day_weekday]);
    break;

  default:
    fprintf (stderr, "Invalid day code\n");
    exit (1);
  }

  sprintf (rrule_buffer, "%s%s\n", buffer, until);
  return TRUE;
}


/* This tries to convert a RRULE like 'BYMONTHDAY=8,9,10,11,12,13,14;BYDAY=FR'
   into 'BYDAY=2FR'. We need this since Outlook doesn't accept BYMONTHDAY.
   It returns FALSE if conversion is not possible. */
static gboolean
output_rrule_2				(char		*buffer,
					 int		 month,
					 int		 day_number,
					 int		 day_weekday)
{

  if (day_number == 1) {
    /* Convert it to a BYDAY=1SU type of RRULE. */
    sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=1%s",
	     month + 1, WeekDays[day_weekday]);

  } else if (day_number == 8) {
    /* Convert it to a BYDAY=2SU type of RRULE. */
    sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=2%s",
	     month + 1, WeekDays[day_weekday]);

  } else if (day_number == 15) {
    /* Convert it to a BYDAY=3SU type of RRULE. */
    sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=3%s",
	     month + 1, WeekDays[day_weekday]);

  } else if (day_number == 22) {
    /* Convert it to a BYDAY=4SU type of RRULE. (Currently not used.) */
    sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=4%s",
	     month + 1, WeekDays[day_weekday]);

  } else if (month != 1 && day_number == DaysInMonth[month] - 6) {
    /* Convert it to a BYDAY=-1SU type of RRULE. (But never for February.) */
    sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=-1%s",
	     month + 1, WeekDays[day_weekday]);

  } else {
    /* Can't convert to a correct RRULE. If we want Outlook compatability we
       have to use a slightly incorrect RRULE, so the time change will be 1
       week out every 7 or so years. Alternatively we could possibly move the
       change by an hour or so so we would always be 1 or 2 hours out, but
       never 1 week out. Yes, that sounds a better idea. */
    if (!VzicPureOutput) {
      printf ("WARNING: %s: Modifying RRULE to be compatible with Outlook (day >= %i, month = %i)\n", CurrentZoneName, day_number, month + 1);

      if (day_number == 2) {
	/* Convert it to a BYDAY=1SU type of RRULE.
	   This is needed for Asia/Karachi. */
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=1%s",
		 month + 1, WeekDays[day_weekday]);
      } else if (day_number == 9) {
	/* Convert it to a BYDAY=2SU type of RRULE.
	   This is needed for Antarctica/Palmer & America/Santiago. */
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=2%s",
		 month + 1, WeekDays[day_weekday]);
      } else if (month != 1 && day_number == DaysInMonth[month] - 7) {
	/* Convert it to a BYDAY=-1SU type of RRULE. (But never for February.)
	   This is needed for America/Godthab. */
	sprintf (buffer, "RRULE:FREQ=YEARLY;BYMONTH=%i;BYDAY=-1%s",
		 month + 1, WeekDays[day_weekday]);
      } else {
	printf ("ERROR: %s: Couldn't modify RRULE to be compatible with Outlook (day >= %i, month = %i)\n", CurrentZoneName, day_number, month + 1);
	exit (1);
      }

    } else {
      sprintf (buffer,
	       "RRULE:FREQ=YEARLY;BYMONTH=%i;BYMONTHDAY=%i,%i,%i,%i,%i,%i,%i;BYDAY=%s",
	       month + 1,
	       day_number, day_number + 1, day_number + 2, day_number + 3,
	       day_number + 4, day_number + 5, day_number + 6,
	       WeekDays[day_weekday]);
    }
  }

  return TRUE;
}


static char*
format_vzictime				(VzicTime	*vzictime)
{
  static char buffer[1024];

  sprintf (buffer, "%s %2i %s %s %i %i %s",
	   dump_year (vzictime->year), vzictime->month + 1,
	   dump_day_coded (vzictime->day_code, vzictime->day_number,
			   vzictime->day_weekday),
	   dump_time (vzictime->time_seconds, vzictime->time_code, TRUE),
	   vzictime->stdoff, vzictime->walloff,
	   vzictime->is_infinite ? "INFINITE" : "");

  return buffer;
}


static void
dump_changes				(FILE		*fp,
					 char		*zone_name,
					 GArray		*changes)
{
  VzicTime *vzictime, *vzictime2 = NULL;
  int i, year_offset, year;

  for (i = 0; i < changes->len; i++) {
    vzictime = &g_array_index (changes, VzicTime, i);

    if (vzictime->year > MAX_CHANGES_YEAR)
      return;

    dump_change (fp, zone_name, vzictime, vzictime->year);
  }

  if (changes->len < 2)
    return;

  /* Now see if the changes array ends with a pair of recurring changes. */
  vzictime = &g_array_index (changes, VzicTime, changes->len - 2);
  vzictime2 = &g_array_index (changes, VzicTime, changes->len - 1);
  if (!vzictime->is_infinite || !vzictime2->is_infinite)
    return;

  year_offset = 1;
  for (;;) {
    year = vzictime->year + year_offset;
    if (year > MAX_CHANGES_YEAR)
      break;
    dump_change (fp, zone_name, vzictime, year);

    year = vzictime2->year + year_offset;
    if (year > MAX_CHANGES_YEAR)
      break;
    dump_change (fp, zone_name, vzictime2, year);

    year_offset++;
  }
}


static void
dump_change				(FILE		*fp,
					 char		*zone_name,
					 VzicTime	*vzictime,
					 int		 year)
{
  int hour, minute, second;
  VzicTime tmp_vzictime;
  static char *months[] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
			    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };

  /* Output format is:

	Zone-Name [tab] Date [tab] Time [tab] UTC-Offset

     The Date and Time fields specify the time change in UTC.

     The UTC Offset is for local (wall-clock) time. It is the amount of time
     to add to UTC to get local time.
  */

  fprintf (fp, "%s\t", zone_name);

  if (year == YEAR_MINIMUM) {
    fprintf (fp, " 1 Jan 0001\t 0:00:00", zone_name);
  } else if (year == YEAR_MAXIMUM) {
    fprintf (stderr, "Maximum year found in change time\n");
    exit (1);
  } else {
    tmp_vzictime = *vzictime;
    tmp_vzictime.year = year;
    calculate_actual_time (&tmp_vzictime, TIME_UNIVERSAL,
			   vzictime->prev_stdoff, vzictime->prev_walloff);

    hour = tmp_vzictime.time_seconds / 3600;
    minute = (tmp_vzictime.time_seconds % 3600) / 60;
    second = tmp_vzictime.time_seconds % 60;

    fprintf (fp, "%2i %s %04i\t%2i:%02i:%02i",
	     tmp_vzictime.day_number, months[tmp_vzictime.month],
	     tmp_vzictime.year, hour, minute, second);
  }

  fprintf (fp, "\t%s", format_tz_offset (vzictime->walloff, FALSE));

  fprintf (fp, "\n");
}


void
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
expand_tzid_prefix		(void)
{
  char *src, *dest;
  char date_buf[16];
  char ch1, ch2;
  time_t t;
  struct tm *tm;

  /* Get today's date as a string in the format "YYYYMMDD". */
  t = time (NULL);
  tm = localtime (&t);
  sprintf (date_buf, "%4i%02i%02i", tm->tm_year + 1900,
	   tm->tm_mon + 1, tm->tm_mday);

  src = TZIDPrefix;
  dest = TZIDPrefixExpanded;

  while (ch1 = *src++) {

    /* Look for a '%'. */
    if (ch1 == '%') {
      ch2 = *src++;

      if (ch2 == 'D') {
	/* '%D' gets expanded into the date string. */
	strcpy (dest, date_buf);
	dest += strlen (dest);
      } else if (ch2 == '%') {
	/* '%%' gets converted into one '%'. */
	*dest++ = '%';
      } else {
	/* Anything else is output as is. */
	*dest++ = '%';
	*dest++ = ch2;
      }
    } else {
      *dest++ = ch1;
    }
  }

#if 0
  printf ("TZID    : %s\n", TZIDPrefix);
  printf ("Expanded: %s\n", TZIDPrefixExpanded);
#endif
}
