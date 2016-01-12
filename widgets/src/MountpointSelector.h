/*
 * Copyright (C) 2012  Red Hat, Inc.
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

#ifndef _MOUNTPOINT_SELECTOR_H
#define _MOUNTPOINT_SELECTOR_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_MOUNTPOINT_SELECTOR            (anaconda_mountpoint_selector_get_type())
#define ANACONDA_MOUNTPOINT_SELECTOR(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_MOUNTPOINT_SELECTOR, AnacondaMountpointSelector))
#define ANACONDA_IS_MOUNTPOINT_SELECTOR(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj)), ANACONDA_TYPE_MOUNTPOINT_SELECTOR)
#define ANACONDA_MOUNTPOINT_SELECTOR_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_MOUNTPOINT_SELECTOR, AnacondaMountpointSelectorClass))
#define ANACONDA_IS_MOUNTPOINT_SELECTOR_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_MOUNTPOINT_SELECTOR))
#define ANACONDA_MOUNTPOINT_SELECTOR_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_MOUNTPOINT_SELECTOR, AnacondaMountpointSelectorClass))

typedef struct _AnacondaMountpointSelector        AnacondaMountpointSelector;
typedef struct _AnacondaMountpointSelectorClass   AnacondaMountpointSelectorClass;
typedef struct _AnacondaMountpointSelectorPrivate AnacondaMountpointSelectorPrivate;

/**
 * AnacondaMountpointSelector:
 *
 * The AnacondaMountpointSelector struct contains only private fields and should
 * not be directly accessed.
 */
struct _AnacondaMountpointSelector {
    GtkEventBox                   parent;

    /*< private >*/
    AnacondaMountpointSelectorPrivate *priv;
};

/**
 * AnacondaMountpointSelectorClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows an AnacondaMountpointSelectorClass
 *                pointer to be cast to a #GtkEventBox pointer.
 */
struct _AnacondaMountpointSelectorClass {
    GtkEventBoxClass parent_class;
};

GType       anaconda_mountpoint_selector_get_type (void);
GtkWidget  *anaconda_mountpoint_selector_new      ();

gboolean    anaconda_mountpoint_selector_get_chosen (AnacondaMountpointSelector *widget);
void        anaconda_mountpoint_selector_set_chosen (AnacondaMountpointSelector *widget, gboolean is_chosen);

GtkWidget  *anaconda_mountpoint_selector_get_page (AnacondaMountpointSelector *widget);
void        anaconda_mountpoint_selector_set_page (AnacondaMountpointSelector *widget, GtkWidget *parent_page);

G_END_DECLS

#endif
