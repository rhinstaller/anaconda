/*  GNOME canvas based interface to a map using a simple cylindrical proj */
/*                                                                        */
/* Copyright (C) 1999 Red Hat, Incorportated                              */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#ifndef _GNOME_MAP_H_
#define _GNOME_MAP_H_

struct _GnomeMapStruct {
    GtkWidget          *canvas;  /* canvas object used to display map */

    gboolean           aa;      /* true if antialiased */

    gint               width;   /* width of canvas in pixels         */
    gint               height;  /* height of canvas in pixels        */
    double             long1;   /* long1, lat1 is lower left corner of view */
    double             lat1;    
    double             long2;   /* long2, lat2 is upper right corner of view */
    double             lat2;

    GdkImlibImage      *image;       /* actual image data */
    GnomeCanvasItem    *image_item;   /* background image canvas object */
    void               *data;      /* extra stuff */
};

typedef struct _GnomeMapStruct  GnomeMap;


/* create new map */
GnomeMap  *gnome_map_new ( gchar *imagefile, 
			  gint width, gint height, 
			  gboolean antialias );

/* set background map image used by map */
/*gint gnome_map_set_image ( GnomeMap *map, gchar *imagefile ); */

/* get original size of map image */
/*void gnome_map_get_image_size ( GnomeMap *map, gint *width, gint *height ); */

/* set/get size of view in pixels */
/*void gnome_map_set_size  ( GnomeMap *map, gint width, gint height );*/
void gnome_map_get_size  ( GnomeMap *map, gint *width, gint *height );

/* utility functions to go from screen coords to map coords */
void gnome_map_xlat_map2screen ( GnomeMap *map,
				   double longitude, double latitude,
				   double *sx, double *sy );
void gnome_map_xlat_screen2map ( GnomeMap *map,
				   double sx, double sy,
				   double *longitude, double *latitude );
void gnome_map_set_view (GnomeMap *map,
			 double longitude1, double latitude1,
			 double longitude2, double latitude2);

gboolean gnome_map_is_loc_in_view (GnomeMap *map, 
				   double longitude, double latitude);
#endif

	
