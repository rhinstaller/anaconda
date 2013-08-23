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

/* based on an example by Ray Strode <rstrode@redhat.com> */

/**
 * SECTION: lightbox
 * @title: Lightbox
 * @short_description: Functions to draw a window over a shaded background
 *
 * The lightbox is a set of functions used to display one window (a dialog or
 * other similar window, typically) over top of the main window in the
 * background.  The main window is shaded out to make the foreground window
 * stand out more, as well as to reinforce to the user that the background
 * window may not be interacted with.
 */

#include <cairo.h>
#include <gdk/gdk.h>
#include <gtk/gtk.h>

#include "lightbox.h"

/* GObject ID for the parent window's configure-event signal handler */
#define ANACONDA_LB_PARENT_CONFIGURE_EVENT  "anaconda-configure-event"

static void anaconda_lb_move_window_to_parent(GtkWidget *parent,
                                              GdkEventConfigure *e,
                                              GtkWindow *window)
{
    GdkWindow *p_window, *w_window;
    int pwidth, pheight, width, height, px, py, x, y, nx, ny;

    if (!GTK_IS_WIDGET(parent) || !GTK_IS_WINDOW(window))
        return;

    p_window = gtk_widget_get_window (parent);
    w_window = gtk_widget_get_window (GTK_WIDGET(window));

    if (!GDK_IS_WINDOW(p_window) || !GDK_IS_WINDOW(w_window))
        return;

    pwidth = gdk_window_get_width (p_window);
    pheight = gdk_window_get_height (p_window);
    gdk_window_get_position(p_window, &px, &py);

    width = gdk_window_get_width (w_window);
    height = gdk_window_get_height (w_window);
    gdk_window_get_position(w_window, &x, &y);

    nx = px + pwidth / 2 - width / 2;
    ny = py + pheight / 2 - height / 2;

    if (x != nx || y != ny)
    {
        gdk_window_move (w_window, nx, ny);
        gdk_window_restack(w_window, p_window, TRUE);
    }

    g_object_set_data(G_OBJECT(window), ANACONDA_LB_PARENT_CONFIGURE_EVENT, NULL);
}

/**
 * anaconda_lb_show_over:
 * @window: (in) A #GtkWindow
 *
 * Show lightbox over window.
 *
 * Return value: (transfer none): the lightbox widget.
 *
 * Since: 1.0
 */
GtkWindow *anaconda_lb_show_over(GtkWindow *window)
{
    GtkWindow *lightbox;
    GdkWindow *w_window;
    GdkWindow *l_window;
    int width, height;
    cairo_t *cr;
    cairo_pattern_t *pattern;
    cairo_surface_t *surface;
    guint signal_handler;

    lightbox = (GTK_WINDOW(gtk_window_new(GTK_WINDOW_TOPLEVEL)));
    gtk_window_set_transient_for(lightbox, window);
    gtk_window_set_decorated(lightbox, FALSE);
    gtk_window_set_has_resize_grip(lightbox, FALSE);
    gtk_window_set_position(lightbox, GTK_WIN_POS_CENTER_ON_PARENT);
    gtk_window_set_type_hint (lightbox, GDK_WINDOW_TYPE_HINT_SPLASHSCREEN);
    gtk_widget_set_app_paintable(GTK_WIDGET(lightbox), TRUE);

    w_window = gtk_widget_get_window (GTK_WIDGET(window));
    width = gdk_window_get_width(w_window);
    height = gdk_window_get_height(w_window);
    gtk_window_set_default_size(lightbox, width, height);
    gtk_widget_realize(GTK_WIDGET(lightbox));
    l_window = gtk_widget_get_window (GTK_WIDGET(lightbox));
    gdk_window_set_background_pattern (l_window, NULL);
    gtk_widget_show(GTK_WIDGET(lightbox));
    surface = gdk_window_create_similar_surface(l_window,
                                                CAIRO_CONTENT_COLOR_ALPHA,
                                                width, height);

    cr = cairo_create (surface);
    gdk_cairo_set_source_window(cr, w_window, 0, 0);
    cairo_paint(cr);
    cairo_set_source_rgba(cr, 0.0, 0.0, 0.0, 0.5);
    cairo_paint(cr);
    cairo_destroy(cr);

    pattern = cairo_pattern_create_for_surface (surface);
    gdk_window_set_background_pattern(l_window, pattern);
    cairo_pattern_destroy (pattern);

    /* make the shade move with the parent window */
    signal_handler = g_signal_connect(window, "configure-event",
                     G_CALLBACK (anaconda_lb_move_window_to_parent), lightbox);

    /* Save the signal handler in the lightbox so we can remove it later */
    g_object_set_data(G_OBJECT(lightbox), ANACONDA_LB_PARENT_CONFIGURE_EVENT,
            GUINT_TO_POINTER(signal_handler));

    return lightbox;
}

/**
 * anaconda_lb_destroy:
 * @lightbox: a #GtkWindow
 *
 * Destroys the previously used lightbox.
 *
 * Since: 1.0
 */
void anaconda_lb_destroy(GtkWindow *lightbox)
{
    GtkWindow *window;
    gpointer p_signal_handler;

    /* Disconnect the configure-event from the contained window */
    if (GTK_IS_WINDOW(lightbox))
    {
        window = gtk_window_get_transient_for(GTK_WINDOW(lightbox));

        p_signal_handler = g_object_get_data(G_OBJECT(lightbox), 
                ANACONDA_LB_PARENT_CONFIGURE_EVENT);
        if ((NULL != p_signal_handler) && GTK_IS_WINDOW(window))
        {
            /* XXX HAAAAAAACK:
             * If the configure-event signal handler for the contained window
             * hasn't fired yet, do it now.
             */
            g_signal_emit_by_name(window, "configure-event", window);

            g_signal_handler_disconnect(window, GPOINTER_TO_UINT(p_signal_handler));
        }
    }

    gtk_widget_destroy(GTK_WIDGET(lightbox));
}
