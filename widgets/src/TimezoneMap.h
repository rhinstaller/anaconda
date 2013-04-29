/*
 * Copyright (C) 2012-2013 Red Hat, Inc
 *
 * Heavily based on the gnome-control-center code,
 * Copyright (c) 2010 Intel, Inc
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

#ifndef _ANACONDA_TIMEZONE_MAP_H
#define _ANACONDA_TIMEZONE_MAP_H

#include <gtk/gtk.h>
#include "tz.h"

G_BEGIN_DECLS

#define ANACONDA_TYPE_TIMEZONE_MAP anaconda_timezone_map_get_type()

#define ANACONDA_TIMEZONE_MAP(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST ((obj), \
  ANACONDA_TYPE_TIMEZONE_MAP, AnacondaTimezoneMap))

#define ANACONDA_TIMEZONE_MAP_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST ((klass), \
  ANACONDA_TYPE_TIMEZONE_MAP, AnacondaTimezoneMapClass))

#define ANACONDA_IS_TIMEZONE_MAP(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE ((obj), \
  ANACONDA_TYPE_TIMEZONE_MAP))

#define ANACONDA_IS_TIMEZONE_MAP_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_TYPE ((klass), \
  ANACONDA_TYPE_TIMEZONE_MAP))

#define ANACONDA_TIMEZONE_MAP_GET_CLASS(obj) \
  (G_TYPE_INSTANCE_GET_CLASS ((obj), \
  ANACONDA_TYPE_TIMEZONE_MAP, AnacondaTimezoneMapClass))

typedef struct _AnacondaTimezoneMap AnacondaTimezoneMap;
typedef struct _AnacondaTimezoneMapClass AnacondaTimezoneMapClass;
typedef struct _AnacondaTimezoneMapPrivate AnacondaTimezoneMapPrivate;

struct _AnacondaTimezoneMap
{
  GtkWidget parent;

  AnacondaTimezoneMapPrivate *priv;
};

struct _AnacondaTimezoneMapClass
{
  GtkWidgetClass parent_class;
};

GType anaconda_timezone_map_get_type (void) G_GNUC_CONST;

GtkWidget *anaconda_timezone_map_new (void);

gboolean anaconda_timezone_map_set_timezone (AnacondaTimezoneMap *map,
                                             const gchar   *timezone,
                                             gboolean no_signal);

gchar *anaconda_timezone_map_get_timezone (AnacondaTimezoneMap *map);

G_END_DECLS

#endif /* _ANACONDA_TIMEZONE_MAP_H */
