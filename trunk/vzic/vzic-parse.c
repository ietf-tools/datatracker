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

#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <libgen.h>

#include "vzic.h"
#include "vzic-parse.h"

/* This is the maximum line length we allow. */
#define MAX_LINE_LEN	1024

/* The maximum number of fields on a line. */
#define MAX_FIELDS	12

#define CREATE_SYMLINK	1

typedef enum
{
  ZONE_ID		= 0,	/* The 'Zone' at the start of the line. */
  ZONE_NAME		= 1,
  ZONE_GMTOFF		= 2,
  ZONE_RULES_SAVE	= 3,
  ZONE_FORMAT		= 4,
  ZONE_UNTIL_YEAR	= 5,
  ZONE_UNTIL_MONTH	= 6,
  ZONE_UNTIL_DAY	= 7,
  ZONE_UNTIL_TIME	= 8
} ZoneFieldNumber;


typedef enum
{
  RULE_ID		= 0,	/* The 'Rule' at the start of the line. */
  RULE_NAME		= 1,
  RULE_FROM		= 2,
  RULE_TO		= 3,
  RULE_TYPE		= 4,
  RULE_IN		= 5,
  RULE_ON		= 6,
  RULE_AT		= 7,
  RULE_SAVE		= 8,
  RULE_LETTER_S		= 9
} RuleFieldNumber;


typedef enum
{
  LINK_ID		= 0,	/* The 'Link' at the start of the line. */
  LINK_FROM		= 1,
  LINK_TO		= 2
} LinkFieldNumber;


/* This struct contains information used while parsing the files, and is
   passed to most parsing functions. */
typedef struct _ParsingData ParsingData;
struct _ParsingData
{
  /* This is the line being parsed. buffer is a copy that we break into fields
     and sub-fields as it is parsed. */
  char	line[MAX_LINE_LEN];
  char	buffer[MAX_LINE_LEN];

  /* These are pointers to the start of each field in buffer. */
  char *fields[MAX_FIELDS];
  int	num_fields;

  /* These are just for producing error messages. */
  char *filename;
  int	line_number;


  /* This is an array of ZoneData structs, 1 for each timezone read. */
  GArray *zone_data;

  /* This is a hash table of arrays of RuleData structs. As each Rule line is
     read in, a new RuleData struct is filled in and appended to the
     appropriate GArray in the hash table. */
  GHashTable *rule_data;

  /* A hash containing data on the Link lines. The keys are the timezones
     where the link is from (i.e. the timezone we will be outputting anyway)
     and the data is a GList of timezones to link to (where we will copy the
     timezone data to). */
  GHashTable *link_data;

  int	max_until_year;
};


/*
 * Parsing functions, used when reading the Olson timezone data file.
 */
static void	parse_fields			(ParsingData	*data);
static gboolean	parse_zone_line			(ParsingData	*data);
static gboolean	parse_zone_continuation_line	(ParsingData	*data);
static gboolean parse_zone_common		(ParsingData	*data,
						 int		 offset);
static void	parse_rule_line			(ParsingData	*data);
static void	parse_link_line			(ParsingData	*data);

static int	parse_year			(ParsingData	*data,
						 char		*field,
						 gboolean	 accept_only,
						 int		 only_value);
static int	parse_month			(ParsingData	*data,
						 char		*field);
static DayCode	parse_day			(ParsingData	*data,
						 char		*field,
						 int		*day,
						 int		*weekday);
static int	parse_weekday			(ParsingData	*data,
						 char		*field);
static int	parse_time			(ParsingData	*data,
						 char		*field,
						 TimeCode	*time_code);
static int	parse_number			(ParsingData	*data,
						 char	       **num);
static int	parse_rules_save		(ParsingData	*data,
						 char		*field,
						 char	       **rules);

static void	parse_coord			(char		*coord,
						 int		 len,
						 int		*result);

void
parse_olson_file		(char		*filename,
				 GArray	       **zone_data,
				 GHashTable    **rule_data,
				 GHashTable    **link_data,
				 int		*max_until_year)
{
  ParsingData data;
  FILE *fp;
  int zone_continues = 0;

  *zone_data = g_array_new (FALSE, FALSE, sizeof (ZoneData));
  *rule_data = g_hash_table_new (g_str_hash, g_str_equal);
  *link_data = g_hash_table_new (g_str_hash, g_str_equal);

  fp = fopen (filename, "r");
  if (!fp) {
    fprintf (stderr, "Couldn't open file: %s\n", filename);
    exit (1);
  }

  data.filename = filename;
  data.zone_data = *zone_data;
  data.rule_data = *rule_data;
  data.link_data = *link_data;
  data.max_until_year = 0;

  for (data.line_number = 0; ; data.line_number++) {
    if (fgets (data.line, sizeof (data.line), fp) != data.line)
      break;

    strcpy (data.buffer, data.line);

    parse_fields (&data);
    if (data.num_fields == 0)
      continue;

    if (zone_continues) {
      zone_continues = parse_zone_continuation_line (&data);
    } else if (!strcmp (data.fields[0], "Zone")) {
      zone_continues = parse_zone_line (&data);
    } else if (!strcmp (data.fields[0], "Rule")) {
      parse_rule_line (&data);
    } else if (!strcmp (data.fields[0], "Link")) {
      parse_link_line (&data);
    } else if (!strcmp (data.fields[0], "Leap")) {
      /* We don't care about Leap lines. */
    } else {
      fprintf (stderr, "%s:%i: Invalid line.\n%s\n", filename,
	       data.line_number, data.line);
      exit (1);
    }
  }

  if (ferror (fp)) {
    fprintf (stderr, "Error reading file: %s\n", filename);
    exit (1);
  }

  if (zone_continues) {
    fprintf (stderr, "%s:%i: Zone continuation line expected.\n%s\n",
	     filename, data.line_number, data.line);
    exit (1);
  }

  fclose (fp);

#if 0
  printf ("Max UNTIL year: %i\n", data.max_until_year);
#endif
  *max_until_year = data.max_until_year;
}


/* Converts the line into fields. */
static void
parse_fields			(ParsingData	*data)
{
  int i;
  char *p, *s, ch;

  /* Reset all fields to NULL. */
  for (i = 0; i < MAX_FIELDS; i++)
    data->fields[i] = 0;

  data->num_fields = 0;
  p = data->buffer;

  for (;;) {
    /* Skip whitespace. */
    while (isspace (*p))
      p++;

    /* See if we have reached the end of the line or a comment. */
    if (*p == '\0' || *p == '#')
      break;

    /* We must have another field, so save the start position. */
    data->fields[data->num_fields++] = p;

    /* Now find the end of the field. If the field contains '"' characters
       they are removed and we have to move the rest of the chars back. */
    s = p;
    for (;;) {
      ch = *p;
      if (ch == '\0' || ch == '#') {
	/* Don't move p on since this is the end of the line. */
	*s = '\0';
	break;
      } else if (isspace (ch)) {
	*s = '\0';
	p++;
	break;
      } else if (ch == '"') {
	p++;
	for (;;) {
	  ch = *p;
	  if (ch == '\0') {
	    fprintf (stderr,
		     "%s:%i: Closing quote character ('\"') missing.\n%s\n",
		     data->filename, data->line_number, data->line);
	    exit (1);
	  } else if (ch == '"') {
	    p++;
	    break;
	  } else {
	    *s++ = ch;
	  }
	  p++;
	}	  
      } else {
	*s++ = ch;
      }
      p++;
    }
  }

#if 0
  printf ("%i fields: ", data->num_fields);
  for (i = 0; i < data->num_fields; i++)
    printf ("'%s' ", data->fields[i]);
  printf ("\n");
#endif
}


static gboolean
parse_zone_line			(ParsingData	*data)
{
  ZoneData zone;

  /* All 5 fields up to FORMAT must be present. */
  if (data->num_fields < 5 || data->num_fields > 9) {
	fprintf (stderr, "%s:%i: Invalid Zone line - %i fields.\n%s\n",
		 data->filename, data->line_number, data->num_fields,
		 data->line);
	exit (1);
  }

  zone.zone_name = g_strdup (data->fields[ZONE_NAME]);
  zone.zone_line_data = g_array_new (FALSE, FALSE, sizeof (ZoneLineData));

  g_array_append_val (data->zone_data, zone);

  return parse_zone_common (data, 0);
}


static gboolean
parse_zone_continuation_line	(ParsingData	*data)
{
  /* All 3 fields up to FORMAT must be present. */
  if (data->num_fields < 3 || data->num_fields > 7) {
	fprintf (stderr,
		 "%s:%i: Invalid Zone continuation line - %i fields.\n%s\n",
		 data->filename, data->line_number, data->num_fields,
		 data->line);
	exit (1);
  }

  return parse_zone_common (data, -2);
}


static gboolean
parse_zone_common		(ParsingData	*data,
				 int		 offset)
{
  ZoneData *zone;
  ZoneLineData zone_line;
  TimeCode time_code;

  zone_line.stdoff_seconds = parse_time (data,
					 data->fields[ZONE_GMTOFF + offset],
					 &time_code);
  zone_line.save_seconds = parse_rules_save (data,
					     data->fields[ZONE_RULES_SAVE + offset],
					     &zone_line.rules);

  if (!VzicPureOutput) {
    /* We round the UTC offsets to the nearest minute, to be compatible with
       Outlook. This also works with -ve numbers, I think.
       -56 % 60 = -59. -61 % 60 = -1. */
    if (zone_line.stdoff_seconds >= 0)
      zone_line.stdoff_seconds += 30;
    else
      zone_line.stdoff_seconds -= 29;
    zone_line.stdoff_seconds -= zone_line.stdoff_seconds % 60;

    if (zone_line.save_seconds >= 0)
      zone_line.save_seconds += 30;
    else
      zone_line.save_seconds -= 29;
    zone_line.save_seconds -= zone_line.save_seconds % 60;
  }

  zone_line.format = g_strdup (data->fields[ZONE_FORMAT + offset]);

  if (data->num_fields - offset >= 6) {
    zone_line.until_set = TRUE;
    zone_line.until_year = parse_year (data,
				       data->fields[ZONE_UNTIL_YEAR + offset],
				       FALSE, 0);
    zone_line.until_month = parse_month (data,
					 data->fields[ZONE_UNTIL_MONTH + offset]);
    zone_line.until_day_code = parse_day (data,
					  data->fields[ZONE_UNTIL_DAY + offset],
					  &zone_line.until_day_number,
					  &zone_line.until_day_weekday);
    zone_line.until_time_seconds = parse_time (data,
					       data->fields[ZONE_UNTIL_TIME + offset],
					       &zone_line.until_time_code);

    /* We also want to know the maximum year used in any UNTIL value, so we
       know where to expand all the infinite Rule data to. */
    if (zone_line.until_year != YEAR_MAXIMUM
	&& zone_line.until_year != YEAR_MINIMUM)
      data->max_until_year = MAX (data->max_until_year, zone_line.until_year);

  } else {
    zone_line.until_set = FALSE;
  }

  /* Append it to the last Zone, since that is the one we are currently
     reading. */
  zone = &g_array_index (data->zone_data, ZoneData, data->zone_data->len - 1);
  g_array_append_val (zone->zone_line_data, zone_line);

  return zone_line.until_set;
}


static void
parse_rule_line			(ParsingData	*data)
{
  GArray *rule_array;
  RuleData rule;
  char *name;
  TimeCode time_code;

  /* All 10 fields must be present. */
  if (data->num_fields != 10) {
	fprintf (stderr, "%s:%i: Invalid Rule line - %i fields.\n%s\n",
		 data->filename, data->line_number, data->num_fields,
		 data->line);
	exit (1);
  }

  name = data->fields[RULE_NAME];

  /* Create the GArray and add it to the hash table if it doesn't already
     exist. */
  rule_array = g_hash_table_lookup (data->rule_data, name);
  if (!rule_array) {
    rule_array = g_array_new (FALSE, FALSE, sizeof (RuleData));
    g_hash_table_insert (data->rule_data, g_strdup (name), rule_array);
  }

  rule.from_year = parse_year (data, data->fields[RULE_FROM], FALSE, 0);
  if (rule.from_year == YEAR_MAXIMUM) {
    fprintf (stderr, "%s:%i: Invalid Rule FROM value: '%s'\n",
	     data->filename, data->line_number, data->fields[RULE_FROM]);
    exit (1);
  }

  rule.to_year = parse_year (data, data->fields[RULE_TO], TRUE,
			     rule.from_year);
  if (rule.to_year == YEAR_MINIMUM) {
    fprintf (stderr, "%s:%i: Invalid Rule TO value: %s\n",
	     data->filename, data->line_number, data->fields[RULE_TO]);
    exit (1);
  }

  if (!strcmp (data->fields[RULE_TYPE], "-"))
    rule.type = NULL;
  else {
    printf ("Type: %s\n", data->fields[RULE_TYPE]);
    rule.type = g_strdup (data->fields[RULE_TYPE]);
  }

  rule.in_month = parse_month (data, data->fields[RULE_IN]);
  rule.on_day_code = parse_day (data, data->fields[RULE_ON],
				&rule.on_day_number, &rule.on_day_weekday);
  rule.at_time_seconds = parse_time (data, data->fields[RULE_AT],
				     &rule.at_time_code);
  rule.save_seconds = parse_time (data, data->fields[RULE_SAVE], &time_code);

  if (!strcmp (data->fields[RULE_LETTER_S], "-")) {
    rule.letter_s = NULL;
  } else {
    rule.letter_s = g_strdup (data->fields[RULE_LETTER_S]);
  }

  rule.is_shallow_copy = FALSE;

  g_array_append_val (rule_array, rule);
}


static void
parse_link_line			(ParsingData	*data)
{
  char *from, *to, *old_from;
  GList *zone_list;

  /* We must have 3 fields for a Link. */
  if (data->num_fields != 3) {
	fprintf (stderr, "%s:%i: Invalid Rule line - %i fields.\n%s\n",
		 data->filename, data->line_number, data->num_fields,
		 data->line);
	exit (1);
  }

  from = data->fields[LINK_FROM];
  to = data->fields[LINK_TO];

#if 0
  printf ("LINK FROM: %s\tTO: %s\n", from, to);
#endif

#if CREATE_SYMLINK
  {
      int len = strnlen(to,254);
      int dirs = 0;
      int i;
      for (i = 0; i < len; i++) {
	  dirs += to[i] == '/' ? 1 : 0;
      }
      if (dirs) {
	  char rel_from[255];
	  char to_dir[255];
	  char to_path[255];
	  if (dirs == 1) {
	      sprintf(rel_from, "../%s.ics", from);	  
	  } else if (dirs == 2) {
	      sprintf(rel_from, "../../%s.ics", from);
	  } else {
	      return;
	  }
	  sprintf(to_path, "%s/%s.ics", VzicOutputDir, to);
	  strncpy(to_dir, to_path, 254);
	  ensure_directory_exists(dirname(to_dir));
	  //printf("Creating symlink from %s to %s\n", rel_from, to_path);
	  symlink(rel_from, to_path);
      }
  }
#else

  if (g_hash_table_lookup_extended (data->link_data, from,
				    (gpointer) &old_from,
				    (gpointer) &zone_list)) {
    from = old_from;
  } else {
    from = g_strdup (from);
    zone_list = NULL;
  }

  zone_list = g_list_prepend (zone_list, g_strdup (to));

  g_hash_table_insert (data->link_data, from, zone_list);
#endif
}


static int
parse_year			(ParsingData	*data,
				 char		*field,
				 gboolean	 accept_only,
				 int		 only_value)
{
  int len, year = 0;
  char *p;

  if (!field) {
    fprintf (stderr, "%s:%i: Missing year.\n%s\n", data->filename,
	     data->line_number, data->line);
    exit (1);
  }

  len = strlen (field);
  if (accept_only && !strncmp (field, "only", len))
    return only_value;
  if (len >= 2) {
    if (!strncmp (field, "maximum", len))
      return YEAR_MAXIMUM;
    else if (!strncmp (field, "minimum", len))
      return YEAR_MINIMUM;
  }

  for (p = field; *p; p++) {
    if (*p < '0' || *p > '9') {
	fprintf (stderr, "%s:%i: Invalid year: %s\n%s\n", data->filename,
		 data->line_number, field, data->line);
	exit (1);
    }

    year = year * 10 + *p - '0';
  }

  if (year < 1000 || year > 2038) {
	fprintf (stderr, "%s:%i: Strange year: %s\n%s\n", data->filename,
		 data->line_number, field, data->line);
	exit (1);
  }

  return year;
}


/* Parses a month name, returning 0 (Jan) to 11 (Dec). */
static int
parse_month			(ParsingData	*data,
				 char		*field)
{
  static char* months[] = { "january", "february", "march", "april", "may",
			    "june", "july", "august", "september", "october",
			    "november", "december" };
  char *p;
  int len, i;

  /* If the field is missing, it must be the optional UNTIL month, so we return
     0 for January. */
  if (!field)
    return 0;

  for (p = field, len = 0; *p; p++, len++) {
    *p = tolower (*p);
  }

  for (i = 0; i < 12; i++) {
    if (!strncmp (field, months[i], len))
      return i;
  }

  fprintf (stderr, "%s:%i: Invalid month: %s\n%s\n", data->filename,
	   data->line_number, field, data->line);
  exit (1);
}


/* Parses a day specifier, returning a code representing the type of match
   together with a day of the month and a weekday number (0=Sun). */
static DayCode
parse_day			(ParsingData	*data,
				 char		*field,
				 int		*day,
				 int		*weekday)
{
  char *day_part, *p;
  DayCode day_code;

  if (!field) {
    *day = 1;
    return DAY_SIMPLE;
  }

  *day = *weekday = 0;

  if (!strncmp (field, "last", 4)) {
    *weekday = parse_weekday (data, field + 4);
    /* We set the day to the end of the month to make sorting Rules easy. */
    *day = 31;
    return DAY_LAST_WEEKDAY;
  }

  day_part = field;
  day_code = DAY_SIMPLE;

  for (p = field; *p; p++) {
    if (*p == '<' || *p == '>') {
      if (*(p + 1) == '=') {
	day_code = (*p == '<') ? DAY_WEEKDAY_ON_OR_BEFORE
	  : DAY_WEEKDAY_ON_OR_AFTER;
	*p = '\0';
	*weekday = parse_weekday (data, field);
	day_part = p + 2;
	break;
      }
      
      fprintf (stderr, "%s:%i: Invalid day: %s\n%s\n", data->filename,
	       data->line_number, field, data->line);
      exit (1);
    }
  }

  for (p = day_part; *p; p++) {
    if (*p < '0' || *p > '9') {
	fprintf (stderr, "%s:%i: Invalid day: %s\n%s\n", data->filename,
		 data->line_number, field, data->line);
	exit (1);
    }

    *day = *day * 10 + *p - '0';
  }

  if (*day < 1 || *day > 31) {
    fprintf (stderr, "%s:%i: Invalid day: %s\n%s\n", data->filename,
	     data->line_number, field, data->line);
    exit (1);
  }

  return day_code;
}


/* Parses a weekday name, returning 0 (Sun) to 6 (Sat). */
static int
parse_weekday			(ParsingData	*data,
				 char		*field)
{
  static char* weekdays[] = { "sunday", "monday", "tuesday", "wednesday",
			      "thursday", "friday", "saturday" };
  char *p;
  int len, i;

  for (p = field, len = 0; *p; p++, len++) {
    *p = tolower (*p);
  }

  for (i = 0; i < 7; i++) {
    if (!strncmp (field, weekdays[i], len))
      return i;
  }

  fprintf (stderr, "%s:%i: Invalid weekday: %s\n%s\n", data->filename,
	   data->line_number, field, data->line);
  exit (1);
}


/* Parses a time (hour + minute + second) and returns the result in seconds,
   together with a time code specifying whether it is Wall clock time,
   local standard time, or universal time.
   The time can start with a '-' in which case it will be negative. */
static int
parse_time			(ParsingData	*data,
				 char		*field,
				 TimeCode	*time_code)
{
  char *p;
  int hours = 0, minutes = 0, seconds = 0, result, negative = 0;

  if (!field) {
    *time_code = TIME_WALL;
    return 0;
  }

  p = field;
  if (*p == '-') {
    p++;
    negative = 1;
  }

  hours = parse_number (data, &p);

  if (*p == ':') {
    p++;
    minutes = parse_number (data, &p);

    if (*p == ':') {
      p++;
      seconds = parse_number (data, &p);
    }
  }

  if (hours < 0 || hours > 24
      || minutes < 0 || minutes > 59
      || seconds < 0 || seconds > 59
      || (hours == 24 && (minutes != 0 || seconds != 0))) {
    fprintf (stderr, "%s:%i: Invalid time: %s\n%s\n", data->filename,
	     data->line_number, field, data->line);
    exit (1);
  }

  if (hours == 24) {
    hours = 23;
    minutes = 59;
    seconds = 59;
  }

#if 0
  printf ("Time: %s -> %i:%02i:%02i\n", field, hours, minutes, seconds);
#endif

  result = hours * 3600 + minutes * 60 + seconds;
  if (negative)
    result = -result;

  if (*p == '\0') {
    *time_code = TIME_WALL;
    return result;
  }

  if (*(p + 1) == '\0') {
    if (*p == 'w') {
      *time_code = TIME_WALL;
      return result;
    } else if (*p == 's') {
      *time_code = TIME_STANDARD;
      return result;
    } else if (*p == 'u' || *p == 'g' || *p == 'z') {
      *time_code = TIME_UNIVERSAL;
      return result;
    }
  }

  fprintf (stderr, "%s:%i: Invalid time: %s\n%s\n", data->filename,
	   data->line_number, field, data->line);
  exit (1);
}


/* Parses a simple number and returns the result. The pointer argument
   is moved to the first character after the number. */
static int
parse_number			(ParsingData	*data,
				 char	       **num)
{
  char *p;
  int result;

  p = *num;

#if 0
  printf ("In parse_number p:%s\n", p);
#endif

  if (*p < '0' || *p > '9') {
    fprintf (stderr, "%s:%i: Invalid number: %s\n%s\n", data->filename,
	     data->line_number, *num, data->line);
    exit (1);
  }

  result = *p++ - '0';

  while (*p >= '0' && *p <= '9')
    result = result * 10 + *p++ - '0';

  *num = p;
  return result;
}


static int
parse_rules_save		(ParsingData	*data,
				 char		*field,
				 char	       **rules)
{
  TimeCode time_code;

  *rules = NULL;

  /* Check for just "-". */
  if (field[0] == '-' && field[1] == '\0')
    return 0;

  /* Check for a time to add to local standard time. We don't care about a
     time code here, since it is just an offset. */
  if (*field == '-' || (*field >= '0' && *field <= '9'))
    return parse_time (data, field, &time_code);

  /* It must be a rules name. */
  *rules = g_strdup (field);
  return 0;
}





GHashTable*
parse_zone_tab			(char		*filename)
{
  GHashTable *zones_hash;
  ZoneDescription *zone_desc;
  FILE *fp;
  char buf[4096];
  gchar **fields, *zone_name, *latitude, *longitude, *p;


  fp = fopen (filename, "r");
  if (!fp) {
    fprintf (stderr, "Couldn't open file: %s\n", filename);
    exit (1);
  }

  zones_hash = g_hash_table_new (g_str_hash, g_str_equal);

  while (fgets (buf, sizeof(buf), fp)) {
    if (*buf == '#') continue;

    g_strchomp (buf);
    fields = g_strsplit (buf,"\t", 4);

    if (strlen (fields[0]) != 2) {
      fprintf (stderr, "Invalid zone description line: %s\n", buf);
      exit (1);
    }

    zone_name = g_strdup (fields[2]);

    zone_desc = g_new (ZoneDescription, 1);
    zone_desc->country_code[0] = fields[0][0];
    zone_desc->country_code[1] = fields[0][1];
    zone_desc->comment = (fields[3] && fields[3][0]) ? g_strdup (fields[3])
      : NULL;

    /* Now parse the latitude and longitude. */
    latitude = fields[1];
    longitude = latitude + 1;
    while (*longitude != '+' && *longitude != '-')
      longitude++;

    parse_coord (latitude, longitude - latitude, zone_desc->latitude);
    parse_coord (longitude, strlen (longitude), zone_desc->longitude);

    g_hash_table_insert (zones_hash, zone_name, zone_desc);

#if 0
    g_print ("Found zone: %s %i %02i %02i,%i %02i %02i\n", zone_name,
	     zone_desc->latitude[0], zone_desc->latitude[1],
	     zone_desc->latitude[2],
	     zone_desc->longitude[0], zone_desc->longitude[1],
	     zone_desc->longitude[2]);
#endif
  }

  fclose (fp);

  return zones_hash;
}


static void
parse_coord			(char		*coord,
				 int		 len,
				 int		*result)
{
  int degrees = 0, minutes = 0, seconds = 0;

  if (len == 5)
    sscanf (coord + 1, "%2d%2d", &degrees, &minutes);
  else if (len == 6)
    sscanf (coord + 1, "%3d%2d", &degrees, &minutes);
  else if (len == 7)
    sscanf (coord + 1, "%2d%2d%2d", &degrees, &minutes, &seconds);
  else if (len == 8)
    sscanf (coord + 1, "%3d%2d%2d", &degrees, &minutes, &seconds);
  else {
    fprintf (stderr, "Invalid coordinate: %s\n", coord);
    exit (1);
  }

  if (coord[0] == '-')
    degrees = -degrees;

  result[0] = degrees;
  result[1] = minutes;
  result[2] = seconds;
}

