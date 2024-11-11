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
 * SECTION: AnacondaMountpointSelector
 * @title: AnacondaMountpointSelector
 * @short_description: A graphical way to select a mount point.
 *
 * A #AnacondaMountpointSelector is a widget that appears on the custom partitioning
 * spoke and allows the user to select a single mount point to do additional
 * configuration.
 *
 * As a #AnacondaMountpointSelector is a subclass of a #GtkEventBox, any signals
 * may be caught.  However #GtkWidget::button-press-event is the most important
 * one and is how we determine what should be displayed on the rest of the
 * screen.
 *
 * # CSS nodes
 *
 * |[<!-- language="plain" -->
 * AnacondaMountpointSelector
 * ├── #anaconda-mountpoint-label
 * ├── #anaconda-mountpoint-size-label
 * ├── #anaconda-mountpoint-arrow
 * ╰── #anaconda-mountpoint-name-label
 * ]|
 *
 * The internal widgets are accessible by name for the purposes of CSS
 * selectors
 *
 * - anaconda-mountpoint-name-label
 *
 *   The name of the mountpoint (e.g., /boot, /home, swap).
 *
 * - anaconda-mountpoint-size-label
 *
 *   The size of the mountpoint.
 *
 * - anaconda-mountpoint-arrow
 *
 *   The arrow image displayed on the selected mountpoint.
 *
 * - anaconda-mountpoint-name-label
 *
 *   The secondary text displayed for the mountpoint. This is commonly the
 *   name of the device node containing the mountpoint.
 */

enum {
    PROP_NAME = 1,
    PROP_SIZE,
    PROP_MOUNTPOINT,
    PROP_SHOW_ARROW
};

#define DEFAULT_NAME        ""
#define DEFAULT_SIZE        N_("0 GB")
#define DEFAULT_MOUNTPOINT  ""
#define DEFAULT_SHOW_ARROW  TRUE

struct _AnacondaMountpointSelectorPrivate {
    GtkWidget *grid;
    GtkWidget *name_label, *size_label, *mountpoint_label;
    GtkWidget *arrow;

    GdkCursor *cursor;

    gboolean   chosen;
    gboolean   show_arrow;
    GtkWidget *parent_page;
};

static guint chosen_changed_signal = 0;

G_DEFINE_TYPE(AnacondaMountpointSelector, anaconda_mountpoint_selector, GTK_TYPE_EVENT_BOX);

static void anaconda_mountpoint_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_mountpoint_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);

static void anaconda_mountpoint_selector_realize(GtkWidget *widget, gpointer user_data);
static void anaconda_mountpoint_selector_finalize(GObject *object);

static void anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget);

static void anaconda_mountpoint_selector_class_init(AnacondaMountpointSelectorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);
    GtkWidgetClass *widget_class = GTK_WIDGET_CLASS(klass);

    object_class->set_property = anaconda_mountpoint_selector_set_property;
    object_class->get_property = anaconda_mountpoint_selector_get_property;
    object_class->finalize = anaconda_mountpoint_selector_finalize;

    /**
     * AnacondaMountpointSelector:name:
     *
     * The #AnacondaMountpointSelector:name string is the secondary text displayed for this widget.  It is
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
     * The #AnacondaMountpointSelector:size string is the size of the mountpoint, including whatever units
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
     * The #AnacondaMountpointSelector:mountpoint string is the primary text displayed for this widget.
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

    /**
     * AnacondaMountpointSelector:show-arrow:
     *
     * The #AnacondaMountpointSelector:show-arrow boolean is used when arrow on the left should
     * or shouldn't be visible.
     *
     * Since: 3.4
     */
    g_object_class_install_property(object_class,
                                    PROP_SHOW_ARROW,
                                    g_param_spec_boolean("show-arrow",
                                                        P_("show-arrow"),
                                                        P_("Show arrow when selected"),
                                                        DEFAULT_SHOW_ARROW,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaMountpointSelector::chosen-changed:
     *
     * The #AnacondaMountpointSelector:chosen-changed signals when set_chosen is called.
     *
     * Since: 3.4
     */
    chosen_changed_signal = g_signal_newv("chosen-changed", // name
                                          G_TYPE_FROM_CLASS(object_class), // type
                                          G_SIGNAL_RUN_LAST | G_SIGNAL_NO_RECURSE | G_SIGNAL_NO_HOOKS, // flags
                                          NULL,             // class closure
                                          NULL,             // accumulator
                                          NULL,             // accumulator user data
                                          NULL,             // c_marshaller
                                          G_TYPE_NONE,      // return type
                                          0,                // length of the parameter type array
                                          NULL);            // array of types, one for each parameter

    g_type_class_add_private(object_class, sizeof(AnacondaMountpointSelectorPrivate));

    gtk_widget_class_set_css_name(widget_class, "AnacondaMountpointSelector");
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

static void anaconda_mountpoint_selector_init(AnacondaMountpointSelector *mountpoint) {
    GtkStyleContext *context;
    GError *err = NULL;
    GdkPixbuf *pixbuf = NULL;

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

    /* Create the icon. Unfortunately, function gtk_image_new_from_resource does not
     * work for some reason, so we should use gdk_pixbuf_new_from_resource instead.
     */
    if (gtk_get_locale_direction() == GTK_TEXT_DIR_LTR)
        pixbuf = gdk_pixbuf_new_from_resource(ANACONDA_RESOURCE_PATH "right-arrow-icon.png", &err);
    else
        pixbuf = gdk_pixbuf_new_from_resource(ANACONDA_RESOURCE_PATH "left-arrow-icon.png", &err);

    if (!pixbuf) {
        fprintf(stderr, "could not create icon: %s\n", err->message);
        g_error_free(err);
    }
    else {
        mountpoint->priv->arrow = gtk_image_new_from_pixbuf(pixbuf);
        g_object_unref(pixbuf);
    }

    gtk_widget_set_no_show_all(GTK_WIDGET(mountpoint->priv->arrow), TRUE);
    gtk_widget_set_name(mountpoint->priv->arrow, "anaconda-mountpoint-arrow");

    /* Set some properties. */
    mountpoint->priv->chosen = FALSE;

    /* Create the name label. */
    mountpoint->priv->name_label = gtk_label_new(_(DEFAULT_NAME));
    gtk_label_set_xalign(GTK_LABEL(mountpoint->priv->name_label), 0.0);
    gtk_label_set_yalign(GTK_LABEL(mountpoint->priv->name_label), 0.0);
    gtk_label_set_ellipsize(GTK_LABEL(mountpoint->priv->name_label), PANGO_ELLIPSIZE_MIDDLE);
    gtk_label_set_max_width_chars(GTK_LABEL(mountpoint->priv->name_label), 25);
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->name_label), TRUE);
    gtk_widget_set_name(mountpoint->priv->name_label, "anaconda-mountpoint-name-label");

    /* Create the size label. */
    mountpoint->priv->size_label = gtk_label_new(_(DEFAULT_SIZE));
    gtk_label_set_xalign(GTK_LABEL(mountpoint->priv->size_label), 0.0);
    gtk_label_set_yalign(GTK_LABEL(mountpoint->priv->size_label), 0.5);
    gtk_widget_set_name(mountpoint->priv->size_label, "anaconda-mountpoint-size-label");

    /* Create the mountpoint label. */
    mountpoint->priv->mountpoint_label = gtk_label_new(DEFAULT_MOUNTPOINT);
    gtk_label_set_xalign(GTK_LABEL(mountpoint->priv->mountpoint_label), 0.0);
    gtk_label_set_yalign(GTK_LABEL(mountpoint->priv->mountpoint_label), 0.0);
    gtk_widget_set_hexpand(GTK_WIDGET(mountpoint->priv->mountpoint_label), TRUE);
    gtk_widget_set_name(mountpoint->priv->mountpoint_label, "anaconda-mountpoint-label");

    /* Add everything to the grid, add the grid to the widget. */
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->mountpoint_label, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->size_label, 1, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->arrow, 2, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(mountpoint->priv->grid), mountpoint->priv->name_label, 0, 1, 1, 2);
    gtk_widget_set_margin_end(GTK_WIDGET(mountpoint->priv->grid), 12);

    /* Set the stylesheet data on child widgets that have it */
    anaconda_widget_apply_stylesheet(mountpoint->priv->mountpoint_label, "MountpointSelector-mountpoint");
    anaconda_widget_apply_stylesheet(mountpoint->priv->size_label, "MountpointSelector-size");
    anaconda_widget_apply_stylesheet(mountpoint->priv->name_label, "MountpointSelector-name");

    gtk_container_add(GTK_CONTAINER(mountpoint), mountpoint->priv->grid);

    /* Set NULL to parent_page while it's not set already */
    mountpoint->priv->parent_page = NULL;

    /* Apply the "fallback" style so that the widgets are colored correctly when
     * selected, insensitive, etc. */
    context = gtk_widget_get_style_context(GTK_WIDGET(mountpoint));
    gtk_style_context_add_class(context, "gtkstyle-fallback");
}

static void anaconda_mountpoint_selector_finalize(GObject *object) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);
    g_object_unref(widget->priv->cursor);
    g_object_unref(widget->priv->parent_page);

    G_OBJECT_CLASS(anaconda_mountpoint_selector_parent_class)->finalize(object);
}

static void anaconda_mountpoint_selector_realize(GtkWidget *widget, gpointer user_data) {
    AnacondaMountpointSelector *mountpoint = ANACONDA_MOUNTPOINT_SELECTOR(widget);

    gdk_window_set_cursor(gtk_widget_get_window(widget), mountpoint->priv->cursor);
}

static void anaconda_mountpoint_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);
    AnacondaMountpointSelectorPrivate *priv = widget->priv;

    switch (prop_id) {
        case PROP_NAME:
            g_value_set_string(value, gtk_label_get_text(GTK_LABEL(priv->name_label)));
            break;

        case PROP_SIZE:
            g_value_set_string(value, gtk_label_get_text(GTK_LABEL(priv->size_label)));
            break;

        case PROP_MOUNTPOINT:
            g_value_set_string(value, gtk_label_get_text(GTK_LABEL(priv->mountpoint_label)));
            break;

        case PROP_SHOW_ARROW:
            g_value_set_boolean(value, priv->show_arrow);
            break;

        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

static void anaconda_mountpoint_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaMountpointSelector *widget = ANACONDA_MOUNTPOINT_SELECTOR(object);

    switch (prop_id) {
        case PROP_NAME:
            gtk_label_set_text(GTK_LABEL(widget->priv->name_label), g_value_get_string(value));
            break;

        case PROP_SIZE:
            gtk_label_set_text(GTK_LABEL(widget->priv->size_label), g_value_get_string(value));
            break;

        case PROP_MOUNTPOINT:
            gtk_label_set_text(GTK_LABEL(widget->priv->mountpoint_label), g_value_get_string(value));
            break;

        case PROP_SHOW_ARROW:
            widget->priv->show_arrow = g_value_get_boolean(value);
            anaconda_mountpoint_selector_set_chosen(widget, widget->priv->chosen);
            break;

        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

static void anaconda_mountpoint_selector_toggle_background(AnacondaMountpointSelector *widget) {
    /* Copy state flag changes to the child labels so they can be used in CSS selectors */
    if (widget->priv->chosen) {
        gtk_widget_set_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED, FALSE);
        gtk_widget_set_state_flags(widget->priv->arrow, GTK_STATE_FLAG_SELECTED, FALSE);
        gtk_widget_set_state_flags(widget->priv->name_label, GTK_STATE_FLAG_SELECTED, FALSE);
        gtk_widget_set_state_flags(widget->priv->size_label, GTK_STATE_FLAG_SELECTED, FALSE);
        gtk_widget_set_state_flags(widget->priv->mountpoint_label, GTK_STATE_FLAG_SELECTED, FALSE);
    }
    else {
        gtk_widget_unset_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED);
        gtk_widget_unset_state_flags(widget->priv->arrow, GTK_STATE_FLAG_SELECTED);
        gtk_widget_unset_state_flags(widget->priv->name_label, GTK_STATE_FLAG_SELECTED);
        gtk_widget_unset_state_flags(widget->priv->size_label, GTK_STATE_FLAG_SELECTED);
        gtk_widget_unset_state_flags(widget->priv->mountpoint_label, GTK_STATE_FLAG_SELECTED);
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
        if (widget->priv->show_arrow)
            gtk_widget_show(GTK_WIDGET(widget->priv->arrow));
        else
            gtk_widget_hide(GTK_WIDGET(widget->priv->arrow));

        gtk_widget_grab_focus(GTK_WIDGET(widget));
    }
    else {
        gtk_widget_hide(GTK_WIDGET(widget->priv->arrow));
    }

    g_signal_emit(widget, chosen_changed_signal, 0);
}

/**
 * anaconda_mountpoint_selector_get_page:
 * @widget: a #AnacondaMountpointSelector
 *
 * Return pointer to Page where this #AnacondaMountpointSelector is contained.
 *
 * Returns: (transfer none): Pointer to GtkWidget page or #NONE.
 *
 * Since: 3.4
 */
GtkWidget *anaconda_mountpoint_selector_get_page(AnacondaMountpointSelector *widget) {
    return widget->priv->parent_page;
}

/**
 * anaconda_mountpoint_selector_set_page:
 * @widget: a #AnacondaMountpointSelector
 * @parent_page: Page object which owns this #AnacondaMountpointSelector
 *
 * Set a pointer to Page where this #AnacondaMountpointSelector is contained.
 *
 * Since: 3.4
 */
void anaconda_mountpoint_selector_set_page(AnacondaMountpointSelector *widget, GtkWidget *parent_page) {
    if (widget->priv->parent_page != NULL)
        g_object_unref(widget->priv->parent_page);

    widget->priv->parent_page = parent_page;

    if (parent_page != NULL)
        g_object_ref(widget->priv->parent_page);
}
