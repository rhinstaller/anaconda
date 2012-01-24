/*
 * Copyright (C) 2011  Red Hat, Inc.
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
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author: Chris Lumens <clumens@redhat.com>
 */

#ifndef _DISK_OVERVIEW_H
#define _DISK_OVERVIEW_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_DISK_OVERVIEW            (anaconda_disk_overview_get_type())
#define ANACONDA_DISK_OVERVIEW(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_DISK_OVERVIEW, AnacondaDiskOverview))
#define ANACONDA_IS_DISK_OVERVIEW(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj)), ANACONDA_TYPE_DISK_OVERVIEW)
#define ANACONDA_DISK_OVERVIEW_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_DISK_OVERVIEW, AnacondaDiskOverviewClass))
#define ANACONDA_IS_DISK_OVERVIEW_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_DISK_OVERVIEW))
#define ANACONDA_DISK_OVERVIEW_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_DISK_OVERVIEW, AnacondaDiskOverviewClass))

typedef struct _AnacondaDiskOverview         AnacondaDiskOverview;
typedef struct _AnacondaDiskOverviewClass    AnacondaDiskOverviewClass;
typedef struct _AnacondaDiskOverviewPrivate  AnacondaDiskOverviewPrivate;

/**
 * AnacondaDiskOverview:
 *
 * The AnacondaDiskOverview struct contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaDiskOverview {
    GtkEventBox                  parent;

    /*< private >*/
    AnacondaDiskOverviewPrivate *priv;
};

/**
 * AnacondaDiskOverviewClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows a AnacondaDiskOverviewClass
 *                pointer to be cast to a #GtkEventBox pointer.
 */
struct _AnacondaDiskOverviewClass {
    GtkEventBoxClass parent_class;
};

GType       anaconda_disk_overview_get_type (void);
GtkWidget  *anaconda_disk_overview_new      ();

gboolean    anaconda_disk_overview_get_chosen(AnacondaDiskOverview *widget);
void        anaconda_disk_overview_set_chosen(AnacondaDiskOverview *widget, gboolean is_chosen);

G_END_DECLS

#endif
