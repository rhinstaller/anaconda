/* -*- Mode: C; tab-width: 8; indent-tabs-mode: t; c-basic-offset: 8 -*- */
/* Generic timezone utilities.
 *
 * Copyright (C) 2000-2001 Ximian, Inc.
 *
 * Authors: Hans Petter Jansson <hpj@ximian.com>
 * 
 * Largely based on Michael Fulbright's work on Anaconda.
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


#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <math.h>
#include <string.h>
#include "tz.h"


/* Forward declarations for private functions */

static float convert_pos (gchar *pos, int digits);
static int compare_country_names (const void *a, const void *b);
static void sort_locations_by_country (GPtrArray *locations);
static gchar * tz_data_file_get (void);
static void load_backward_tz (TzDB *tz_db);

/* Returns path to anaconda widgets data directory using the value of the
 * environment variable ANACONDA_WIDGETS_DATA or WIDGETS_DATADIR macro
 * (defined in Makefile.am) if the environment variable is not defined.
 */
gchar *get_widgets_datadir() {
    gchar *env_value;

    env_value = getenv("ANACONDA_WIDGETS_DATA");
    if (env_value == NULL)
        return WIDGETS_DATADIR;
    else
        return env_value;
}

/* ---------------- *
 * Public interface *
 * ---------------- */
TzDB *
tz_load_db (void)
{
	gchar *tz_data_file;
	TzDB *tz_db;
	FILE *tzfile;
	char buf[4096];

	tz_data_file = tz_data_file_get ();
	if (!tz_data_file) {
		g_warning ("Could not get the TimeZone data file name");
		return NULL;
	}
	tzfile = fopen (tz_data_file, "r");
	if (!tzfile) {
		g_warning ("Could not open *%s*\n", tz_data_file);
		g_free (tz_data_file);
		return NULL;
	}

	tz_db = g_new0 (TzDB, 1);
	tz_db->locations = g_ptr_array_new ();

	while (fgets (buf, sizeof(buf), tzfile)) {
		gchar **tmpstrarr;
		gchar *latstr, *lngstr, *p;
		TzLocation *loc;

		if (*buf == '#') continue;

		g_strchomp(buf);
		tmpstrarr = g_strsplit(buf,"\t", 6);
		
		latstr = g_strdup (tmpstrarr[1]);
		p = latstr + 1;
		while (*p != '-' && *p != '+') p++;
		lngstr = g_strdup (p);
		*p = '\0';
		
		loc = g_new0 (TzLocation, 1);
		loc->country = g_strdup (tmpstrarr[0]);
		loc->zone = g_strdup (tmpstrarr[2]);
		loc->latitude  = convert_pos (latstr, 2);
		loc->longitude = convert_pos (lngstr, 3);
		
		loc->comment = (tmpstrarr[3]) ? g_strdup(tmpstrarr[3]) : NULL;

		g_ptr_array_add (tz_db->locations, (gpointer) loc);

		g_free (latstr);
		g_free (lngstr);
		g_strfreev (tmpstrarr);
	}
	
	fclose (tzfile);
	
	/* now sort by country */
	sort_locations_by_country (tz_db->locations);
	
	g_free (tz_data_file);

	/* Load up the hashtable of backward links */
	load_backward_tz (tz_db);

	return tz_db;
}

static void
tz_location_free (TzLocation *loc)
{
	g_free (loc->country);
	g_free (loc->zone);
	g_free (loc->comment);

	g_free (loc);
}

void
tz_db_free (TzDB *db)
{
	g_ptr_array_foreach (db->locations, (GFunc) tz_location_free, NULL);
	g_ptr_array_free (db->locations, TRUE);
	g_hash_table_destroy (db->backward);
	g_free (db);
}

GPtrArray *
tz_get_locations (TzDB *db)
{
	return db->locations;
}


gchar *
tz_location_get_country (TzLocation *loc)
{
	return loc->country;
}


gchar *
tz_location_get_zone (TzLocation *loc)
{
	return loc->zone;
}


gchar *
tz_location_get_comment (TzLocation *loc)
{
	return loc->comment;
}


void
tz_location_get_position (TzLocation *loc, double *longitude, double *latitude)
{
	*longitude = loc->longitude;
	*latitude = loc->latitude;
}

glong
tz_location_get_utc_offset (TzLocation *loc)
{
	TzInfo *tz_info;
	glong offset;

	tz_info = tz_info_from_location (loc);
	offset = tz_info->utc_offset;
	tz_info_free (tz_info);
	return offset;
}

TzInfo *
tz_info_from_location (TzLocation *loc)
{
	TzInfo *tzinfo;
	time_t curtime;
	struct tm *curzone;
	gchar *tz_env_value;
	
	g_return_val_if_fail (loc != NULL, NULL);
	g_return_val_if_fail (loc->zone != NULL, NULL);
	
	tz_env_value = g_strdup (getenv ("TZ"));
	setenv ("TZ", loc->zone, 1);
	
	tzinfo = g_new0 (TzInfo, 1);

	curtime = time (NULL);
	curzone = localtime (&curtime);

	/* Currently this solution doesnt seem to work - I get that */
	/* America/Phoenix uses daylight savings, which is wrong    */
	tzinfo->tzname_normal = g_strdup (curzone->tm_zone);
	if (curzone->tm_isdst) 
		tzinfo->tzname_daylight =
			g_strdup (&curzone->tm_zone[curzone->tm_isdst]);
	else
		tzinfo->tzname_daylight = NULL;

	tzinfo->utc_offset = curzone->tm_gmtoff;

	tzinfo->daylight = curzone->tm_isdst;

	if (tz_env_value)
		setenv ("TZ", tz_env_value, 1);
	else
		unsetenv ("TZ");

	g_free (tz_env_value);
	
	return tzinfo;
}


void
tz_info_free (TzInfo *tzinfo)
{
	g_return_if_fail (tzinfo != NULL);
	
	if (tzinfo->tzname_normal) g_free (tzinfo->tzname_normal);
	if (tzinfo->tzname_daylight) g_free (tzinfo->tzname_daylight);
	g_free (tzinfo);
}

struct {
	const char *orig;
	const char *dest;
} aliases[] = {
	{ "Asia/Istanbul",  "Europe/Istanbul" },	/* Istanbul is in both Europe and Asia */
	{ "Europe/Nicosia", "Asia/Nicosia" },		/* Ditto */
	{ "EET",            "Europe/Istanbul" },	/* Same tz as the 2 above */
	{ "HST",            "Pacific/Honolulu" },
	{ "WET",            "Europe/Brussels" },	/* Other name for the mainland Europe tz */
	{ "CET",            "Europe/Brussels" },	/* ditto */
	{ "MET",            "Europe/Brussels" },
	{ "Etc/Zulu",       "Etc/GMT" },
	{ "Etc/UTC",        "Etc/GMT" },
	{ "GMT",            "Etc/GMT" },
	{ "Greenwich",      "Etc/GMT" },
	{ "Etc/UCT",        "Etc/GMT" },
	{ "Etc/GMT0",       "Etc/GMT" },
	{ "Etc/GMT+0",      "Etc/GMT" },
	{ "Etc/GMT-0",      "Etc/GMT" },
	{ "Etc/Universal",  "Etc/GMT" },
	{ "PST8PDT",        "America/Los_Angeles" },	/* Other name for the Atlantic tz */
	{ "EST",            "America/New_York" },	/* Other name for the Eastern tz */
	{ "EST5EDT",        "America/New_York" },	/* ditto */
	{ "CST6CDT",        "America/Chicago" },	/* Other name for the Central tz */
	{ "MST",            "America/Denver" },		/* Other name for the mountain tz */
	{ "MST7MDT",        "America/Denver" },		/* ditto */
};

static gboolean
compare_timezones (const char *a,
		   const char *b)
{
	if (g_str_equal (a, b))
		return TRUE;
	if (strchr (b, '/') == NULL) {
		char *prefixed;

		prefixed = g_strdup_printf ("/%s", b);
		if (g_str_has_suffix (a, prefixed)) {
			g_free (prefixed);
			return TRUE;
		}
		g_free (prefixed);
	}

	return FALSE;
}

char *
tz_info_get_clean_name (TzDB *tz_db,
			const char *tz)
{
	char *ret;
	const char *timezone;
	guint i;
	gboolean replaced;

	/* Remove useless prefixes */
	if (g_str_has_prefix (tz, "right/"))
		tz = tz + strlen ("right/");
	else if (g_str_has_prefix (tz, "posix/"))
		tz = tz + strlen ("posix/");

	/* Here start the crazies */
	replaced = FALSE;

	for (i = 0; i < G_N_ELEMENTS (aliases); i++) {
		if (compare_timezones (tz, aliases[i].orig)) {
			replaced = TRUE;
			timezone = aliases[i].dest;
			break;
		}
	}

	/* Try again! */
	if (!replaced) {
		/* Ignore crazy solar times from the '80s */
		if (g_str_has_prefix (tz, "Asia/Riyadh") ||
		    g_str_has_prefix (tz, "Mideast/Riyadh")) {
			timezone = "Asia/Riyadh";
			replaced = TRUE;
		}
	}

	if (!replaced)
		timezone = tz;

	ret = g_hash_table_lookup (tz_db->backward, timezone);
	if (ret == NULL)
		return g_strdup (timezone);
	return g_strdup (ret);
}

/* ----------------- *
 * Private functions *
 * ----------------- */

static gchar *
tz_data_file_get (void)
{
	gchar *file;

	file = g_strdup (TZ_DATA_FILE);

	return file;
}

static float
convert_pos (gchar *pos, int digits)
{
	gchar whole[10];
	gchar *fraction;
	gint i;
	float t1, t2;
	
	if (!pos || strlen(pos) < 4 || digits > 9) return 0.0;
	
	for (i = 0; i < digits + 1; i++) whole[i] = pos[i];
	whole[i] = '\0';
	fraction = pos + digits + 1;

	t1 = g_strtod (whole, NULL);
	t2 = g_strtod (fraction, NULL);

	if (t1 >= 0.0) return t1 + t2/pow (10.0, strlen(fraction));
	else return t1 - t2/pow (10.0, strlen(fraction));
}

static int
compare_country_names (const void *a, const void *b)
{
	const TzLocation *tza = * (TzLocation **) a;
	const TzLocation *tzb = * (TzLocation **) b;
	
	return strcmp (tza->zone, tzb->zone);
}


static void
sort_locations_by_country (GPtrArray *locations)
{
	qsort (locations->pdata, locations->len, sizeof (gpointer),
	       compare_country_names);
}

static void
load_backward_tz (TzDB *tz_db)
{
  GError *error = NULL;
  char **lines, *contents;
  guint i;
  gchar *file;

  tz_db->backward = g_hash_table_new_full (g_str_hash, g_str_equal, g_free, g_free);

  file = g_strdup_printf ("%s/" TZMAP_DATADIR "/timezones_backward", get_widgets_datadir());
  if (g_file_get_contents (file, &contents, NULL, &error) == FALSE) {
      g_warning ("Failed to load 'backward' file: %s", error->message);
      return;
    }
  g_free(file);

  lines = g_strsplit (contents, "\n", -1);
  g_free (contents);
  for (i = 0; lines[i] != NULL; i++) {
      char **items;
      guint j;
      char *real, *alias;

      if (g_ascii_strncasecmp (lines[i], "Link\t", 5) != 0)
        continue;

      items = g_strsplit (lines[i], "\t", -1);
      real = NULL;
      alias = NULL;
      /* Skip the "Link<tab>" part */
      for (j = 1; items[j] != NULL; j++) {
          if (items[j][0] == '\0')
            continue;
          if (real == NULL) {
              real = items[j];
              continue;
            }
          alias = items[j];
          break;
        }

      if (real == NULL || alias == NULL)
        g_warning ("Could not parse line: %s", lines[i]);

      /* We don't need more than one name for it */
      if (g_str_equal (real, "Etc/UTC") ||
          g_str_equal (real, "Etc/UCT"))
        real = "Etc/GMT";

      g_hash_table_insert (tz_db->backward, g_strdup (alias), g_strdup (real));
      g_strfreev (items);
    }
  g_strfreev (lines);
}

