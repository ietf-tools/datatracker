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
 * These functions are for dumping all the parsed Zones and Rules to
 * files, to be compared with the output of vzic-dump.pl to check our parsing
 * code is OK. Some of the functions are also used for producing debugging
 * output.
 */

#ifndef _VZIC_DUMP_H_
#define _VZIC_DUMP_H_

#include <glib.h>

void		dump_zone_data			(GArray		*zone_data,
						 char		*filename);
void		dump_rule_data			(GHashTable	*rule_data,
						 char		*filename);

void		dump_rule_array			(char		*name,
						 GArray		*rule_array,
						 FILE		*fp);

char*		dump_year			(int		year);
char*		dump_day_coded			(DayCode	day_code,
						 int		day_number,
						 int		day_weekday);
char*		dump_time			(int		 seconds,
						 TimeCode	 time_code,
						 gboolean	 use_zero);

void		dump_time_zone_names		(GList		*names,
						 char		*output_dir,
						 GHashTable	*zones_hash);

#endif /* _VZIC_DUMP_H_ */
