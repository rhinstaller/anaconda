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
 * Author: Ales Kozumplik <akozumpl@redhat.com>
 */

#ifndef LIGHTBOX_H
#define LIGHTBOX_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_LIGHTBOX              (anaconda_lightbox_get_type())
#define ANACONDA_LIGHTBOX(obj)              (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_LIGHTBOX, AnacondaLightbox))
#define ANACONDA_LIGHTBOX_CLASS(klass)      (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_LIGHTBOX, AnacondaLightboxClass))
#define ANACONDA_IS_LIGHTBOX(obj)           (G_TYPE_CHECK_INSTANCE_TYPE ((obj), ANACONDA_TYPE_LIGHTBOX))
#define ANACONDA_IS_LIGHTBOX_CLASS(klass)   (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_LIGHTBOX))
#define ANACONDA_LIGHTBOX_GET_CLASS(obj)    (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_LIGHTBOX, AnacondaLightboxClass))

typedef struct _AnacondaLightbox        AnacondaLightbox;
typedef struct _AnacondaLightboxClass   AnacondaLightboxClass;
typedef struct _AnacondaLightboxPrivate AnacondaLightboxPrivate;

/**
 * AnacondaLightbox:
 *
 * The AnacondaLightbox struct contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaLightbox {
    GtkWindow               parent;

    /*< private >*/
    AnacondaLightboxPrivate *priv;
};

/**
 * AnacondaLightboxClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly. This allows a AnacondaLightbox
 *                pointer to be cast to a #GtkWindow pointer.
 */
struct _AnacondaLightboxClass {
    GtkWindowClass          parent_class;
};

GType      anaconda_lightbox_get_type(void);
GtkWidget *anaconda_lightbox_new(GtkWindow *parent);

G_END_DECLS

#endif
