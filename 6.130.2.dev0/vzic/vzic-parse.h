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

#ifndef _VZIC_PARSE_H_
#define _VZIC_PARSE_H_

#include <glib.h>

void		parse_olson_file		(char		*filename,
						 GArray	       **zone_data,
						 GHashTable    **rule_data,
						 GHashTable    **link_data,
						 int		*max_until_year);

GHashTable*	parse_zone_tab			(char		*filename);

#endif /* _VZIC_PARSE_H_ */
