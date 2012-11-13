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

#include <gdk/gdk.h>
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
    PROP_CAPACITY,
    PROP_OS,
    PROP_POPUP_INFO
};

/* Defaults for each property. */
#define DEFAULT_DESCRIPTION   N_("New Device")
#define DEFAULT_KIND          "drive-harddisk"
#define DEFAULT_CAPACITY      N_("0 MB")
#define DEFAULT_OS            ""
#define DEFAULT_POPUP_INFO    ""

#define ICON_SIZE             125

struct _AnacondaDiskOverviewPrivate {
    GtkWidget *vbox;
    GtkWidget *kind;
    GtkWidget *description_label;
    GtkWidget *capacity_label;
    GtkWidget *os_label;
    GtkWidget *tooltip;

    GdkCursor *cursor;

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
     * AnacondaDiskOverview:os:
     *
     * The :os string describes any operating system found on this device.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_OS,
                                    g_param_spec_string("os",
                                                        P_("Operating System"),
                                                        P_("Installed OS on this drive"),
                                                        DEFAULT_OS,
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

    /* Create the vbox. */
    widget->priv->vbox = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_container_set_border_width(GTK_CONTAINER(widget->priv->vbox), 6);

    /* Create the capacity label. */
    widget->priv->capacity_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span size='large'>%s</span>", _(DEFAULT_CAPACITY));
    gtk_label_set_markup(GTK_LABEL(widget->priv->capacity_label), markup);
    g_free(markup);

    /* Create the spoke's icon. */
    widget->priv->kind = gtk_image_new_from_icon_name(DEFAULT_KIND, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(widget->priv->kind), ICON_SIZE);

    /* Create the description label. */
    widget->priv->description_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", _(DEFAULT_DESCRIPTION));
    gtk_label_set_markup(GTK_LABEL(widget->priv->description_label), markup);
    g_free(markup);

    /* Create the OS label.  By default there is no operating system, so just
     * create a new label here so we have a place for later, should an OS be
     * specified.
     */
    widget->priv->os_label = gtk_label_new(NULL);

    /* Add everything to the vbox, add the vbox to the widget. */
    gtk_container_add(GTK_CONTAINER(widget->priv->vbox), widget->priv->capacity_label);
    gtk_container_add(GTK_CONTAINER(widget->priv->vbox), widget->priv->kind);
    gtk_container_add(GTK_CONTAINER(widget->priv->vbox), widget->priv->description_label);
    gtk_container_add(GTK_CONTAINER(widget->priv->vbox), widget->priv->os_label);

    gtk_container_add(GTK_CONTAINER(widget), widget->priv->vbox);

    /* We need to handle button-press-event in order to change the background color. */
    g_signal_connect(widget, "button-press-event", G_CALLBACK(anaconda_disk_overview_clicked), NULL);

    /* And this one is to handle when you select a DiskOverview via keyboard. */
    g_signal_connect(widget, "key-release-event", G_CALLBACK(anaconda_disk_overview_clicked), NULL);
}

gboolean anaconda_disk_overview_clicked(AnacondaDiskOverview *widget, GdkEvent *event) {
    /* This handler runs for mouse presses and key releases.  For key releases, it only
     * runs for activate-type keys (enter, space, etc.).
     */
    if (event->type == GDK_KEY_RELEASE &&
        (event->key.keyval != GDK_KEY_space && event->key.keyval != GDK_KEY_Return &&
         event->key.keyval != GDK_KEY_ISO_Enter && event->key.keyval != GDK_KEY_KP_Enter &&
         event->key.keyval != GDK_KEY_KP_Space))
        return FALSE;

    widget->priv->chosen = !widget->priv->chosen;
    anaconda_disk_overview_toggle_background(widget);
    return FALSE;
}

static void anaconda_disk_overview_toggle_background(AnacondaDiskOverview *widget) {
    if (widget->priv->chosen) {
	gtk_widget_set_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED, FALSE);
    }
    else
	gtk_widget_unset_state_flags(GTK_WIDGET(widget), GTK_STATE_FLAG_SELECTED);
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
            g_value_set_object (value, (GObject *)priv->kind);
            break;

        case PROP_CAPACITY:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->capacity_label)));
            break;

        case PROP_OS:
            g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->os_label)));
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
            gtk_image_set_from_icon_name(GTK_IMAGE(priv->kind), g_value_get_string(value), GTK_ICON_SIZE_DIALOG);
            gtk_image_set_pixel_size(GTK_IMAGE(priv->kind), ICON_SIZE);
            break;

        case PROP_CAPACITY: {
            char *markup = g_markup_printf_escaped("<span size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->capacity_label), markup);
            g_free(markup);
            break;
        }

        case PROP_OS: {
            /* If no OS is given, set the label to blank.  This will prevent
             * seeing a strange brown blob with no text in the middle of
             * nowhere.
             */
            if (!strcmp(g_value_get_string(value), ""))
               gtk_label_set_text(GTK_LABEL(priv->os_label), NULL);
            else {
                char *markup = g_markup_printf_escaped("<span foreground='white' background='brown'>%s</span>", g_value_get_string(value));
                gtk_label_set_markup(GTK_LABEL(priv->os_label), markup);
                g_free(markup);
                break;
            }
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
