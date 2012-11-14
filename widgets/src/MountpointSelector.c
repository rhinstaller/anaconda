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

#include <unistd.h>
#include <gdk/gdk.h>
#include <glib.h>
#include <glib/gstdio.h>

#include "MountpointSelector.h"
#include "intl.h"

/**
 * SECTION: MountpointSelector
 * @title: AnacondaMountpointSelector
 * @short_description: A graphical way to select a mount point.
 *
 * A #AnacondaMountpointSelector is a widget that appears on the custom partitioning
 * Mountpoint and allows the user to select a single mount point to do additional
 * configuration.
 *
 * As a #AnacondaMountpointSelector is a subclass of a #GtkEventBox, any signals
 * may be caught.  However ::button-press-event is the most important one and is
 * how we determine what should be displayed on the rest of the screen.
 */

enum {
    PROP_NAME = 1,
    PROP_SIZE,
    PROP_MOUNTPOINT
};

#define DEFAULT_NAME        N_("Root")
#define DEFAULT_SIZE        N_("0 GB")
#define DEFAULT_MOUNTPOINT  ""

struct _AnacondaMountpointSelectorPrivate {
    GtkWidget *grid;
    GtkWidget *name_label, *size_label, *mountpoint_label;
    GtkWidget *arrow;

    GdkCursor *cursor;

    gboolean   chosen;
};

G_DEFINE_TYPE(AnacondaMountpointSelector, anaconda_mountpoint_selector, GTK_TYPE_EVENT_BOX)

static void anaconda_mountpoint_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_mountpoint_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);

static void anaconda_mountpoint_selector_realize(GtkWidget *widget, gpointer user_data);
static void anaconda_mountpoint_selector_finalize(AnacondaMountpointSelector *widget);

static void     anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget);
static gboolean anaconda_mountpoint_selector_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data);

static void anaconda_mountpoint_selector_class_init(AnacondaMountpointSelectorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_mountpoint_selector_set_property;
    object_class->get_property = anaconda_mountpoint_selector_get_property;
    object_class->finalize = (GObjectFinalizeFunc) anaconda_mountpoint_selector_finalize;

    /**
     * AnacondaMountpointSelector:name:
     *
     * The :name string is the primary text displayed for a given mountpoint.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_NAME,
                                    g_param_spec_string("name",
                                                        P_("name"),
                                                        P_("Name display"),
                                                        DEFAULT_NAME,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaMountpointSelector:size:
     *
     * The :size string is the size of the mountpoint, including whatever units
     * it is measured in.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_SIZE,
                                    g_param_spec_string("size",
                                                        P_("size"),
                                                        P_("Size display"),
                                                        DEFAULT_SIZE,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaMountpointSelector:mountpoint:
     *
     * The :mountpoint string is where on the filesystem this is mounted.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_MOUNTPOINT,
                                    g_param_spec_string("mountpoint",
                                                        P_("mountpoint"),
                                                        P_("Mount point display"),
                                                        DEFAULT_MOUNTPOINT,
                                                        G_PARAM_READWRITE));

    g_type_class_add_private(object_class, sizeof(AnacondaMountpointSelectorPrivate));
}

/**
 * anaconda_mountpoint_selector_new:
 *
 * Creates a new #AnacondaMountpointSelector, which is a selectable display for a
 * single mountpoint.  Many mountpoints may be put together into a list, displaying
 * all configured filesystems at once.
 *
 * Returns: A new #AnacondaMountpointSelector.
 */
GtkWidget *anaconda_mountpoint_selector_new() {
    return g_object_new(ANACONDA_TYPE_MOUNTPOINT_SELECTOR, NULL);
}

static gchar *find_pixmap(const gchar *file) {
    const gchar *envvar;
    gchar **paths, **iterator = NULL;

    envvar = g_getenv("PIXMAPPATH");
    if (!envvar)
       envvar = g_strdup("/usr/share/anaconda/pixmaps");

    paths = g_strsplit(envvar, ":", 0);
    iterator = paths;

    while (*iterator != NULL) {
        gchar *path = g_strjoin("/", *iterator, file, NULL);

        if (!g_access(path, R_OK))
           return path;

        g_free(path);
        iterator++;
    }

    g_strfreev(paths);
    return NULL;
}

static void anaconda_mountpoint_selector_init(AnacondaMountpointSelector *mountpoint) {
    gchar *pixmap_path;
    char *markup;

    mountpoint->priv = G_TYPE_INSTANCE_GET_PRIVATE(mountpoint,
                                                   ANACONDA_TYPE_MOUNTPOINT_SELECTOR,
                                                   AnacondaMountpointSelectorPrivate);

    /* Allow tabbing from one MountpointSelector to the next, and make sure it's
     * selectable with the keyboard.
     */
    gtk_widget_set_can_focus(GTK_WIDGET(mountpoint), TRUE);
    gtk_widget_add_events(GTK_WIDGET(mountpoint), GDK_FOCUS_CHANGE_MASK|GDK_KEY_RELEASE_MASK);
    g_signal_connect(mountpoint, "focus-in-event", G_CALLBACK(anaconda_mountpoint_selector_focus_changed), NULL);
    g_signal_connect(mountpoint, "focus-out-event", G_CALLBACK(anaconda_mountpoint_selector_focus_changed), NULL);

    /* Set "hand" cursor shape when over the selector */
    mountpoint->priv->cursor = gdk_cursor_new(GDK_HAND2);
    g_signal_connect(mountpoint, "realize", G_CALLBACK(anaconda_mountpoint_selector_realize), NULL);

    /* Create the grid. */
    mountpoint->priv->grid = gtk_grid_new();
    gtk_grid_set_column_spacing(GTK_GRID(mountpoint->priv->grid), 12);
    gtk_widget_set_margin_left(GTK_WIDGET(mountpoint->priv->grid), 30);

    /* Create the icon.  We don't need to check if find_pixmap returned NULL
     * since gtk_image_new_from_file will just display a broken image icon in
     * that case.  That's good enough error notification.
     */
    pixmap_path = find_pixmap("right-arrow-icon.png");
    mountpoint->priv->arrow = gtk_image_new_from_file(pixmap_path);
    gtk_widget_set_no_show_all(GTK_WIDGET(mountpoint->priv->arrow), TRUE);
    g_free(pixmap_path);

    /* Set some properties. */
    mountpoint->priv->chosen = FALSE;

    /* Create the name label. */
    mountpoint->priv->name_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span fgcolor='black' size='large' weight='bold'>%s</span>", _(DEFAULT_NAME));
    gtk_label_set_markup(GTK_LABEL(mountpoint->priv->name_label), markup);
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->name_label), 0, 0);
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->name_label), TRUE);
    g_free(markup);

    /* Create the size label. */
    mountpoint->priv->size_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span fgcolor='black' size='large' weight='bold'>%s</span>", _(DEFAULT_SIZE));
    gtk_label_set_markup(GTK_LABEL(mountpoint->priv->size_label), markup);
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->size_label), 0, 0.5);
    g_free(markup);

    /* Create the mountpoint label. */
    mountpoint->priv->mountpoint_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span fgcolor='grey' size='small'>%s</span>", DEFAULT_MOUNTPOINT);
    gtk_label_set_markup(GTK_LABEL(mountpoint->priv->mountpoint_label), markup);
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->mountpoint_label), 0, 0);
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->mountpoint_label), TRUE);
    g_free(markup);

    /* Add everything to the grid, add the grid to the widget. */
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->name_label, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->size_label, 1, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->arrow, 2, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->mountpoint_label, 0, 1, 1, 2);
    gtk_widget_set_margin_right(GTK_WIDGET(mountpoint->priv->grid), 12);

    gtk_container_add(GTK_CONTAINER(mountpoint), mountpoint->priv->grid);
}

static void anaconda_mountpoint_selector_finalize(AnacondaMountpointSelector *widget) {
    g_object_unref(widget->priv->cursor);
}

static void anaconda_mountpoint_selector_realize(GtkWidget *widget, gpointer user_data) {
    AnacondaMountpointSelector *mountpoint = ANACONDA_MOUNTPOINT_SELECTOR(widget);

    gdk_window_set_cursor(gtk_widget_get_window(widget), mountpoint->priv->cursor);
}

static void anaconda_mountpoint_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);
    AnacondaMountpointSelectorPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_NAME:
           g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->name_label)));
           break;

        case PROP_SIZE:
           g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->size_label)));
           break;

        case PROP_MOUNTPOINT:
           g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->mountpoint_label)));
           break;
    }
}

static void anaconda_mountpoint_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);
    AnacondaMountpointSelectorPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_NAME: {
            char *markup = g_markup_printf_escaped("<span size='large' weight='bold'>%s</span>", g_value_get_string(value)); 
            gtk_label_set_markup(GTK_LABEL(priv->name_label), markup);
            g_free(markup);
            break;
        }

        case PROP_SIZE: {
            char *markup = g_markup_printf_escaped("<span size='large' weight='bold'>%s</span>", g_value_get_string(value)); 
            gtk_label_set_markup(GTK_LABEL(priv->size_label), markup);
            g_free(markup);
            break;
        }

        case PROP_MOUNTPOINT: {
            char *markup = g_markup_printf_escaped("<span size='small'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->mountpoint_label), markup);
            g_free(markup);
            break;
        }
    }
}

static gboolean anaconda_mountpoint_selector_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data) {
    GtkStateFlags new_state;

    new_state = gtk_widget_get_state_flags(widget) & ~GTK_STATE_FOCUSED;
    if (event->in) {
        gtk_widget_show(GTK_WIDGET(ANACONDA_MOUNTPOINT_SELECTOR(widget)->priv->arrow));
        new_state |= GTK_STATE_FOCUSED;
        anaconda_mountpoint_selector_set_chosen(ANACONDA_MOUNTPOINT_SELECTOR(widget), TRUE);
    }
    else {
        gtk_widget_hide(GTK_WIDGET(ANACONDA_MOUNTPOINT_SELECTOR(widget)->priv->arrow));
        anaconda_mountpoint_selector_set_chosen(ANACONDA_MOUNTPOINT_SELECTOR(widget), FALSE);
    }

    gtk_widget_set_state_flags(widget, new_state, TRUE);
    return FALSE;
}

static void anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget) {
    if (widget->priv->chosen) {
        gtk_widget_set_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED, FALSE);
        gtk_widget_override_color(GTK_WIDGET(widget->priv->mountpoint_label), GTK_STATE_FLAG_SELECTED, NULL);
    }
    else {
        GdkRGBA color;
        gtk_widget_unset_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED);
        gdk_rgba_parse(&color, "#555555");
        gtk_widget_override_color(GTK_WIDGET(widget->priv->mountpoint_label), GTK_STATE_FLAG_NORMAL, &color);
    }
}

/**
 * anaconda_mountpoint_selector_get_chosen:
 * @widget: a #AnacondaMountpointSelector
 *
 * Returns whether or not this mountpoint has been chosen by the user.
 *
 * Returns: Whether @widget has been chosen.
 *
 * Since: 1.0
 */
gboolean anaconda_mountpoint_selector_get_chosen(AnacondaMountpointSelector *widget) {
    return widget->priv->chosen;
}

/**
 * anaconda_mountpoint_selector_set_chosen:
 * @widget: a #AnacondaMountpointSelector
 * @is_chosen: %TRUE if this mountpoint is chosen.
 *
 * Specifies whether the mountpoint shown by this selector has been chosen by
 * the user.  If so, a special background will be set as a visual indicator.
 *
 * Since: 1.0
 */
void anaconda_mountpoint_selector_set_chosen(AnacondaMountpointSelector *widget, gboolean is_chosen) {
    widget->priv->chosen = is_chosen;
    anaconda_mountpoint_selector_toggle_background(widget);
    if (is_chosen)
        gtk_widget_grab_focus(GTK_WIDGET(widget));
}
