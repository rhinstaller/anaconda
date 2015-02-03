/*
 * Copyright (C) 2011-2012  Red Hat, Inc.
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

#ifndef _STANDALONE_WINDOW_H
#define _STANDALONE_WINDOW_H

#include <gtk/gtk.h>

#include "BaseStandalone.h"

G_BEGIN_DECLS

#define ANACONDA_TYPE_STANDALONE_WINDOW              (anaconda_standalone_window_get_type())
#define ANACONDA_STANDALONE_WINDOW(obj)              (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_STANDALONE_WINDOW, AnacondaStandaloneWindow))
#define ANACONDA_IS_STANDALONE_WINDOW(obj)           (G_TYPE_CHECK_INSTANCE_TYPE ((obj), ANACONDA_TYPE_STANDALONE_WINDOW))
#define ANACONDA_STANDALONE_WINDOW_CLASS(klass)      (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_STANDALONE_WINDOW, AnacondaStandaloneWindowClass))
#define ANACONDA_IS_STANDALONE_WINDOW_CLASS(klass)   (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_STANDALONE_WINDOW))
#define ANACONDA_STANDALONE_WINDOW_GET_CLASS(obj)    (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_STANDALONE_WINDOW, AnacondaStandaloneWindowClass))

typedef struct _AnacondaStandaloneWindow          AnacondaStandaloneWindow;
typedef struct _AnacondaStandaloneWindowClass     AnacondaStandaloneWindowClass;
typedef struct _AnacondaStandaloneWindowPrivate   AnacondaStandaloneWindowPrivate;

/**
 * AnacondaStandaloneWindow:
 *
 * The AnacondaStandaloneWindow struct contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaStandaloneWindow {
    AnacondaBaseStandalone       parent;

    /*< private >*/
    AnacondaStandaloneWindowPrivate  *priv;
};

/**
 * AnacondaStandaloneWindowClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows an AnacondaStandaloneWindowClass
 *                pointer to be cast to an #AnacondaBaseWindow pointer.
 */
struct _AnacondaStandaloneWindowClass {
    AnacondaBaseStandaloneClass parent_class;
};

GType       anaconda_standalone_window_get_type (void);
GtkWidget  *anaconda_standalone_window_new      ();
void        anaconda_standalone_window_retranslate       (AnacondaStandaloneWindow *win);

G_END_DECLS

#endif
