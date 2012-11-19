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

#include <gdk/gdk.h>
#include <glib.h>
#include <pango/pango.h>

#include "SpokeSelector.h"
#include "intl.h"

/**
 * SECTION: SpokeSelector
 * @title: AnacondaSpokeSelector
 * @short_description: A graphical way to enter a configuration spoke
 *
 * A #AnacondaSpokeSelector is a widget that is associated with a Spoke and
 * is packed into a grid on a Hub.  A Spoke allows the user to configure one
 * piece of system, and the associated selector both displays the current
 * configuration and allows for a place to click to do further configuration.
 *
 * Some Spokes can have their initial configuration guessed, while others
 * (specifically storage) requires the user to do something.  For those that
 * the user has not entered, the selector may be set as incomplete.  See
 * #anaconda_spoke_selector_get_incomplete and #anaconda_spoke_selector_set_incomplete.
 *
 * As a #AnacondaSpokeSelector is a subclass of a #GtkEventBox, any signals
 * may be caught.  However ::button-press-event is the most important one and
 * should be how control is transferred to a Spoke.
 */

enum {
    PROP_ICON = 1,
    PROP_STATUS,
    PROP_TITLE,
};

#define DEFAULT_ICON    "gtk-missing-image"
#define DEFAULT_STATUS  N_("None")
#define DEFAULT_TITLE   N_("New Selector")

struct _AnacondaSpokeSelectorPrivate {
    gboolean   is_incomplete;
    GtkWidget *grid;
    GtkWidget *icon, *incomplete_icon;
    GtkWidget *title_label;
    GtkWidget *status_label;
    GdkCursor *cursor;

    GtkCssProvider *status_provider;
};

G_DEFINE_TYPE(AnacondaSpokeSelector, anaconda_spoke_selector, GTK_TYPE_EVENT_BOX)

static void anaconda_spoke_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_spoke_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_spoke_selector_realize(GtkWidget *widget, gpointer user_data);
static void anaconda_spoke_selector_finalize(AnacondaSpokeSelector *spoke);

static gboolean anaconda_spoke_selector_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data);

static void anaconda_spoke_selector_class_init(AnacondaSpokeSelectorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_spoke_selector_set_property;
    object_class->get_property = anaconda_spoke_selector_get_property;
    object_class->finalize = (GObjectFinalizeFunc) anaconda_spoke_selector_finalize;

    /**
     * AnacondaSpokeSelector:icon:
     *
     * The :icon string is the standard icon name for an icon to display
     * beside this spoke's :title.  It is strongly suggested that one of the
     * "-symbolic" icons be used, as that is consistent with the style we
     * are going for.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_ICON,
                                    g_param_spec_string("icon",
                                                        P_("Icon"),
                                                        P_("Icon to appear next to the title"),
                                                        DEFAULT_ICON,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaSpokeSelector:status:
     *
     * The :status string is text displayed underneath the spoke's :title and
     * also beside the :icon.  This text very briefly describes what has been
     * selected on the spoke associated with this selector.  For instance, it
     * might be set up to "English" for a language-related spoke.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_STATUS,
                                    g_param_spec_string("status",
                                                        P_("Status"),
                                                        P_("Status display"),
                                                        DEFAULT_STATUS,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaSpokeSelector:title:
     *
     * The :title of this selector, which will be displayed large and bold
     * beside the :icon.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_TITLE,
                                    g_param_spec_string("title",
                                                        P_("Title"),
                                                        P_("The title of the spoke selector"),
                                                        DEFAULT_TITLE,
                                                        G_PARAM_READWRITE));

    g_type_class_add_private(object_class, sizeof(AnacondaSpokeSelectorPrivate));
}

/**
 * anaconda_spoke_selector_new:
 *
 * Creates a new #AnacondaSpokeSelector, which is a selectable display for a
 * single spoke of an Anaconda hub.  Many spokes may be put together into a
 * grid, displaying everything that a user needs to do in one place.
 *
 * Returns: A new #AnacondaSpokeSelector.
 */
GtkWidget *anaconda_spoke_selector_new() {
    return g_object_new(ANACONDA_TYPE_SPOKE_SELECTOR, NULL);
}

static void format_status_label(AnacondaSpokeSelector *spoke, const char *markup) {
    gchar *escaped;
    PangoAttrList *attrs;

    attrs = pango_attr_list_new();
    pango_attr_list_insert(attrs, pango_attr_style_new(PANGO_STYLE_ITALIC));
    pango_attr_list_insert(attrs, pango_attr_scale_new(PANGO_SCALE_LARGE));

    /* Ampersands (and maybe other characters) in status text need to be escaped. */
    escaped = g_markup_escape_text(markup, -1);

    gtk_label_set_markup(GTK_LABEL(spoke->priv->status_label), escaped);
    gtk_label_set_attributes(GTK_LABEL(spoke->priv->status_label), attrs);

    pango_attr_list_unref(attrs);
    g_free(escaped);
}

static void anaconda_spoke_selector_init(AnacondaSpokeSelector *spoke) {
    char *markup;

    spoke->priv = G_TYPE_INSTANCE_GET_PRIVATE(spoke,
                                              ANACONDA_TYPE_SPOKE_SELECTOR,
                                              AnacondaSpokeSelectorPrivate);

    /* Allow tabbing from one SpokeSelector to the next, and make sure it's
     * selectable with the keyboard.
     */
    gtk_widget_set_can_focus(GTK_WIDGET(spoke), TRUE);
    gtk_widget_add_events(GTK_WIDGET(spoke), GDK_FOCUS_CHANGE_MASK|GDK_KEY_RELEASE_MASK);
    g_signal_connect(spoke, "focus-in-event", G_CALLBACK(anaconda_spoke_selector_focus_changed), NULL);
    g_signal_connect(spoke, "focus-out-event", G_CALLBACK(anaconda_spoke_selector_focus_changed), NULL);

    /* Set "hand" cursor shape when over the selector */
    spoke->priv->cursor = gdk_cursor_new(GDK_HAND2);
    g_signal_connect(spoke, "realize", G_CALLBACK(anaconda_spoke_selector_realize), NULL);

    /* Set property defaults. */
    spoke->priv->is_incomplete = FALSE;

    /* Create the grid. */
    spoke->priv->grid = gtk_grid_new();
    gtk_grid_set_column_spacing(GTK_GRID(spoke->priv->grid), 6);

    /* Create the icons. */
    spoke->priv->icon = gtk_image_new_from_stock(DEFAULT_ICON, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(spoke->priv->icon), 64);
    gtk_widget_set_valign(spoke->priv->icon, GTK_ALIGN_CENTER);
    gtk_misc_set_padding(GTK_MISC(spoke->priv->icon), 12, 0);

    spoke->priv->incomplete_icon = gtk_image_new_from_icon_name("dialog-warning-symbolic", GTK_ICON_SIZE_MENU);
    gtk_widget_set_no_show_all(GTK_WIDGET(spoke->priv->incomplete_icon), TRUE);
    gtk_widget_set_visible(GTK_WIDGET(spoke->priv->incomplete_icon), FALSE);
    gtk_widget_set_valign(spoke->priv->incomplete_icon, GTK_ALIGN_START);
    gtk_widget_set_hexpand(spoke->priv->incomplete_icon, FALSE);
    gtk_misc_set_alignment(GTK_MISC(spoke->priv->incomplete_icon), 0, 1);

    /* Create the title label. */
    spoke->priv->title_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", _(DEFAULT_TITLE));
    gtk_label_set_justify(GTK_LABEL(spoke->priv->title_label), GTK_JUSTIFY_LEFT);
    gtk_label_set_markup(GTK_LABEL(spoke->priv->title_label), markup);
    gtk_misc_set_alignment(GTK_MISC(spoke->priv->title_label), 0, 1);
    gtk_widget_set_hexpand(GTK_WIDGET(spoke->priv->title_label), FALSE);
    g_free(markup);

    /* Create the status label. */
    spoke->priv->status_label = gtk_label_new(NULL);
    format_status_label(spoke, _(DEFAULT_STATUS));
    gtk_label_set_justify(GTK_LABEL(spoke->priv->status_label), GTK_JUSTIFY_LEFT);
    gtk_misc_set_alignment(GTK_MISC(spoke->priv->status_label), 0, 0);
    gtk_label_set_ellipsize(GTK_LABEL(spoke->priv->status_label), PANGO_ELLIPSIZE_MIDDLE);
    gtk_label_set_max_width_chars(GTK_LABEL(spoke->priv->status_label), 45);
    gtk_widget_set_hexpand(GTK_WIDGET(spoke->priv->status_label), FALSE);

    spoke->priv->status_provider = gtk_css_provider_new();
    gtk_css_provider_load_from_data(spoke->priv->status_provider, "GtkLabel { color: @text_color }", -1, NULL);

    /* Add everything to the grid, add the grid to the widget. */
    gtk_grid_attach(GTK_GRID(spoke->priv->grid), spoke->priv->icon, 0, 0, 1, 2);
    gtk_grid_attach(GTK_GRID(spoke->priv->grid), spoke->priv->title_label, 1, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(spoke->priv->grid), spoke->priv->incomplete_icon, 2, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(spoke->priv->grid), spoke->priv->status_label, 1, 1, 2, 1);

    gtk_container_add(GTK_CONTAINER(spoke), spoke->priv->grid);
}

static void anaconda_spoke_selector_finalize(AnacondaSpokeSelector *spoke) {
    g_object_unref(spoke->priv->cursor);
}

static void anaconda_spoke_selector_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaSpokeSelector *widget = ANACONDA_SPOKE_SELECTOR(object);
    AnacondaSpokeSelectorPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_ICON:
           g_value_set_object (value, (GObject *)priv->icon);
           break;

        case PROP_STATUS:
           g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->status_label)));
           break;

        case PROP_TITLE:
           g_value_set_string (value, gtk_label_get_text(GTK_LABEL(priv->title_label)));
           break;
    }
}

static void anaconda_spoke_selector_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaSpokeSelector *widget = ANACONDA_SPOKE_SELECTOR(object);
    AnacondaSpokeSelectorPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_ICON:
           gtk_image_set_from_icon_name(GTK_IMAGE(priv->icon), g_value_get_string(value), GTK_ICON_SIZE_DIALOG);
           gtk_image_set_pixel_size(GTK_IMAGE(priv->icon), 64);
           gtk_widget_set_valign(priv->icon, GTK_ALIGN_START);
           break;

        case PROP_STATUS: {
            GtkStyleContext *context = gtk_widget_get_style_context(GTK_WIDGET(priv->status_label));
            format_status_label(widget, g_value_get_string(value));

            if (gtk_widget_get_sensitive(GTK_WIDGET(widget)))
                gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(priv->status_provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
            else
                gtk_style_context_remove_provider(context, GTK_STYLE_PROVIDER(priv->status_provider));

            break;
        }

        case PROP_TITLE: {
            char *markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->title_label), markup);
            g_free(markup);
            break;
        }
    }
}

/**
 * anaconda_spoke_selector_get_incomplete:
 * @spoke: a #AnacondaSpokeSelector
 *
 * Returns whether or not this spoke has been completed.
 *
 * Returns: Whether @spoke has been completed by the user.
 *
 * Since: 1.0
 */
gboolean anaconda_spoke_selector_get_incomplete(AnacondaSpokeSelector *spoke) {
    return spoke->priv->is_incomplete;
}

/**
 * anaconda_spoke_selector_set_incomplete:
 * @spoke: a #AnacondaSpokeSelector
 * @is_incomplete: %TRUE if this spoke still needs to be visited.
 *
 * Specifies whether this spoke must still be visited by the user.  If so, this
 * means anaconda doesn't have enough information to continue and the user must
 * take some action.  A warning icon will be displayed alongside the spoke's
 * icon, and the continue button will be disabled.
 *
 * Since: 1.0
 */
void anaconda_spoke_selector_set_incomplete(AnacondaSpokeSelector *spoke, gboolean is_incomplete) {
    spoke->priv->is_incomplete = is_incomplete;
    gtk_widget_set_visible(GTK_WIDGET(spoke->priv->incomplete_icon), is_incomplete);
}

static gboolean anaconda_spoke_selector_focus_changed(GtkWidget *widget, GdkEventFocus *event, gpointer user_data) {
    GtkStateFlags new_state;

    new_state = gtk_widget_get_state_flags(widget) & ~GTK_STATE_FOCUSED;
    if (event->in)
        new_state |= GTK_STATE_FOCUSED;
    gtk_widget_set_state_flags(widget, new_state, TRUE);
    return FALSE;
}

static void anaconda_spoke_selector_realize(GtkWidget *widget, gpointer user_data) {
    AnacondaSpokeSelector *spoke_selector = ANACONDA_SPOKE_SELECTOR(widget);

    gdk_window_set_cursor(gtk_widget_get_window(widget), spoke_selector->priv->cursor);
}
