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
    g_signal_connect(window, "configure-event",
                     G_CALLBACK (anaconda_lb_move_window_to_parent), lightbox);

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
    gtk_widget_destroy(GTK_WIDGET(lightbox));
}
