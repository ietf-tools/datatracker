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

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "vzic.h"
#include "vzic-parse.h"
#include "vzic-dump.h"
#include "vzic-output.h"


/*
 * Global command-line options.
 */

/* By default we output Outlook-compatible output. If --pure is used we
   output pure output, with no changes to be compatible with Outlook. */
gboolean VzicPureOutput			= FALSE;

gboolean VzicDumpOutput			= FALSE;
gboolean VzicDumpChanges		= FALSE;
gboolean VzicDumpZoneNamesAndCoords	= TRUE;
gboolean VzicDumpZoneTranslatableStrings= TRUE;
gboolean VzicNoRRules			= FALSE;
gboolean VzicNoRDates			= FALSE;
char*    VzicOutputDir			= "zoneinfo";
char*    VzicUrlPrefix                  = NULL;
char*    VzicOlsonDir                   = OLSON_DIR;

GList*	 VzicTimeZoneNames		= NULL;

static void	convert_olson_file		(char		*olson_file);

static void	usage				(void);

static void	free_zone_data			(GArray		*zone_data);
static void	free_rule_array			(gpointer	 key,
						 gpointer	 value,
						 gpointer	 data);
static void	free_link_data			(gpointer	 key,
						 gpointer	 value,
						 gpointer	 data);


int
main				(int		 argc,
				 char		*argv[])
{
  int i;
  char directory[PATHNAME_BUFFER_SIZE];
  char filename[PATHNAME_BUFFER_SIZE];
  GHashTable *zones_hash;

  /*
   * Command-Line Option Parsing.
   */
  for (i = 1; i < argc; i++) {
    /*
     * User Options.
     */

    /* --pure: Output the perfect VCALENDAR data, which Outlook won't parse
       as it has problems with certain iCalendar constructs. */
    if (!strcmp (argv[i], "--pure"))
      VzicPureOutput = TRUE;

    /* --output-dir: specify where to output all the files beneath. The
       default is the current directory. */
    else if (argc > i + 1 && !strcmp (argv[i], "--output-dir"))
      VzicOutputDir = argv[++i];

    /* --url-prefix: Used as the base for the TZURL property in each
       VTIMEZONE. The default is to not output TZURL properties. */
    else if (argc > i + 1 && !strcmp (argv[i], "--url-prefix")) {
      int length;
      VzicUrlPrefix = argv[++i];
      /* remove the trailing '/' if there is one */
      length = strlen (VzicUrlPrefix);
      if (VzicUrlPrefix[length - 1] == '/')
          VzicUrlPrefix[length - 1] = '\0';
    }

    else if (argc > i + 1 && !strcmp (argv[i], "--olson-dir")) {
      VzicOlsonDir = argv[++i];
    }

    /*
     * Debugging Options.
     */

    /* --dump: Dump the Rule and Zone data that we parsed from the Olson
       timezone files. This is used to test the parsing code. */
    else if (!strcmp (argv[i], "--dump"))
      VzicDumpOutput = TRUE;

    /* --dump-changes: Dumps a list of times when each timezone changed,
       and the new local time offset from UTC. */
    else if (!strcmp (argv[i], "--dump-changes"))
      VzicDumpChanges = TRUE;

    /* --no-rrules: Don't output RRULE properties in the VTIMEZONEs. Instead
       it will just output RDATEs for each year up to a certain year. */
    else if (!strcmp (argv[i], "--no-rrules"))
      VzicNoRRules = TRUE;

    /* --no-rdates: Don't output multiple RDATEs in a single VTIMEZONE
       component. Instead they will be output separately. */
    else if (!strcmp (argv[i], "--no-rdates"))
      VzicNoRDates = TRUE;

    else
      usage ();
  }

  /*
   * Create any necessary directories.
   */
  ensure_directory_exists (VzicOutputDir);

  if (VzicDumpOutput) {
    /* Create the directories for the dump output, if they don't exist. */
    sprintf (directory, "%s/ZonesVzic", VzicOutputDir);
    ensure_directory_exists (directory);
    sprintf (directory, "%s/RulesVzic", VzicOutputDir);
    ensure_directory_exists (directory);
  }

  if (VzicDumpChanges) {
    /* Create the directory for the changes output, if it doesn't exist. */
    sprintf (directory, "%s/ChangesVzic", VzicOutputDir);
    ensure_directory_exists (directory);
  }

  /*
   * Convert the Olson timezone files.
   */
  convert_olson_file ("africa");
  convert_olson_file ("antarctica");
  convert_olson_file ("asia");
  convert_olson_file ("australasia");
  convert_olson_file ("europe");
  convert_olson_file ("northamerica");
  convert_olson_file ("southamerica");

  /* These are backwards-compatability and weird stuff. */
#if 0
  convert_olson_file ("backward");
  convert_olson_file ("etcetera");
  convert_olson_file ("leapseconds");
  convert_olson_file ("pacificnew");
  convert_olson_file ("solar87");
  convert_olson_file ("solar88");
  convert_olson_file ("solar89");
#endif

  /* This doesn't really do anything and it messes up vzic-dump.pl so we
     don't bother. */
#if 0
  convert_olson_file ("factory");
#endif

  /* This is old System V stuff, which we don't currently support since it
     uses 'min' as a Rule FROM value which messes up our algorithm, making
     it too slow and use too much memory. */
#if 0
  convert_olson_file ("systemv");
#endif

  /* Output the timezone names and coordinates in a zone.tab file, and
     the translatable strings to feed to gettext. */
  if (VzicDumpZoneNamesAndCoords) {
    sprintf (filename, "%s/zone.tab", VzicOlsonDir);
    zones_hash = parse_zone_tab (filename);

    dump_time_zone_names (VzicTimeZoneNames, VzicOutputDir, zones_hash);
  }

  return 0;
}


static void
convert_olson_file		(char		*olson_file)
{
  char input_filename[PATHNAME_BUFFER_SIZE];
  GArray *zone_data;
  GHashTable *rule_data, *link_data;
  char dump_filename[PATHNAME_BUFFER_SIZE];
  ZoneData *zone;
  int i, max_until_year;

  sprintf (input_filename, "%s/%s", VzicOlsonDir, olson_file);

  parse_olson_file (input_filename, &zone_data, &rule_data, &link_data,
		    &max_until_year);

  if (VzicDumpOutput) {
    sprintf (dump_filename, "%s/ZonesVzic/%s", VzicOutputDir, olson_file);
    dump_zone_data (zone_data, dump_filename);

    sprintf (dump_filename, "%s/RulesVzic/%s", VzicOutputDir, olson_file);
    dump_rule_data (rule_data, dump_filename);
  }

  output_vtimezone_files (VzicOutputDir, zone_data, rule_data, link_data,
			  max_until_year);

  free_zone_data (zone_data);
  g_hash_table_foreach (rule_data, free_rule_array, NULL);
  g_hash_table_destroy (rule_data);
  g_hash_table_foreach (link_data, free_link_data, NULL);
  g_hash_table_destroy (link_data);
}


static void
usage				(void)
{
  fprintf (stderr, "Usage: vzic [--dump] [--dump-changes] [--no-rrules] [--no-rdates] [--pure] [--output-dir <directory>] [--url-prefix <url>] [--olson-dir <directory>]\n");

  exit (1);
}




/*
 * Functions to free the data structures.
 */

static void
free_zone_data			(GArray		*zone_data)
{
  ZoneData *zone;
  ZoneLineData *zone_line;
  int i, j;

  for (i = 0; i < zone_data->len; i++) {
    zone = &g_array_index (zone_data, ZoneData, i);

    g_free (zone->zone_name);

    for (j = 0; j < zone->zone_line_data->len; j++) {
      zone_line = &g_array_index (zone->zone_line_data, ZoneLineData, j);

      g_free (zone_line->rules);
      g_free (zone_line->format);
    }

    g_array_free (zone->zone_line_data, TRUE);
  }

  g_array_free (zone_data, TRUE);
}


static void
free_rule_array			(gpointer	 key,
				 gpointer	 value,
				 gpointer	 data)
{
  char *name = key;
  GArray *rule_array = value;
  RuleData *rule;
  int i;

  for (i = 0; i < rule_array->len; i++) {
    rule = &g_array_index (rule_array, RuleData, i);

    if (!rule->is_shallow_copy) {
      g_free (rule->type);
      g_free (rule->letter_s);
    }
  }

  g_array_free (rule_array, TRUE);

  g_free (name);
}


static void
free_link_data			(gpointer	 key,
				 gpointer	 value,
				 gpointer	 data)
{
  GList *link = data;

  g_free (key);

  while (link) {
    g_free (link->data);
    link = link->next;
  }

  g_list_free (data);
}

