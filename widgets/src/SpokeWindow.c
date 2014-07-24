/*
 * Copyright (C) 2011-2014  Red Hat, Inc.
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

#include "config.h"

#include "BaseWindow.h"
#include "SpokeWindow.h"
#include "intl.h"
#include "widgets-common.h"

#include <atk/atk.h>
#include <gdk/gdkkeysyms.h>

/**
 * SECTION: SpokeWindow
 * @title: AnacondaSpokeWindow
 * @short_description: Window for displaying single spokes
 *
 * A #AnacondaSpokeWindow is a widget that displays a single spoke on the
 * screen.  Examples include the keyboard and language configuration screens
 * off the first hub.
 *
 * The AnacondaSpokeWindow consists of two areas:
 *
 * - A navigation area in the top of the screen, inherited from #AnacondaBaseWindow
 *   and augmented with a button in the upper left corner.
 *
 * - An action area in the rest of the screen, taking up a majority of the
 *   space.  This is where widgets will be added and the user will do things.
 */

#define DEFAULT_BUTTON_LABEL _("_Done")

enum {
    SIGNAL_BUTTON_CLICKED,
    LAST_SIGNAL
};

static guint window_signals[LAST_SIGNAL] = { 0 };

struct _AnacondaSpokeWindowPrivate {
    GtkWidget  *button;
};

G_DEFINE_TYPE(AnacondaSpokeWindow, anaconda_spoke_window, ANACONDA_TYPE_BASE_WINDOW)

static void anaconda_spoke_window_button_clicked(GtkButton *button,
                                                 AnacondaSpokeWindow *win);

static void anaconda_spoke_window_class_init(AnacondaSpokeWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    klass->button_clicked = NULL;

    /**
     * AnacondaSpokeWindow::button-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the button in the upper left corner has been activated
     * (pressed and released).  This is commonly the button that takes the user
     * back to the hub, but could do other things.  Note that we do not want
     * to trap people in spokes, so there should always be a way back to the
     * hub via this signal, even if it involves canceling some operation or
     * resetting things.
     *
     * Since: 1.0
     */
    window_signals[SIGNAL_BUTTON_CLICKED] = g_signal_new("button-clicked",
                                                         G_TYPE_FROM_CLASS(object_class),
                                                         G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                         G_STRUCT_OFFSET(AnacondaSpokeWindowClass, button_clicked),
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
    AtkObject *atk;
    GtkWidget *nav_area;
    GtkStyleContext *context;

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_SPOKE_WINDOW,
                                            AnacondaSpokeWindowPrivate);

    /* Create the button. */
    win->priv->button = gtk_button_new_with_mnemonic(DEFAULT_BUTTON_LABEL);
    gtk_widget_set_halign(win->priv->button, GTK_ALIGN_START);
    gtk_widget_set_vexpand(win->priv->button, FALSE);
    gtk_widget_set_valign(win->priv->button, GTK_ALIGN_END);
    gtk_widget_set_margin_bottom(win->priv->button, 6);

    atk = gtk_widget_get_accessible(win->priv->button);
    atk_object_set_name(atk, DEFAULT_BUTTON_LABEL);

    /* Set 'Done' button to blue 'suggested-action' style class */
    context = gtk_widget_get_style_context(win->priv->button);
    gtk_style_context_add_class(context, "suggested-action");

    /* Hook up some signals for that button.  The signal handlers here will
     * just raise our own custom signals for the whole window.
     */
    g_signal_connect(win->priv->button, "clicked",
                     G_CALLBACK(anaconda_spoke_window_button_clicked), win);

    /* And then put the button into the navigation area. */
    nav_area = anaconda_base_window_get_nav_area(ANACONDA_BASE_WINDOW(win));
    gtk_grid_attach(GTK_GRID(nav_area), win->priv->button, 0, 1, 1, 2);
}

static void anaconda_spoke_window_button_clicked(GtkButton *button,
                                                 AnacondaSpokeWindow *win) {
    g_signal_emit(win, window_signals[SIGNAL_BUTTON_CLICKED], 0);
}
