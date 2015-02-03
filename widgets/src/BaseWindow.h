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

#ifndef _BASE_WINDOW_H
#define _BASE_WINDOW_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_BASE_WINDOW            (anaconda_base_window_get_type())
#define ANACONDA_BASE_WINDOW(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_BASE_WINDOW, AnacondaBaseWindow))
#define ANACONDA_IS_BASE_WINDOW(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), ANACONDA_TYPE_BASE_WINDOW))
#define ANACONDA_BASE_WINDOW_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_BASE_WINDOW, AnacondaBaseWindowClass))
#define ANACONDA_IS_BASE_WINDOW_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_BASE_WINDOW))
#define ANACONDA_BASE_WINDOW_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_BASE_WINDOW, AnacondaBaseWindowClass))

typedef struct _AnacondaBaseWindow        AnacondaBaseWindow;
typedef struct _AnacondaBaseWindowClass   AnacondaBaseWindowClass;
typedef struct _AnacondaBaseWindowPrivate AnacondaBaseWindowPrivate;

/**
 * AnacondaBaseWindow:
 *
 * The AnacondaBaseWindow struct contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaBaseWindow {
    GtkBin                     parent;

    /*< private >*/
    AnacondaBaseWindowPrivate *priv;
};

/**
 * AnacondaBaseWindowClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows a AnacondaBaseWindowClass
 *                pointer to be cast to a #GtkBin pointer.
 * @info_bar_clicked : Function pointer called when the #AnacondaBaseWindow::info-bar-clicked
 *                     signal is emitted.
 * @help_button_clicked: Function pointer called when the #AnacondaBaseWindow::help-button-clicked
 *                       signal is emitted.
 */
struct _AnacondaBaseWindowClass {
    GtkBinClass parent_class;

    void (* info_bar_clicked) (AnacondaBaseWindow *window);
    void (* help_button_clicked) (AnacondaBaseWindow *window);
};

GType       anaconda_base_window_get_type (void);
GtkWidget  *anaconda_base_window_new      ();

void        anaconda_base_window_retranslate (AnacondaBaseWindow *win);

gboolean    anaconda_base_window_get_beta (AnacondaBaseWindow *win);
void        anaconda_base_window_set_beta (AnacondaBaseWindow *win, gboolean is_beta);

void        anaconda_base_window_set_error   (AnacondaBaseWindow *win, const char *msg);
void        anaconda_base_window_set_info    (AnacondaBaseWindow *win, const char *msg);
void        anaconda_base_window_set_warning (AnacondaBaseWindow *win, const char *msg);
void        anaconda_base_window_clear_info  (AnacondaBaseWindow *win);

GtkWidget  *anaconda_base_window_get_action_area   (AnacondaBaseWindow *win);
GtkWidget  *anaconda_base_window_get_alignment     (AnacondaBaseWindow *win);
GtkWidget  *anaconda_base_window_get_main_box      (AnacondaBaseWindow *win);
GtkWidget  *anaconda_base_window_get_nav_area      (AnacondaBaseWindow *win);
GtkWidget  *anaconda_base_window_get_nav_area_background_window (AnacondaBaseWindow *win);
GtkWidget  *anaconda_base_window_get_help_button (AnacondaBaseWindow *win);

G_END_DECLS

#endif
