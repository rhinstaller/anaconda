/*  GNOME canvas based interface to a map using a simple cylindrical proj */
/*                                                                        */
/* Copyright (C) 1999 Red Hat, Incorportated                              */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#ifndef _GNOME_MAP_TIMEZONES_H
#define _GNOME_MAP_TIMEZONES_H


#define TZ_DATAFILE "/usr/share/zoneinfo/zone.tab"


struct _TZ_DATA_LOCATION {
    char      *country;
    float     latitude;
    float     longitude;
    char      *zone;
    char      *comment;
};

typedef struct _TZ_DATA_LOCATION TimeZoneLocation;

/* see the glibc info page information on time zone information */
/*  tzname_normal    is the default name for the timezone */
/*  tzname_daylight  is the name of the zone when in daylight savings */
/*  utc_offset       is offset in seconds from utc */
/*  daylight         if non-zero then location obeys daylight savings */
struct _TZ_ZONE_INFO {
    char      *tzname_normal;
    char      *tzname_daylight;
    long int  utc_offset;
    int       daylight;
};

typedef struct _TZ_ZONE_INFO TZZoneInfo;

GPtrArray *loadTZDB ( void );
TZZoneInfo *tzinfo_get_for_location (TimeZoneLocation *loc);
void tzinfo_free (TZZoneInfo *tzinfo);
#endif
