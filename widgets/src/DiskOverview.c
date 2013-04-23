/*
 * Copyright (C) 2011-2013  Red Hat, Inc.
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

#include <gdk/gdk.h>
#include <gio/gio.h>
#include <string.h>

#include "DiskOverview.h"
#include "intl.h"

/**
 * SECTION: DiskOverview
 * @title: AnacondaDiskOverview
 * @short_description: A widget that displays basic information about a disk
 *
 * A #AnacondaDiskOverview is a potentially selectable widget that displays a
 * disk device's size, kind, and a prominant icon based on the kind of device.
 * This widget can come in different sizes, depending on where it needs to be
 * used.
 *
 * As a #AnacondaDiskOverview is a subclass of a #GtkEventBox, any signals
 * may be caught.  The #GtkWidget::button-press-event signal is already
 * handled internally to change the background color, but may also be handled
 * by user code in order to take some action based on the disk clicked upon.
 */
enum {
    PROP_DESCRIPTION = 1,
    PROP_KIND,
    PROP_FREE,
    PROP_CAPACITY,
    PROP_NAME,
    PROP_POPUP_INFO
};

/* Defaults for each property. */
#define DEFAULT_DESCRIPTION   N_("New Device")
#define DEFAULT_KIND          "drive-harddisk"
#define DEFAULT_CAPACITY      N_("0 MB")
#define DEFAULT_FREE          N_("0 MB")
#define DEFAULT_NAME          ""
#define DEFAULT_POPUP_INFO    ""

#define ICON_SIZE             128

struct _AnacondaDiskOverviewPrivate {
    GtkWidget *grid;
    GtkWidget *kind_icon;
    GtkWidget *description_label;
    GtkWidget *capacity_label, *free_label;
    GtkWidget *name_label;
    GtkWidget *tooltip;

    GdkCursor *cursor;

    gchar *kind;
    gboolean chosen;
};

G_DEFINE_TYPE(AnacondaDiskOverview, anaconda_disk_overview, GTK_TYPE_EVENT_BOX)

gboolean anaconda_disk_overview_clicked(AnacondaDiskOverview *widget, GdkEvent *event);
static void anaconda_disk_overview_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_disk_overview_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_disk_overview_toggle_background(AnacondaDiskOverview *widget);

static void anaconda_disk_overview_realize(GtkWidget *widget, gpointer user_data);
static void anaconda_disk_overview_finalize(AnacondaDiskOverview *widget);

static gboolean anaconda_disk_overview_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data);

static void anaconda_disk_overview_class_init(AnacondaDiskOverviewClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_disk_overview_set_property;
    object_class->get_property = anaconda_disk_overview_get_property;
    object_class->finalize = (GObjectFinalizeFunc) anaconda_disk_overview_finalize;

    /**
     * AnacondaDiskOverview:kind:
     *
     * The :kind string specifies what type of disk device this is, used to
     * figure out what icon to be displayed.  This should be something like
     * "drive-harddisk", "drive-removable-media", etc.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_KIND,
                                    g_param_spec_string("kind",
                                                        P_("kind"),
                                                        P_("Drive kind icon"),
                                                        DEFAULT_KIND,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaDiskOverview:description:
     *
     * The :description string is a very basic description of the device
     * and is displayed in bold letters under the icon.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_DESCRIPTION,
                                    g_param_spec_string("description",
                                                        P_("Description"),
                                                        P_("The drive description"),
                                                        DEFAULT_DESCRIPTION,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaDiskOverview:capacity:
     *
     * The :capacity string is the total size of the disk, plus units.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_CAPACITY,
                                    g_param_spec_string("capacity",
                                                        P_("Capacity"),
                                                        P_("The drive size (including units)"),
                                                        DEFAULT_CAPACITY,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaDiskOverview:free:
     *
     * The :free string is the amount of free, unpartitioned space on the disk,
     * plus units.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_FREE,
                                    g_param_spec_string("free",
                                                        P_("Free space"),
                                                        P_("The drive's unpartitioned free space (including units)"),
                                                        DEFAULT_FREE,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaDiskOverview:name:
     *
     * The :name string provides this device's node name (like 'sda').  Note
     * that these names aren't guaranteed to be consistent across reboots but
     * their use is so ingrained that we need to continue displaying them.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_NAME,
                                    g_param_spec_string("name",
                                                        P_("Device node name"),
                                                        P_("Device node name"),
                                                        DEFAULT_NAME,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaDiskOverview:popup-info:
     *
     * The :popup-info string is text that should appear in a tooltip when the
     * #AnacondaDiskOverview is hovered over.  For normal disk devices, this
     * could be available space information.  For more complex devics, this
     * could be WWID, LUN, and so forth.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_POPUP_INFO,
                                    g_param_spec_string("popup-info",
                                                        P_("Detailed Disk Information"),
                                                        P_("Tooltip information for this drive"),
                                                        DEFAULT_POPUP_INFO,
                                                        G_PARAM_READWRITE));

    g_type_class_add_private(object_class, sizeof(AnacondaDiskOverviewPrivate));
}

/**
 * anaconda_disk_overview_new:
 *
 * Creates a new #AnacondaDiskOverview, which is a potentially selectable
 * widget that displays basic information about a single storage device, be
 * that a regular disk or a more complicated network device.
 *
 * Returns: A new #AnacondaDiskOverview.
 */
GtkWidget *anaconda_disk_overview_new() {
    return g_object_new(ANACONDA_TYPE_DISK_OVERVIEW, NULL);
}

static void set_icon(AnacondaDiskOverview *widget, const char *icon_name) {
    GError *err = NULL;
    GIcon *base_icon, *emblem_icon, *icon;
    GEmblem *emblem = NULL;

    if (!icon_name)
        return;

    if (widget->priv->kind_icon)
        gtk_widget_destroy(widget->priv->kind_icon);

    if (widget->priv->chosen) {
        base_icon = g_icon_new_for_string(icon_name, &err);
        if (!base_icon) {
            fprintf(stderr, "could not create icon: %s\n", err->message);
            g_error_free(err);
            return;
        }

        emblem_icon = g_icon_new_for_string("/usr/share/anaconda/pixmaps/anaconda-selected-icon.svg", &err);
        if (!emblem_icon) {
            fprintf(stderr, "could not create emblem: %s\n", err->message);
            g_error_free(err);
        }
        else {
            emblem = g_emblem_new(emblem_icon);
        }

        icon = g_emblemed_icon_new(base_icon, emblem);
        g_object_unref(base_icon);
    }
    else {
        icon = g_icon_new_for_string(icon_name, &err);
        if (!icon) {
            fprintf(stderr, "could not create icon: %s\n", err->message);
            g_error_free(err);
            return;
        }
    }

    widget->priv->kind_icon = gtk_image_new_from_gicon(icon, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(widget->priv->kind_icon), ICON_SIZE);
}

/* Initialize the widgets in a newly allocated DiskOverview. */
static void anaconda_disk_overview_init(AnacondaDiskOverview *widget) {
    char *markup;

    widget->priv = G_TYPE_INSTANCE_GET_PRIVATE(widget,
                                               ANACONDA_TYPE_DISK_OVERVIEW,
                                               AnacondaDiskOverviewPrivate);
    gtk_widget_set_valign(GTK_WIDGET(widget), GTK_ALIGN_CENTER);

    /* Allow tabbing from one DiskOverview to the next. */
    gtk_widget_set_can_focus(GTK_WIDGET(widget), TRUE);
    gtk_widget_add_events(GTK_WIDGET(widget), GDK_FOCUS_CHANGE_MASK|GDK_KEY_RELEASE_MASK);
    g_signal_connect(widget, "focus-in-event", G_CALLBACK(anaconda_disk_overview_focus_changed), NULL);
    g_signal_connect(widget, "focus-out-event", G_CALLBACK(anaconda_disk_overview_focus_changed), NULL);

    /* Set "hand" cursor shape when over the selector */
    widget->priv->cursor = gdk_cursor_new(GDK_HAND2);
    g_signal_connect(widget, "realize", G_CALLBACK(anaconda_disk_overview_realize), NULL);

    /* Set some properties. */
    widget->priv->chosen = FALSE;

    /* Create the grid. */
    widget->priv->grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(widget->priv->grid), 6);
    gtk_grid_set_column_spacing(GTK_GRID(widget->priv->grid), 6);
    gtk_container_set_border_width(GTK_CONTAINER(widget->priv->grid), 6);

    /* Create the capacity label. */
    widget->priv->capacity_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span size='large'>%s</span>", _(DEFAULT_CAPACITY));
    gtk_label_set_markup(GTK_LABEL(widget->priv->capacity_label), markup);
    g_free(markup);

    /* Create the spoke's icon. */
    set_icon(widget, DEFAULT_KIND);

    /* Create the description label. */
    widget->priv->description_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", _(DEFAULT_DESCRIPTION));
    gtk_label_set_markup(GTK_LABEL(widget->priv->description_label), markup);
    g_free(markup);

    /* Create the name label. */
    widget->priv->name_label = gtk_label_new(NULL);
    gtk_widget_set_halign(widget->priv->name_label, GTK_ALIGN_END);

    /* Create the free space label. */
    widget->priv->free_label = gtk_label_new(NULL);
    gtk_widget_set_halign(widget->priv->free_label, GTK_ALIGN_START);
    markup = g_markup_printf_escaped("<span size='large'>%s</span>", _(DEFAULT_FREE));
    gtk_label_set_markup(GTK_LABEL(widget->priv->capacity_label), markup);
    g_free(markup);

    /* Add everything to the grid, add the grid to the widget. */
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->capacity_label, 0, 0, 3, 1);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->kind_icon, 0, 1, 3, 1);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->description_label, 0, 2, 3, 1);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->name_label, 0, 3, 1, 1);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), gtk_label_new("/"), 1, 3, 1, 1);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->free_label, 2, 3, 1, 1);

    gtk_container_add(GTK_CONTAINER(widget), widget->priv->grid);

    /* We need to handle button-press-event in order to change the background color. */
    g_signal_connect(widget, "button-press-event", G_CALLBACK(anaconda_disk_overview_clicked), NULL);

    /* And this one is to handle when you select a DiskOverview via keyboard. */
    g_signal_connect(widget, "key-release-event", G_CALLBACK(anaconda_disk_overview_clicked), NULL);
}

gboolean anaconda_disk_overview_clicked(AnacondaDiskOverview *widget, GdkEvent *event) {
    /* This handler runs for mouse presses and key releases.  For key releases, it only
     * runs for activate-type keys (enter, space, etc.).
     */
    gtk_widget_grab_focus(GTK_WIDGET(widget));
    if (event->type != GDK_BUTTON_PRESS && event->type != GDK_KEY_RELEASE)
        return FALSE;
    else if (event->type == GDK_KEY_RELEASE &&
        (event->key.keyval != GDK_KEY_space && event->key.keyval != GDK_KEY_Return &&
         event->key.keyval != GDK_KEY_ISO_Enter && event->key.keyval != GDK_KEY_KP_Enter &&
         event->key.keyval != GDK_KEY_KP_Space))
        return FALSE;

    widget->priv->chosen = !widget->priv->chosen;
    anaconda_disk_overview_toggle_background(widget);
    return FALSE;
}

static void anaconda_disk_overview_toggle_background(AnacondaDiskOverview *widget) {
    set_icon(widget, widget->priv->kind);
    gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->kind_icon, 0, 1, 3, 1);
    gtk_widget_show(widget->priv->kind_icon);
}

static void anaconda_disk_overview_finalize(AnacondaDiskOverview *widget) {
    g_object_unref(widget->priv->cursor);
}

static void anaconda_disk_overview_realize(GtkWidget *widget, gpointer user_data) {
    AnacondaDiskOverview *overview = ANACONDA_DISK_OVERVIEW(widget);

    gdk_window_set_cursor(gtk_widget_get_window(widget), overview->priv->cursor);
}

static void anaconda_disk_overview_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaDiskOverview *widget = ANACONDA_DISK_OVERVIEW(object);
    AnacondaDiskOverviewPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_DESCRIPTION:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->description_label)));
            break;

        case PROP_KIND:
            g_value_set_object (value, (GObject *)priv->kind_icon);
            break;

        case PROP_FREE:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->free_label)));
            break;

        case PROP_CAPACITY:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->capacity_label)));
            break;

        case PROP_NAME:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->name_label)));
            break;

        case PROP_POPUP_INFO:
            g_value_set_string (value, gtk_widget_get_tooltip_text(GTK_WIDGET(widget)));
            break;
    }
}

static void anaconda_disk_overview_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaDiskOverview *widget = ANACONDA_DISK_OVERVIEW(object);
    AnacondaDiskOverviewPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_DESCRIPTION: {
            char *markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->description_label), markup);
            g_free(markup);
            break;
        }

        case PROP_KIND:
            if (widget->priv->kind)
                g_free(widget->priv->kind);

            widget->priv->kind = g_strdup(g_value_get_string(value));
            set_icon(widget, widget->priv->kind);
            gtk_grid_attach(GTK_GRID(widget->priv->grid), widget->priv->kind_icon, 0, 1, 3, 1);
            break;

        case PROP_FREE: {
            char *markup = g_markup_printf_escaped("<span size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->free_label), markup);
            g_free(markup);
            break;
        }

        case PROP_CAPACITY: {
            char *markup = g_markup_printf_escaped("<span size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->capacity_label), markup);
            g_free(markup);
            break;
        }

        case PROP_NAME: {
            char *markup = g_markup_printf_escaped("<span size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->name_label), markup);
            g_free(markup);
            break;
        }

        case PROP_POPUP_INFO: {
            if (!strcmp(g_value_get_string(value), ""))
                gtk_widget_set_has_tooltip(GTK_WIDGET(widget), FALSE);
            else {
                gtk_widget_set_tooltip_text(GTK_WIDGET(widget), g_value_get_string(value));
                break;
            }
        }
    }
}

/**
 * anaconda_disk_overview_get_chosen:
 * @widget: a #AnacondaDiskOverview
 *
 * Returns whether or not this disk has been chosen by the user.
 *
 * Returns: Whether @widget has been chosen.
 *
 * Since: 1.0
 */
gboolean anaconda_disk_overview_get_chosen(AnacondaDiskOverview *widget) {
    return widget->priv->chosen;
}

/**
 * anaconda_disk_overview_set_chosen:
 * @widget: a #AnacondaDiskOverview
 * @is_chosen: %TRUE if this disk is chosen.
 *
 * Specifies whether the disk shown by this overview has been chosen by
 * the user for inclusion in installation.  If so, a special background will
 * be set as a visual indicator.
 *
 * Since: 1.0
 */
void anaconda_disk_overview_set_chosen(AnacondaDiskOverview *widget, gboolean is_chosen) {
    widget->priv->chosen = is_chosen;
    anaconda_disk_overview_toggle_background(widget);
}

static gboolean anaconda_disk_overview_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data) {
    GtkStateFlags new_state;

    new_state = gtk_widget_get_state_flags(widget) & ~GTK_STATE_FOCUSED;
    if (event->in)
        new_state |= GTK_STATE_FOCUSED;
    gtk_widget_set_state_flags(widget, new_state, TRUE);

    return FALSE;
}
