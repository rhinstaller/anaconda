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

#ifndef _SPOKE_WINDOW_H
#define _SPOKE_WINDOW_H

#include <gtk/gtk.h>

#include "BaseWindow.h"

G_BEGIN_DECLS

#define ANACONDA_TYPE_SPOKE_WINDOW              (anaconda_spoke_window_get_type())
#define ANACONDA_SPOKE_WINDOW(obj)              (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_SPOKE_WINDOW, AnacondaSpokeWindow))
#define ANACONDA_IS_SPOKE_WINDOW(obj)           (G_TYPE_CHECK_INSTANCE_TYPE ((obj), ANACONDA_TYPE_SPOKE_WINDOW))
#define ANACONDA_SPOKE_WINDOW_CLASS(klass)      (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_SPOKE_WINDOW, AnacondaSpokeWindowClass))
#define ANACONDA_IS_SPOKE_WINDOW_CLASS(klass)   (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_SPOKE_WINDOW))
#define ANACONDA_SPOKE_WINDOW_GET_CLASS(obj)    (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_SPOKE_WINDOW, AnacondaSpokeWindowClass))

typedef struct _AnacondaSpokeWindow          AnacondaSpokeWindow;
typedef struct _AnacondaSpokeWindowClass     AnacondaSpokeWindowClass;
typedef struct _AnacondaSpokeWindowPrivate   AnacondaSpokeWindowPrivate;

/**
 * AnacondaSpokeWindow:
 *
 * The AnacondaSpokeWindow struct contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaSpokeWindow {
    AnacondaBaseWindow           parent;

    /*< private >*/
    AnacondaSpokeWindowPrivate  *priv;
};

/**
 * AnacondaSpokeWindowClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows an AnacondaSpokeWindowClass
 *                pointer to be cast to an #AnacondaBaseWindow pointer.
 * @button_clicked: Function pointer called when the #AnacondaSpokeWindow::button-clicked
 *                  signal is emitted.
 */
struct _AnacondaSpokeWindowClass {
    AnacondaBaseWindowClass parent_class;

    void (* button_clicked)  (AnacondaSpokeWindow *window);
};

GType       anaconda_spoke_window_get_type (void);
GtkWidget  *anaconda_spoke_window_new      ();

G_END_DECLS

#endif
