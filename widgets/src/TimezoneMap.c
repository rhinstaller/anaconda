/* Copyright (C) 2012-2013 Red Hat, Inc
 *
 * Heavily based on the code from gnome-control-center, Copyright (C) 2010 Intel, Inc.
 * Written by Thomas Wood <thomas.wood@intel.com>
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
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
 *
 * Author: Vratislav Podzimek <vpodzime@redhat.com>
 *
 */

#include "TimezoneMap.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include "tz.h"

/**
 * SECTION: TimezoneMap
 * @title: AnacondaTimezoneMap
 * @short_description: An interactive map for timezone selection
 *
 * A #AnacondaTimezoneMap is a widget that can be used for timezone selection.
 * The most important is the ::timezone-changed signal that includes the newly
 * selected timezone.
 */

G_DEFINE_TYPE (AnacondaTimezoneMap, anaconda_timezone_map, GTK_TYPE_WIDGET)

#define TIMEZONE_MAP_PRIVATE(o) \
  (G_TYPE_INSTANCE_GET_PRIVATE ((o), ANACONDA_TYPE_TIMEZONE_MAP, AnacondaTimezoneMapPrivate))


typedef struct {
  gdouble offset;
  guchar red;
  guchar green;
  guchar blue;
  guchar alpha;
} AnacondaTimezoneMapOffset;

struct _AnacondaTimezoneMapPrivate {
  GdkPixbuf *orig_background;
  GdkPixbuf *orig_color_map;

  GdkPixbuf *background;
  GdkPixbuf *color_map;

  guchar *visible_map_pixels;
  gint visible_map_rowstride;

  gdouble selected_offset;

  TzDB *tzdb;
  TzLocation *location;
};

enum {
  TIMEZONE_CHANGED,
  LAST_SIGNAL
};

static guint signals[LAST_SIGNAL];

static AnacondaTimezoneMapOffset color_codes[] =
{
    {-11.0, 43, 0, 0, 255 },
    {-10.0, 85, 0, 0, 255 },
    {-9.5, 102, 255, 0, 255 },
    {-9.0, 128, 0, 0, 255 },
    {-8.0, 170, 0, 0, 255 },
    {-7.0, 212, 0, 0, 255 },
    {-6.0, 255, 0, 1, 255 }, // north
    {-6.0, 255, 0, 0, 255 }, // south
    {-5.0, 255, 42, 42, 255 },
    {-4.5, 192, 255, 0, 255 },
    {-4.0, 255, 85, 85, 255 },
    {-3.5, 0, 255, 0, 255 },
    {-3.0, 255, 128, 128, 255 },
    {-2.0, 255, 170, 170, 255 },
    {-1.0, 255, 213, 213, 255 },
    {0.0, 43, 17, 0, 255 },
    {1.0, 85, 34, 0, 255 },
    {2.0, 128, 51, 0, 255 },
    {3.0, 170, 68, 0, 255 },
    {3.5, 0, 255, 102, 255 },
    {4.0, 212, 85, 0, 255 },
    {4.5, 0, 204, 255, 255 },
    {5.0, 255, 102, 0, 255 },
    {5.5, 0, 102, 255, 255 },
    {5.75, 0, 238, 207, 247 },
    {6.0, 255, 127, 42, 255 },
    {6.5, 204, 0, 254, 254 },
    {7.0, 255, 153, 85, 255 },
    {8.0, 255, 179, 128, 255 },
    {9.0, 255, 204, 170, 255 },
    {9.5, 170, 0, 68, 250 },
    {10.0, 255, 230, 213, 255 },
    {10.5, 212, 124, 21, 250 },
    {11.0, 212, 170, 0, 255 },
    {11.5, 249, 25, 87, 253 },
    {12.0, 255, 204, 0, 255 },
    {12.75, 254, 74, 100, 248 },
    {13.0, 255, 85, 153, 250 },
    {-100, 0, 0, 0, 0 }
};

/**
 * anaconda_timezone_map_new:
 *
 * Creates a new #AnacondaTimezoneMap.
 *
 * Returns: A new #AnacondaTimezoneMap
 */
GtkWidget *anaconda_timezone_map_new () {
    return g_object_new(ANACONDA_TYPE_TIMEZONE_MAP, NULL);
}

static void
anaconda_timezone_map_get_property (GObject    *object,
                              guint       property_id,
                              GValue     *value,
                              GParamSpec *pspec) {
  switch (property_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
    }
}

static void
anaconda_timezone_map_set_property (GObject      *object,
                              guint         property_id,
                              const GValue *value,
                              GParamSpec   *pspec) {
  switch (property_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
    }
}

static void
anaconda_timezone_map_dispose (GObject *object) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (object)->priv;

  if (priv->orig_background) {
      g_object_unref (priv->orig_background);
      priv->orig_background = NULL;
    }

  if (priv->orig_color_map) {
      g_object_unref (priv->orig_color_map);
      priv->orig_color_map = NULL;
    }

  if (priv->background) {
      g_object_unref (priv->background);
      priv->background = NULL;
    }

  if (priv->color_map) {
      g_object_unref (priv->color_map);
      priv->color_map = NULL;

      priv->visible_map_pixels = NULL;
      priv->visible_map_rowstride = 0;
    }

  G_OBJECT_CLASS (anaconda_timezone_map_parent_class)->dispose (object);
}

static void
anaconda_timezone_map_finalize (GObject *object) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (object)->priv;

  if (priv->tzdb) {
      tz_db_free (priv->tzdb);
      priv->tzdb = NULL;
    }


  G_OBJECT_CLASS (anaconda_timezone_map_parent_class)->finalize (object);
}

/* GtkWidget functions */
static void
anaconda_timezone_map_get_preferred_width (GtkWidget *widget,
                                     gint      *minimum,
                                     gint      *natural) {
  /* choose a minimum size small enough to prevent the window
   * from growing horizontally
   */
  if (minimum != NULL)
    *minimum = 300;
  if (natural != NULL)
    *natural = 300;
}

static void
anaconda_timezone_map_get_preferred_height (GtkWidget *widget,
                                      gint      *minimum,
                                      gint      *natural) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (widget)->priv;
  gint size;

  /* The + 20 here is a slight tweak to make the map fill the
   * panel better without causing horizontal growing
   */
  size = 300 * gdk_pixbuf_get_height (priv->orig_background) / gdk_pixbuf_get_width (priv->orig_background) + 20;
  if (minimum != NULL)
    *minimum = size;
  if (natural != NULL)
    *natural = size;
}

static void
anaconda_timezone_map_size_allocate (GtkWidget     *widget,
                               GtkAllocation *allocation) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (widget)->priv;

  if (priv->background)
    g_object_unref (priv->background);

  priv->background = gdk_pixbuf_scale_simple (priv->orig_background,
                                              allocation->width,
                                              allocation->height,
                                              GDK_INTERP_BILINEAR);

  if (priv->color_map)
    g_object_unref (priv->color_map);

  priv->color_map = gdk_pixbuf_scale_simple (priv->orig_color_map,
                                             allocation->width,
                                             allocation->height,
                                             GDK_INTERP_BILINEAR);

  priv->visible_map_pixels = gdk_pixbuf_get_pixels (priv->color_map);
  priv->visible_map_rowstride = gdk_pixbuf_get_rowstride (priv->color_map);

  GTK_WIDGET_CLASS (anaconda_timezone_map_parent_class)->size_allocate (widget,
                                                                  allocation);
}

static void
anaconda_timezone_map_realize (GtkWidget *widget) {
  GdkWindowAttr attr = { 0, };
  GtkAllocation allocation;
  GdkCursor *cursor;
  GdkWindow *window;

  gtk_widget_get_allocation (widget, &allocation);

  gtk_widget_set_realized (widget, TRUE);

  attr.window_type = GDK_WINDOW_CHILD;
  attr.wclass = GDK_INPUT_OUTPUT;
  attr.width = allocation.width;
  attr.height = allocation.height;
  attr.x = allocation.x;
  attr.y = allocation.y;
  attr.event_mask = gtk_widget_get_events (widget)
                                 | GDK_EXPOSURE_MASK | GDK_BUTTON_PRESS_MASK;

  window = gdk_window_new (gtk_widget_get_parent_window (widget), &attr,
                           GDK_WA_X | GDK_WA_Y);

  cursor = gdk_cursor_new (GDK_HAND2);
  gdk_window_set_cursor (window, cursor);

  gdk_window_set_user_data (window, widget);
  gtk_widget_set_window (widget, window);
}


static gdouble
convert_longtitude_to_x (gdouble longitude, gint map_width) {
  const gdouble xdeg_offset = -6;
  gdouble x;

  x = (map_width * (180.0 + longitude) / 360.0)
    + (map_width * xdeg_offset / 180.0);

  return x;
}

static gdouble
radians (gdouble degrees) {
  return (degrees / 360.0) * G_PI * 2;
}

static gdouble
convert_latitude_to_y (gdouble latitude, gdouble map_height) {
  gdouble bottom_lat = -59;
  gdouble top_lat = 81;
  gdouble top_per, y, full_range, top_offset, map_range;

  top_per = top_lat / 180.0;
  y = 1.25 * log (tan (G_PI_4 + 0.4 * radians (latitude)));
  full_range = 4.6068250867599998;
  top_offset = full_range * top_per;
  map_range = fabs (1.25 * log (tan (G_PI_4 + 0.4 * radians (bottom_lat))) - top_offset);
  y = fabs (y - top_offset);
  y = y / map_range;
  y = y * map_height;
  return y;
}


static gboolean
anaconda_timezone_map_draw (GtkWidget *widget,
                      cairo_t   *cr) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (widget)->priv;
  GdkPixbuf *hilight, *orig_hilight, *pin;
  GtkAllocation alloc;
  gchar *file;
  GError *err = NULL;
  gdouble pointx, pointy;
  char buf[16];

  gtk_widget_get_allocation (widget, &alloc);

  /* paint background */
  gdk_cairo_set_source_pixbuf (cr, priv->background, 0, 0);
  cairo_paint (cr);

  /* paint hilight */
  file = g_strdup_printf ("%s/" TZMAP_DATADIR "/timezone_%s.png",
                          get_widgets_datadir(),
                          g_ascii_formatd (buf, sizeof (buf),
                                           "%g", priv->selected_offset));
  orig_hilight = gdk_pixbuf_new_from_file (file, &err);
  g_free (file);
  file = NULL;

  if (!orig_hilight) {
      g_warning ("Could not load hilight: %s",
                 (err) ? err->message : "Unknown Error");
      if (err)
        g_clear_error (&err);
    }
  else {

      hilight = gdk_pixbuf_scale_simple (orig_hilight, alloc.width,
                                         alloc.height, GDK_INTERP_BILINEAR);
      gdk_cairo_set_source_pixbuf (cr, hilight, 0, 0);

      cairo_paint (cr);
      g_object_unref (hilight);
      g_object_unref (orig_hilight);
    }

  /* load pin icon */

  file = g_strdup_printf("%s/" TZMAP_DATADIR "/pin.png", get_widgets_datadir());
  pin = gdk_pixbuf_new_from_file (file, &err);
  g_free(file);

  if (err) {
      g_warning ("Could not load pin icon: %s", err->message);
      g_clear_error (&err);
    }

  if (priv->location) {
      pointx = convert_longtitude_to_x (priv->location->longitude, alloc.width);
      pointy = convert_latitude_to_y (priv->location->latitude, alloc.height);

      if (pointy > alloc.height)
        pointy = alloc.height;

      if (pin) {
          gdk_cairo_set_source_pixbuf (cr, pin, pointx - 8, pointy - 14);
          cairo_paint (cr);
        }
    }

  if (pin) {
      g_object_unref (pin);
    }

  return TRUE;
}


static void
anaconda_timezone_map_class_init (AnacondaTimezoneMapClass *klass) {
  GObjectClass *object_class = G_OBJECT_CLASS (klass);
  GtkWidgetClass *widget_class = GTK_WIDGET_CLASS (klass);

  g_type_class_add_private (klass, sizeof (AnacondaTimezoneMapPrivate));

  object_class->get_property = anaconda_timezone_map_get_property;
  object_class->set_property = anaconda_timezone_map_set_property;
  object_class->dispose = anaconda_timezone_map_dispose;
  object_class->finalize = anaconda_timezone_map_finalize;

  widget_class->get_preferred_width = anaconda_timezone_map_get_preferred_width;
  widget_class->get_preferred_height = anaconda_timezone_map_get_preferred_height;
  widget_class->size_allocate = anaconda_timezone_map_size_allocate;
  widget_class->realize = anaconda_timezone_map_realize;
  widget_class->draw = anaconda_timezone_map_draw;

  signals[TIMEZONE_CHANGED] = g_signal_new ("timezone-changed",
                                            ANACONDA_TYPE_TIMEZONE_MAP,
                                            G_SIGNAL_RUN_FIRST,
                                            0,
                                            NULL,
                                            NULL,
                                            g_cclosure_marshal_VOID__STRING,
                                            G_TYPE_NONE, 1,
                                            G_TYPE_STRING);
}


static gint
sort_locations (TzLocation *a,
                TzLocation *b) {
  if (a->dist > b->dist)
    return 1;

  if (a->dist < b->dist)
    return -1;

  return 0;
}

static void
set_location (AnacondaTimezoneMap *map,
              TzLocation    *location,
              gboolean no_city,
              gboolean no_signal) {
  AnacondaTimezoneMapPrivate *priv = map->priv;
  TzInfo *info;

  info = tz_info_from_location (location);

  priv->selected_offset = tz_location_get_utc_offset (location)
    / (60.0*60.0) + ((info->daylight) ? -1.0 : 0.0);

  if (no_city) {
      priv->location = NULL;
      if (!no_signal)
          g_signal_emit (map, signals[TIMEZONE_CHANGED], 0, "");
  }
  else {
      priv->location = location;
      if (!no_signal)
          g_signal_emit (map, signals[TIMEZONE_CHANGED], 0, priv->location->zone);
  }

  tz_info_free (info);
}

static gboolean
button_press_event (GtkWidget      *widget,
                    GdkEventButton *event) {
  AnacondaTimezoneMapPrivate *priv = ANACONDA_TIMEZONE_MAP (widget)->priv;
  gint x, y;
  guchar r, g, b, a;
  guchar *pixels;
  gint rowstride;
  gint i;

  const GPtrArray *array;
  gint width, height;
  GList *distances = NULL;
  GtkAllocation alloc;

  x = event->x;
  y = event->y;


  rowstride = priv->visible_map_rowstride;
  pixels = priv->visible_map_pixels;

  r = pixels[(rowstride * y + x * 4)];
  g = pixels[(rowstride * y + x * 4) + 1];
  b = pixels[(rowstride * y + x * 4) + 2];
  a = pixels[(rowstride * y + x * 4) + 3];


  for (i = 0; color_codes[i].offset != -100; i++) {
       if (color_codes[i].red == r && color_codes[i].green == g
           && color_codes[i].blue == b && color_codes[i].alpha == a) {
           priv->selected_offset = color_codes[i].offset;
         }
    }

  gtk_widget_queue_draw (widget);

  /* work out the co-ordinates */

  array = tz_get_locations (priv->tzdb);

  gtk_widget_get_allocation (widget, &alloc);
  width = alloc.width;
  height = alloc.height;

  for (i = 0; i < array->len; i++) {
      gdouble pointx, pointy, dx, dy;
      TzLocation *loc = array->pdata[i];

      pointx = convert_longtitude_to_x (loc->longitude, width);
      pointy = convert_latitude_to_y (loc->latitude, height);

      dx = pointx - x;
      dy = pointy - y;

      loc->dist = dx * dx + dy * dy;
      distances = g_list_prepend (distances, loc);

    }
  distances = g_list_sort (distances, (GCompareFunc) sort_locations);


  set_location (ANACONDA_TIMEZONE_MAP (widget), (TzLocation*) distances->data, FALSE, FALSE);

  g_list_free (distances);

  return TRUE;
}

static void
anaconda_timezone_map_init (AnacondaTimezoneMap *self) {
  AnacondaTimezoneMapPrivate *priv;
  GError *err = NULL;
  gchar *file;

  priv = self->priv = TIMEZONE_MAP_PRIVATE (self);

  file = g_strdup_printf("%s/" TZMAP_DATADIR "/bg.png", get_widgets_datadir());
  priv->orig_background = gdk_pixbuf_new_from_file (file, &err);
  g_free(file);

  if (!priv->orig_background) {
      g_warning ("Could not load background image: %s",
                 (err) ? err->message : "Unknown error");
      g_clear_error (&err);
    }

  file = g_strdup_printf("%s/" TZMAP_DATADIR "/cc.png", get_widgets_datadir());
  priv->orig_color_map = gdk_pixbuf_new_from_file (file, &err);
  g_free(file);

  if (!priv->orig_color_map) {
      g_warning ("Could not load background image: %s",
                 (err) ? err->message : "Unknown error");
      g_clear_error (&err);
    }

  priv->tzdb = tz_load_db ();

  g_signal_connect (self, "button-press-event", G_CALLBACK (button_press_event),
                    NULL);
}

/**
 * anaconda_timezone_map_set_timezone:
 * @map: an #AnacondaTimezoneMap
 * @timezone: timezone name
 * @no_signal: whether the timezone-changed signal should be emitted or not
 *
 * Modifies the map to show @timezone as selected. Also modifies the internal
 * data of the @map.
 *
 * Returns: (transfer none): Whether the change was successfully completed.
 */
gboolean
anaconda_timezone_map_set_timezone (AnacondaTimezoneMap *map,
                                    const gchar   *timezone,
                                    gboolean no_signal) {
  GPtrArray *locations;
  guint i;
  char *real_tz;
  gboolean ret;
  gboolean no_city = FALSE;

  /* "" means reset to default -- Europe/London timezone without
   *                              a pin (no_city) */
  if (!g_strcmp0 (timezone, "")) {
      timezone = "Europe/London";
      no_city = TRUE;
  }

  real_tz = tz_info_get_clean_name (map->priv->tzdb, timezone);

  locations = tz_get_locations (map->priv->tzdb);
  ret = FALSE;

  for (i = 0; i < locations->len; i++) {
      TzLocation *loc = locations->pdata[i];

      if (!g_strcmp0 (loc->zone, real_tz ? real_tz : timezone)) {
          set_location (map, loc, no_city, no_signal);
          ret = TRUE;
          break;
        }
    }

  if (ret)
    gtk_widget_queue_draw (GTK_WIDGET (map));

  g_free (real_tz);

  return ret;
}

/**
 * anaconda_timezone_map_get_timezone:
 * @map: an #AnacondaTimezoneMap
 *
 * Returns: (transfer none): the selected timezone
 */
gchar *
anaconda_timezone_map_get_timezone (AnacondaTimezoneMap *map) {
    if (map->priv->location)
        return map->priv->location->zone;
    else
        return "";
}
