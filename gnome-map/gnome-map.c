/*  GNOME canvas based interface to a map using a simple cylindrical proj */
/*                                                                        */
/* Copyright (C) 1999 Red Hat, Incorportated                              */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#include <gnome.h>
#include <math.h>
#include "gnome-map.h"

/* look in <gdk/gdkcursors.h> for valid values */
#define MAP_CURSOR GDK_LEFT_PTR

/**
 * gnome_map_set_image:
 * @map: Map to apply image to.
 * @imagefile: Filename of image for map.
 *
 * This function sets the image used for the map to @imagefile.  It is 
 * assumed that this image is a simple cylindrical projection. 
 *
 * Return value: 0 on success, -1 if image could not be loaded
 **/
static gint
gnome_map_set_image ( GnomeMap *map, gchar *imagefile )
{

    g_return_val_if_fail ( map != NULL, -1 );
    g_return_val_if_fail ( map->image == NULL, -1 );

    /* load map image */
    if (map->aa)
	map->image = gnome_canvas_load_alpha (imagefile);
    else
	map->image = gdk_imlib_load_image (imagefile);

    if (!map->image)
	return -1;

    return 0;
}


static void
canvas_realize_event (GtkWidget *canvas, gpointer *data)
{

    GdkCursor   *ptrcursor;

    ptrcursor = gdk_cursor_new (MAP_CURSOR);
    if (!ptrcursor) {
	g_warning ("Unable to load new cursor %d for map\n", MAP_CURSOR);
	return;
    }

    gdk_window_set_cursor (canvas->window, ptrcursor);

    gdk_cursor_destroy (ptrcursor);
}

/**
 * gnome_map_new:
 * @imagefile: File to be used map image.
 * @width: Width of map view in pixels. 
 * @height: Height of map view in pixels.
 * @antialias: Boolean used to set map to use antialias canvas or not.
 *
 * Creates a new map, using anti-aliased or normal canvas based on the
 * value of @antialias.  Of anti-aliased maps the image file must be
 * in PNG format (this is a gnome-canvas limitation as of gnome-libs 1.0.10).
 * If @width and @height are both <= 0, then the map image size is used.
 * If only one of  @width or @height is > 0, then the unspecified
 * dimension is scaled (perserving the aspect of the original image).
 *
 * Return value: The newly-created map structure or NULL if image couldn't
 *               be loaded.
 **/
GnomeMap *
gnome_map_new ( gchar *imagefile, gint width, gint height, gboolean aa )
{
    GnomeCanvasGroup *canvas_root;
    GnomeMap    *map;
    gint        h, w;

    map = g_new0 ( GnomeMap, 1 );
    map->aa = aa;

    if ( gnome_map_set_image ( map, imagefile ) < 0 ) {
	g_free (map);
	return NULL;
    }

    /* create a canvas */
    if (aa) {
	gtk_widget_push_visual (gdk_rgb_get_visual ());
	gtk_widget_push_colormap (gdk_rgb_get_cmap ());
	map->canvas = gnome_canvas_new_aa ();
    } else {
	gtk_widget_push_visual (gdk_imlib_get_visual ());
	gtk_widget_push_colormap (gdk_imlib_get_colormap ());
	map->canvas = gnome_canvas_new ();
    }

    /* set map size and scaling */
    if ( width <= 0 && height <= 0 ) {
	w = map->image->rgb_width;
	h = map->image->rgb_height;
    } else if ( width > 0 && height <= 0 ) {
	w = width;
	h = (int)(((float)w/(float)map->image->rgb_width)*map->image->rgb_height);
    } else if ( width <= 0 && height > 0 ) {
	h = height;
	w = (int)(((float)h/(float)map->image->rgb_height)*map->image->rgb_width);
    } else {
	w = width;
	h = height;
    }

    map->width = w;
    map->height = h;
    map->long1 = -180.0;
    map->lat1  = -90.0;
    map->long2 = 180.0;
    map->lat2  =  90.0;

    gtk_widget_set_usize (map->canvas, w, h);
    gnome_canvas_set_pixels_per_unit (GNOME_CANVAS (map->canvas), 1.0);
    gnome_canvas_set_scroll_region (GNOME_CANVAS (map->canvas), 
				    0.0, 0.0,
				    (double)w, (double)h);

    gtk_widget_show(map->canvas);

    /* Setup canvas items */
    canvas_root = gnome_canvas_root (GNOME_CANVAS (map->canvas));
    map->image_item = gnome_canvas_item_new (canvas_root,
					gnome_canvas_image_get_type (),
					"image", map->image,
					"x", 0.0,
					"y", 0.0,
					"width", (double) w,
					"height", (double) h,
					"anchor", GTK_ANCHOR_NW,
					NULL);

    /* grap realize signal so we can set cursor for map */
    gtk_signal_connect (GTK_OBJECT (map->canvas), "realize",
			 (GtkSignalFunc) canvas_realize_event,
			 NULL);

    /* restore to original */
    gtk_widget_pop_colormap ();
    gtk_widget_pop_visual ();

    return map;
}


/**
 * gnome_map_get_image_size: Get the unscaled image size of map image.
 * @map: The map which image size is desired for.
 * @width: Width of map in pixels.
 * @height: Height of map in pixels.
 *
 * Given the GnomeMap @map, this function returns the dimensions of the
 * original unscaled map image.
 *
 * Return value: None.
 **/
void
gnome_map_get_image_size ( GnomeMap *map, gint *width, gint *height )
{
    g_return_if_fail ( map != NULL || map->image != NULL);
    g_return_if_fail ( width != NULL || height != NULL );

    *width  = map->image->rgb_width;
    *height = map->image->rgb_width;
}

/**
 * gnome_map_set_size: Set screen dimensions (in pixels) of map view.
 * @map: Map to apply dimensions to.
 * @width: Desired width of map view.
 * @height: Desired height of map view.
 *
 * Given a map which has an image associated with it via the
 * gnome_map_set_image() call, set the onscreen size of the map view widget.
 *
 * Return value: None.
 **/
void
gnome_map_set_size ( GnomeMap *map, gint width, gint height )
{
    g_return_if_fail ( map != NULL );
    g_return_if_fail ( map->canvas != NULL );
    g_return_if_fail ( map->image != NULL );
    g_return_if_fail ( width > 0 );
    g_return_if_fail ( height > 0 );
}
    

    
/**
 * gnome_map_xlat_map2screen: Convert from map coordinates to screen coordinates.
 * @map: Map to apply dimensions to.
 * @longitude: Longitude coordinate to convert (in degrees). 
 * @latitude: Latitude coordinate to convert (in degrees).
 * @sx: Converted screen coordinate.
 * @sy: Converted screen coordinate.
 *
 * A (longitude, latitude) pair is converted to a (x, y) canvas coordinate.
 * (An obvious improvement to the gnome-map would be to just let the
 * canvas do the mapping internally.  If this change is made this function
 * will still work but will be a small stub).
 *
 * Return value: None.
 **/
void
gnome_map_xlat_map2screen ( GnomeMap *map, 
			    double longitude, double latitude,
			    double *sx, double *sy )
{
    g_return_if_fail ( map != NULL );

    *sx = (map->width/2.0 + (map->width/2.0)*longitude/180.0);
    *sy = (map->height/2.0 - (map->height/2.0)*latitude/90.0);
}

    
/**
 * gnome_map_xlat_screen2map: Convert from screen coordinates to map coordinates.
 * @map: Map to apply dimensions to.
 * @sx: Screen coordinate to convert.
 * @sy: Screen coordinate to convert.
 * @longitude: Converted longitude coordinate (in degrees). 
 * @latitude: Converted latitude coordinate (in degrees).
 *
 * A (x, y) canvas coordinate is converted to a (longitude, latitude) pair.
 * (An obvious improvement to the gnome-map would be to just let the
 * canvas do the mapping internally.  If this change is made this function
 * will still work but will be a small stub).
 *
 * Return value: None.
 **/
void
gnome_map_xlat_screen2map ( GnomeMap *map, 
			    double sx, double sy,
			    double *longitude, double *latitude)
{
    g_return_if_fail ( map != NULL );

    *longitude = ( sx - (double)map->width/2.0)/((double)map->width/2.0)*180.0;
    *latitude  = ((double)map->height/2.0-sy)/((double)map->height/2.0)*90.0;
}

/**
 * gnome_map_set_view: Set view of map in map coordinates.
 * @map: Map to apply dimensions to.
 * @longitude1: Longitude of corner 1.
 * @latitude1: Latitude of corner 1.
 * @longitude2: Longitude of corner 2.
 * @latitude2: Latitude of corner 2.
 *
 * Sets view of map to a box defined by the two corners given in map
 * coordinates.
 *
 * Return value: None.
 **/
void
gnome_map_set_view ( GnomeMap *map, 
			    double longitude1, double latitude1,
			    double longitude2, double latitude2)
{
    double x1, y1, x2, y2;
    double scale;

    g_return_if_fail ( map != NULL );
    g_return_if_fail ( longitude1 >= -180.0 && longitude1 <= 180.0 );
    g_return_if_fail ( longitude2 >= -180.0 && longitude2 <= 180.0 );
    g_return_if_fail ( latitude1 >= -90.0 && latitude1 <= 90.0 );
    g_return_if_fail ( latitude2 >= -90.0 && latitude2 <= 90.0 );


    gnome_map_xlat_map2screen (map, longitude1, latitude1, &x1, &y1);
    gnome_map_xlat_map2screen (map, longitude2, latitude2, &x2, &y2);

    gnome_canvas_set_scroll_region (GNOME_CANVAS(map->canvas),
				    x1, y1, x2, y2);

    if (longitude1 < longitude2) {
	map->long1 = longitude1;
	map->long2 = longitude2;
    } else {
	map->long1 = longitude2;
	map->long2 = longitude1;
    }

    if (latitude1 < latitude2) {
	map->lat1 = latitude1;
	map->lat2 = latitude2;
    } else {
	map->lat1 = latitude2;
	map->lat2 = latitude1;
    }	

    scale = ((double)map->width)/fabs(x1-x2);
    gnome_canvas_set_pixels_per_unit (GNOME_CANVAS(map->canvas), scale);

}
			    
/**
 * gnome_map_is_loc_in_view: Test to see if location is on current view 
 * @map: Map to apply dimensions to.
 * @longitude: Longitude of location to test.
 * @latitude: Latitude of location to test.
 *
 * Tests whether (longitude, latitude) is within current map view.
 *
 * Return value: TRUE is visible, FALSE if not.
 **/
gboolean
gnome_map_is_loc_in_view (GnomeMap *map, double longitude, double latitude)
{

    return !(longitude < map->long1 || longitude > map->long2 ||
	     latitude < map->lat1  || latitude > map->lat2);
}

