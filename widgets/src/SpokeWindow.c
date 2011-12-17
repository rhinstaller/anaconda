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

#include "BaseWindow.h"
#include "SpokeWindow.h"
#include "intl.h"

/**
 * SECTION: SpokeWindow
 * @title: AnacondaSpokeWindow
 * @short_description: Window for displaying single spokes
 *
 * A #AnacondaSpokeWindow is a top-level window that displays a single spoke
 * on the entire screen.  Examples include the keyboard and language
 * configuration screens off the first hub.
 *
 * The iwndow consists of two areas:
 *
 * - A navigation area in the top of the screen, inherited from #AnacondaBaseWindow
 *   and augmented with a back button.
 *
 * - An action area in the rest of the screen, taking up a majority of the
 *   space.  This is where widgets will be added and the user will do things.
 */

enum {
    SIGNAL_BACK_CLICKED,
    LAST_SIGNAL
};

static guint window_signals[LAST_SIGNAL] = { 0 };

struct _AnacondaSpokeWindowPrivate {
    GtkWidget  *back_button;
};

static void anaconda_spoke_window_back_clicked(GtkButton *button,
                                               AnacondaSpokeWindow *win);

G_DEFINE_TYPE(AnacondaSpokeWindow, anaconda_spoke_window, ANACONDA_TYPE_BASE_WINDOW)

static void anaconda_spoke_window_class_init(AnacondaSpokeWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    klass->back_clicked = NULL;

    /**
     * AnacondaSpokeWindow::back-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the back button has been activated (pressed and released).
     *
     * Since: 1.0
     */
    window_signals[SIGNAL_BACK_CLICKED] = g_signal_new("back-clicked",
                                                       G_TYPE_FROM_CLASS(object_class),
                                                       G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                       G_STRUCT_OFFSET(AnacondaSpokeWindowClass, back_clicked),
                                                       NULL, NULL,
                                                       g_cclosure_marshal_VOID__VOID,
                                                       G_TYPE_NONE, 0);

    g_type_class_add_private(object_class, sizeof(AnacondaSpokeWindowPrivate));
}

/**
 * anaconda_spoke_window_new:
 *
 * Creates a new #AnacondaSpokeWindow, which is a window designed for
 * displaying a single spoke, such as the keyboard or network configuration
 * screens.
 *
 * Returns: A new #AnacondaSpokeWindow.
 */
GtkWidget *anaconda_spoke_window_new() {
    return g_object_new(ANACONDA_TYPE_SPOKE_WINDOW, NULL);
}

static void anaconda_spoke_window_init(AnacondaSpokeWindow *win) {
    GtkWidget *nav_area;

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_SPOKE_WINDOW,
                                            AnacondaSpokeWindowPrivate);

    /* Set some default properties. */
    gtk_window_set_modal(GTK_WINDOW(win), TRUE);

    /* Create the buttons. */
    win->priv->back_button = gtk_button_new_with_mnemonic(_("_Back to install summary"));
    gtk_widget_set_halign(win->priv->back_button, GTK_ALIGN_START);

    /* Hook up some signals for that button.  The signal handlers here will
     * just raise our own custom signals for the whole window.
     */
    g_signal_connect(win->priv->back_button, "clicked",
                     G_CALLBACK(anaconda_spoke_window_back_clicked), win);

    /* And then put the back button into the navigation area. */
    nav_area = anaconda_base_window_get_nav_area(ANACONDA_BASE_WINDOW(win));
    gtk_grid_attach(GTK_GRID(nav_area), win->priv->back_button, 0, 1, 1, 1);
}

static void anaconda_spoke_window_back_clicked(GtkButton *button,
                                               AnacondaSpokeWindow *win) {
    g_signal_emit(win, window_signals[SIGNAL_BACK_CLICKED], 0);
}
