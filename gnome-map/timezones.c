/*  GNOME canvas based interface to a map using a simple cylindrical proj */
/*                                                                        */
/* Copyright (C) 1999 Red Hat, Incorportated                              */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <math.h>

#include "timezones.h"


TZZoneInfo *
tzinfo_get_for_location (TimeZoneLocation *loc)
{
    TZZoneInfo *tzinfo;
    gchar      *str;

    g_return_val_if_fail (loc != NULL, NULL);
    g_return_val_if_fail (loc->zone != NULL, NULL);

    str = g_strdup_printf ("TZ=%s", loc->zone);
    g_print ("%s %s\n",loc->zone, str);
    putenv (str);
    tzset ();
    g_free (str);
    tzinfo = g_new0 (TZZoneInfo, 1);

    g_print ("%s %s %ld %d\n",tzname[0], tzname[1], timezone, daylight);

    /* Currently this solution doesnt seem to work - I get that */
    /* America/Phoenix uses daylight savings, which is wrong    */
    tzinfo->tzname_normal   = (tzname[0]) ? g_strdup (tzname[0]) : NULL;
    tzinfo->tzname_daylight = (tzname[1]) ? g_strdup (tzname[1]) : NULL;
    tzinfo->utc_offset = timezone;
    tzinfo->daylight   = daylight;

    return tzinfo;
}

void
tzinfo_free (TZZoneInfo *tzinfo)
{
    g_return_if_fail (tzinfo != NULL);

    if (tzinfo->tzname_normal)
	g_free (tzinfo->tzname_normal);
    if (tzinfo->tzname_daylight)
	g_free (tzinfo->tzname_daylight);
    g_free (tzinfo);
}

static float
convertPos( gchar *pos, int digits )
{
    gchar whole[10];
    gchar *fraction;
    gint i;
    float t1, t2;

    if (!pos || strlen(pos) < 4 || digits > 9)
	return 0.0;

    for (i=0; i < digits+1; i++)
	whole[i] = pos[i];
    whole[i] = '\0';
    fraction = pos+digits+1;

    t1 = g_strtod (whole, NULL);
    t2 = g_strtod (fraction, NULL);

    /* how do I get sign of a float in a portable fashion? */
    if (t1 >= 0.0 )
	return t1 + t2/pow (10.0, strlen(fraction));
    else
	return t1 - t2/pow (10.0, strlen(fraction));

}

#if 0

/* Currently not working */
static void
free_tzdata( TimeZoneLocation *tz)
{

    if (tz->country)
	g_free(tz->country);
    if (tz->zone)
	g_free(tz->zone);
    if (tz->comment)
	g_free(tz->comment);

    g_free(tz);
}
#endif

static int
compare_country_names (const void * a, const void * b)
{
    const TimeZoneLocation *tza = * (TimeZoneLocation **) a;
    const TimeZoneLocation *tzb = * (TimeZoneLocation **) b;
    
    return strcmp (tza->zone, tzb->zone);
}

static void
sort_locations_by_country (GPtrArray *locations)
{
    qsort (locations->pdata, locations->len, sizeof (gpointer),
	   compare_country_names);
}


GPtrArray *
loadTZDB( void )
{
    GPtrArray *tzdb;
    FILE *tzfile;
    char buf[4096];

    tzfile = fopen (TZ_DATAFILE, "r");
    if (!tzfile)
	return NULL;

    tzdb = g_ptr_array_new ();

    while (fgets (buf, sizeof(buf), tzfile)) {
	gchar **tmpstrarr;
	gchar *latstr, *lngstr, *p;
	TimeZoneLocation *loc;

	if (*buf == '#')
	    continue;

	g_strchomp(buf);
	tmpstrarr = g_strsplit(buf,"\t", 4);

#ifdef DEBUG_ZONEREAD
	printf ("country code: %s\nlocaton:%s\ntimezone:%s\ncomment:\%s\n", 
		tmpstrarr[0], tmpstrarr[1], tmpstrarr[2], tmpstrarr[3]);
#endif
	latstr = g_strdup (tmpstrarr[1]);
	p = latstr+1;
	while (*p != '-' && *p != '+')
	    p++;
	lngstr = g_strdup (p);
	*p = '\0';

#ifdef DEBUG_ZONEREAD
	printf ("lat: %s\nlong: %s\n",latstr, lngstr);
	printf ("lat: %f\nlong: %f\n\n", convertPos (latstr,2), convertPos (lngstr,3));
#endif	
	loc = g_new( TimeZoneLocation, 1);
	loc->country = g_strdup(tmpstrarr[0]);
	loc->zone    = g_strdup(tmpstrarr[2]);
	loc->comment = (tmpstrarr[3]) ? g_strdup(tmpstrarr[3]) : NULL;
	loc->latitude  = convertPos(latstr,2);
	loc->longitude = convertPos(lngstr,3);

	g_ptr_array_add (tzdb, (gpointer) loc);

	g_free (latstr);
	g_free (lngstr);
	g_strfreev (tmpstrarr);
    }

    fclose (tzfile);

    /* now sort by country */
    sort_locations_by_country (tzdb);

    return tzdb;
}    

