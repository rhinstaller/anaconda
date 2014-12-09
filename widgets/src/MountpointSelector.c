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

#include "config.h"

#include <unistd.h>
#include <gdk/gdk.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <pango/pango.h>
#include <gettext.h>

#include "MountpointSelector.h"
#include "intl.h"
#include "widgets-common.h"

/**
 * SECTION: MountpointSelector
 * @title: AnacondaMountpointSelector
 * @short_description: A graphical way to select a mount point.
 *
 * A #AnacondaMountpointSelector is a widget that appears on the custom partitioning
 * spoke and allows the user to select a single mount point to do additional
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

#define DEFAULT_NAME        ""
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
static void anaconda_mountpoint_selector_finalize(GObject *object);

static void anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget);

static void anaconda_mountpoint_selector_class_init(AnacondaMountpointSelectorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_mountpoint_selector_set_property;
    object_class->get_property = anaconda_mountpoint_selector_get_property;
    object_class->finalize = anaconda_mountpoint_selector_finalize;

    /**
     * AnacondaMountpointSelector:name:
     *
     * The :name string is the secondary text displayed for this widget.  It is
     * commonly going to be the name of the device node containing this
     * mountpoint.
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
     * The :mountpoint string is the primary text displayed for this widget.
     * It shows where on the filesystem this device is mounted.
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

static void format_mountpoint_label(AnacondaMountpointSelector *widget, const char *value) {
    char *markup;

    markup = g_markup_printf_escaped("<span fgcolor='black' size='large' weight='bold'>%s</span>", value);
    gtk_label_set_markup(GTK_LABEL(widget->priv->mountpoint_label), markup);
    g_free(markup);
}

static void format_size_label(AnacondaMountpointSelector *widget, const char *value) {
    char *markup;

    markup = g_markup_printf_escaped("<span fgcolor='black' size='large' weight='bold'>%s</span>", value);
    gtk_label_set_markup(GTK_LABEL(widget->priv->size_label), markup);
    g_free(markup);
}

static void format_name_label(AnacondaMountpointSelector *widget, const char *value) {
    char *markup;

    markup = g_markup_printf_escaped("<span fgcolor='black' size='small'>%s</span>", value);
    gtk_label_set_markup(GTK_LABEL(widget->priv->name_label), markup);
    g_free(markup);
}

static void anaconda_mountpoint_selector_init(AnacondaMountpointSelector *mountpoint) {
    gchar *file;

    mountpoint->priv = G_TYPE_INSTANCE_GET_PRIVATE(mountpoint,
                                                   ANACONDA_TYPE_MOUNTPOINT_SELECTOR,
                                                   AnacondaMountpointSelectorPrivate);

    /* Allow tabbing from one MountpointSelector to the next, and make sure it's
     * selectable with the keyboard.
     */
    gtk_widget_set_can_focus(GTK_WIDGET(mountpoint), TRUE);
    gtk_widget_add_events(GTK_WIDGET(mountpoint), GDK_FOCUS_CHANGE_MASK|GDK_KEY_RELEASE_MASK);

    /* Set "hand" cursor shape when over the selector */
    mountpoint->priv->cursor = gdk_cursor_new_for_display(gdk_display_get_default(), GDK_HAND2);
    g_signal_connect(mountpoint, "realize", G_CALLBACK(anaconda_mountpoint_selector_realize), NULL);

    /* Create the grid. */
    mountpoint->priv->grid = gtk_grid_new();
    gtk_grid_set_column_spacing(GTK_GRID(mountpoint->priv->grid), 12);
    gtk_widget_set_margin_start(GTK_WIDGET(mountpoint->priv->grid), 30);

    /* Create the icon.  We don't need to check if it returned NULL since
     * gtk_image_new_from_file will just display a broken image icon in that
     * case.  That's good enough error notification.
     */
    if (gtk_get_locale_direction() == GTK_TEXT_DIR_LTR)
        file = g_strdup_printf("%s/pixmaps/right-arrow-icon.png", anaconda_get_widgets_datadir());
    else
        file = g_strdup_printf("%s/pixmaps/left-arrow-icon.png", anaconda_get_widgets_datadir());
    mountpoint->priv->arrow = gtk_image_new_from_file(file);
    g_free(file);
    gtk_widget_set_no_show_all(GTK_WIDGET(mountpoint->priv->arrow), TRUE);

    /* Set some properties. */
    mountpoint->priv->chosen = FALSE;

    /* Create the name label. */
    mountpoint->priv->name_label = gtk_label_new(NULL);
    format_name_label(mountpoint, _(DEFAULT_NAME));
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    /* gtk+ did a garbage job of "deprecating" GtkMisc, so keep using it for now */
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->name_label), 0, 0);
G_GNUC_END_IGNORE_DEPRECATIONS
    gtk_label_set_ellipsize(GTK_LABEL(mountpoint->priv->name_label), PANGO_ELLIPSIZE_MIDDLE);
    gtk_label_set_max_width_chars(GTK_LABEL(mountpoint->priv->name_label), 25);
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->name_label), TRUE);

    /* Create the size label. */
    mountpoint->priv->size_label = gtk_label_new(NULL);
    format_size_label(mountpoint, _(DEFAULT_SIZE));
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->size_label), 0, 0.5);
G_GNUC_END_IGNORE_DEPRECATIONS

    /* Create the mountpoint label. */
    mountpoint->priv->mountpoint_label = gtk_label_new(NULL);
    format_mountpoint_label(mountpoint, DEFAULT_MOUNTPOINT);
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    gtk_misc_set_alignment(GTK_MISC(mountpoint->priv->mountpoint_label), 0, 0);
G_GNUC_END_IGNORE_DEPRECATIONS
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->mountpoint_label), TRUE);

    /* Add everything to the grid, add the grid to the widget. */
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->mountpoint_label, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->size_label, 1, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->arrow, 2, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->name_label, 0, 1, 1, 2);
    gtk_widget_set_margin_end(GTK_WIDGET(mountpoint->priv->grid), 12);

    gtk_container_add(GTK_CONTAINER(mountpoint), mountpoint->priv->grid);
}

static void anaconda_mountpoint_selector_finalize(GObject *object) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);
    g_object_unref(widget->priv->cursor);

    G_OBJECT_CLASS(anaconda_mountpoint_selector_parent_class)->finalize(object);
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

    switch(prop_id) {
        case PROP_NAME: {
            format_name_label(widget, g_value_get_string(value));
            break;
        }

        case PROP_SIZE: {
            format_size_label(widget, g_value_get_string(value));
            break;
        }

        case PROP_MOUNTPOINT: {
            format_mountpoint_label(widget, g_value_get_string(value));
            break;
        }
    }
}

static void anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget) {
    if (widget->priv->chosen) {
        gtk_widget_set_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED, FALSE);
    }
    else {
        gtk_widget_unset_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED);
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

    if (is_chosen) {
        gtk_widget_show(GTK_WIDGET(widget->priv->arrow));
        gtk_widget_grab_focus(GTK_WIDGET(widget));
    }
    else {
        gtk_widget_hide(GTK_WIDGET(widget->priv->arrow));
    }
}
