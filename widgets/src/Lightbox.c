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
 * SECTION: Lightbox
 * @title: Lightbox
 * @short_description: Functions to draw a window over a shaded background
 *
 * The lightbox is a widget used to display one window (a dialog or other
 * similar window, typically) over top of the main window in the background.
 * The main window is shaded out to make the foreground window stand out more,
 * as well as to reinforce to the user that the background window may not be
 * interacted with.
 *
 * The lightbox window will show as soon as it is created.
 */

/*
 * We have two methods for drawing the transparent background, depending
 * on whether we can use a compositing window manager for alpha blending
 * or not.
 *
 * In a compositing window manager (e.g., gnome-shell on the livecd), we
 * create the transparent background using Gtk by overriding the window's
 * background color and setting an opacity.
 *
 * In a non-compositing window manager (e.g., metacity on the install DVD),
 * we override Gtk's drawing of the widget entirely. We set paintable to
 * false to indicate that theme information should not be applied, and then
 * as the parent-window property is being set, we use cairo to paint a new
 * surface using the parent's Gdk window as the source pattern, apply a 50%
 * translucent fill to the surface, and then use this surface as the
 * background for the lightbox's Gdk window.
 */

#include <cairo.h>
#include <gtk/gtk.h>

#include "Lightbox.h"

#include "intl.h"

enum {
    PROP_PARENT_WINDOW = 1
};

struct _AnacondaLightboxPrivate {
    GtkWindow *transient_parent;
    gboolean   parent_configure_event_handler_set;
    guint      parent_configure_event_handler;

    gboolean   composited;
};

static void anaconda_lightbox_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_lightbox_set_parent_window(GObject *gobject, GParamSpec *psec, gpointer user_data);

static gboolean anaconda_lb_parent_configure_event(GtkWidget *parent, GdkEvent *event, gpointer lightbox);
static gboolean anaconda_lb_configure_event(GtkWidget *lightbox, GdkEvent *event, gpointer user_data);
static void anaconda_lb_cleanup(GtkWidget *widget, gpointer user_data);

G_DEFINE_TYPE(AnacondaLightbox, anaconda_lightbox, GTK_TYPE_WINDOW)

static void anaconda_lightbox_class_init(AnacondaLightboxClass *klass)
{
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_lightbox_set_property;

    /**
     * AnacondaLightbox:parent-window:
     *
     * The parent of this window. This value is used as the transient parent
     * for this window.
     *
     * Since: 2.0
     */
    g_object_class_install_property(object_class,
            PROP_PARENT_WINDOW,
            g_param_spec_object("parent-window",
                P_("Parent Window"),
                P_("The parent of this window"),
                GTK_TYPE_WINDOW,
                G_PARAM_WRITABLE | G_PARAM_CONSTRUCT_ONLY));

    g_type_class_add_private(object_class, sizeof(AnacondaLightboxPrivate));
}

static void anaconda_lightbox_init(AnacondaLightbox *lightbox)
{
    lightbox->priv = G_TYPE_INSTANCE_GET_PRIVATE(lightbox,
            ANACONDA_TYPE_LIGHTBOX,
            AnacondaLightboxPrivate
            );

    /* Disable the window decorations on the parent (Gtk.Window) class */
    gtk_container_set_border_width(GTK_CONTAINER(lightbox), 0);
    gtk_window_set_decorated(GTK_WINDOW(lightbox), FALSE);
    gtk_window_set_has_resize_grip(GTK_WINDOW(lightbox), FALSE);

    gtk_window_set_type_hint(GTK_WINDOW(lightbox), GDK_WINDOW_TYPE_HINT_SPLASHSCREEN);

    /* Decide now which background drawing method to use */
    lightbox->priv->composited = gtk_widget_is_composited(GTK_WIDGET(lightbox));
    if (lightbox->priv->composited)
    {
        GdkRGBA color = {0.0, 0.0, 0.0, 1.0};    /* opaque black */

        /* Set the background to black */
        gtk_widget_override_background_color(GTK_WIDGET(lightbox),
                GTK_STATE_FLAG_NORMAL,
                &color
                );

        /* Set the opacity to 50% */
        gtk_widget_set_opacity(GTK_WIDGET(lightbox), 0.5);
    }
    else
    {
        /*
         * Indicate we will handle drawing the widget, do the rest in
         * anaconda_lightbox_set_parent_window
         */
        gtk_widget_set_app_paintable(GTK_WIDGET(lightbox), TRUE);
    }

    /* handle restacking events */
    g_signal_connect(lightbox, "configure-event", G_CALLBACK(anaconda_lb_configure_event), NULL);

    /* cleanup */
    g_signal_connect(lightbox, "destroy", G_CALLBACK(anaconda_lb_cleanup), NULL);
}

static void anaconda_lightbox_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec)
{
    AnacondaLightbox *lightbox = ANACONDA_LIGHTBOX(object);
    AnacondaLightboxPrivate *priv = lightbox->priv;

    switch (prop_id)
    {
        case PROP_PARENT_WINDOW:
            priv->transient_parent = GTK_WINDOW(g_object_ref(g_value_get_object(value)));
            /* The property is CONSTRUCT_ONLY, so no point calling notify */
            anaconda_lightbox_set_parent_window(object, pspec, NULL);
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

/*
 * Adjust the lightbox any time the parent window's size, position or stacking
 * changes. Returns FALSE to allow signal processing to continue.
 */
static gboolean anaconda_lb_parent_configure_event(
        GtkWidget *parent,
        GdkEvent *event,
        gpointer lightbox
        )
{
    /* Always return FALSE to continue processing for this signal. */
    GdkWindow *g_parent_window;
    GdkWindow *g_lightbox_window;

    if ((event->type != GDK_CONFIGURE) ||
            !GTK_IS_WIDGET(parent) ||
            !GTK_IS_WINDOW(lightbox))
    {
        return FALSE;
    }

    g_lightbox_window = gtk_widget_get_window(GTK_WIDGET(lightbox));
    if (NULL == g_lightbox_window)
    {
        /*
         * No underlying GdkWindow. This may mean the lightbox is not yet
         * realized, but whatever the cause, there's nothing we can do here.
         */
        return FALSE;
    }

    /* Resize and move the window according to the event data */
    gdk_window_move_resize(g_lightbox_window,
            event->configure.x,
            event->configure.y,
            event->configure.width,
            event->configure.height
            );

    g_parent_window = gtk_widget_get_window(parent);
    if (NULL == g_parent_window)
    {
        return FALSE;
    }

    /* Stack the lightbox above the parent */
    gdk_window_restack(g_lightbox_window, g_parent_window, TRUE);

    return FALSE;
}


/*
 * Draw the window background. Uses the gobject notify handler signature
 * in case we want to allow parent-window to change in the future.
 */
static void anaconda_lightbox_set_parent_window(
        GObject *gobject,
        GParamSpec *psec,
        gpointer user_data
        )
{
    AnacondaLightbox *lightbox;

    GdkWindow *g_lightbox_window;
    GdkWindow *g_parent_window;
    cairo_surface_t *surface;
    cairo_pattern_t *pattern;
    cairo_t *cr;

    if (!ANACONDA_IS_LIGHTBOX(gobject))
    {
        return;
    }

    lightbox = ANACONDA_LIGHTBOX(gobject);

    /*
     * Skip the check for whether the value has changed, since we only allow
     * it to be set in the constructor
     */

    if (lightbox->priv->transient_parent)
    {
        gtk_window_set_transient_for(GTK_WINDOW(lightbox), lightbox->priv->transient_parent);

        /* Destroy the lightbox when the parent is destroyed */
        gtk_window_set_destroy_with_parent(GTK_WINDOW(lightbox), TRUE);

        /* Set the initial position to the center of the parent */
        gtk_window_set_position(GTK_WINDOW(lightbox), GTK_WIN_POS_CENTER_ON_PARENT);

        /* Set the lightbox to the parent window's dimensions */
        g_parent_window = gtk_widget_get_window(GTK_WIDGET(lightbox->priv->transient_parent));
        gtk_window_set_default_size(GTK_WINDOW(lightbox),
                gdk_window_get_width(g_parent_window),
                gdk_window_get_height(g_parent_window)
                );

        /* make the shade move with the parent window */
        /* Add a reference for the lightbox pointer held for the handler */
        g_object_ref(lightbox);
        lightbox->priv->parent_configure_event_handler =
            g_signal_connect(lightbox->priv->transient_parent, "configure-event",
                    G_CALLBACK(anaconda_lb_parent_configure_event), lightbox);
        lightbox->priv->parent_configure_event_handler_set = TRUE;

        /* Handle the non-compositing background case */
        if (!lightbox->priv->composited)
        {
            /*
             * NB: We should probably be handling the draw signal in order to refresh
             * the transparent pattern from the parent window whenver something
             * changes, but by the time things get to the signal handler the surface is
             * already set up and doesn't support alpha channels and replacing it
             * doesn't seem to work quite right. Besides, none of these windows are
             * supposed to move anyway.
             */

            /* Realize the window to initialize the Gdk objects */
            if (!gtk_widget_get_realized(GTK_WIDGET(lightbox)))
            {
                gtk_widget_realize(GTK_WIDGET(lightbox));
            }
            g_lightbox_window = gtk_widget_get_window(GTK_WIDGET(lightbox));

            /* Create a new surface that supports alpha content */
            surface = gdk_window_create_similar_surface(g_lightbox_window,
                    CAIRO_CONTENT_COLOR_ALPHA,
                    gdk_window_get_width(g_parent_window),
                    gdk_window_get_height(g_parent_window));
            cr = cairo_create(surface);

            /* Use the parent window as a pattern and paint it on the surface */
            gdk_cairo_set_source_window(cr, g_parent_window, 0, 0);
            cairo_paint(cr);

            /* Paint a black, 50% transparent shade */
            cairo_set_source_rgba(cr, 0.0, 0.0, 0.0, 0.5);
            cairo_paint(cr);

            cairo_destroy(cr);

            /* Use the surface we painted as the window background */
            pattern = cairo_pattern_create_for_surface(surface);
            gdk_window_set_background_pattern(g_lightbox_window, pattern);
            cairo_pattern_destroy(pattern);
        }
    }

    gtk_widget_show(GTK_WIDGET(lightbox));
}

/*
 * Restack the lightbox and its parent any time we receive a configure-event
 * on the lightbox
 */
static gboolean anaconda_lb_configure_event(
        GtkWidget *lightbox,
        GdkEvent *event,
        gpointer user_data
        )
{
    GtkWindow *parent;
    GdkWindow *g_parent_window;
    GdkWindow *g_lightbox_window;

    if ((event->type != GDK_CONFIGURE) || !ANACONDA_IS_LIGHTBOX(lightbox))
    {
        return FALSE;
    }

    parent = ANACONDA_LIGHTBOX(lightbox)->priv->transient_parent;
    if (!GTK_IS_WINDOW(parent))
    {
        return FALSE;
    }

    g_lightbox_window = gtk_widget_get_window(lightbox);
    if (NULL == g_lightbox_window)
    {
        return FALSE;
    }

    g_parent_window = gtk_widget_get_window(GTK_WIDGET(parent));
    if (NULL == g_parent_window)
    {
        return FALSE;
    }

    gdk_window_restack(g_lightbox_window, g_parent_window, TRUE);
    return FALSE;
}

/* Clean up references to lightbox held by the parent window */
static void anaconda_lb_cleanup(GtkWidget *widget, gpointer user_data)
{
    AnacondaLightbox *lightbox;

    /* Remove the signal handlers set on the parent window */
    if (ANACONDA_IS_LIGHTBOX(widget))
    {
        lightbox = ANACONDA_LIGHTBOX(widget);

        if (lightbox->priv->parent_configure_event_handler_set)
        {
            g_signal_handler_disconnect(lightbox->priv->transient_parent,
                    lightbox->priv->parent_configure_event_handler);
            lightbox->priv->parent_configure_event_handler_set = FALSE;
            g_object_unref(lightbox);
        }

        /* Drop the reference for the parent window */
        g_object_unref(lightbox->priv->transient_parent);
        lightbox->priv->transient_parent = NULL;
    }
}

/**
 * anaconda_lightbox_new:
 * @parent: The parent for this window
 *
 * Creates a new #AnacondaLightbox, which is a top-level, undecorated window
 * that uses a shaded version of its parent window's background as its own
 * background.
 *
 * Returns: the new lightbox as a #GtkWidget
 */
GtkWidget* anaconda_lightbox_new(GtkWindow *parent)
{
    AnacondaLightbox *lightbox;

    lightbox = ANACONDA_LIGHTBOX(g_object_new(ANACONDA_TYPE_LIGHTBOX,
                "parent-window", parent,
                NULL));

    return GTK_WIDGET(lightbox);
}
