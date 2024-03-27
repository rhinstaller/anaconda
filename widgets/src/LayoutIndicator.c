/*
 * Copyright (C) 2013-2014 Red Hat, Inc.
 *
 * Some parts of this code were inspired by the xfce4-xkb-plugin's sources.
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

#include <atk/atk.h>
#include <gio/gio.h>
#include <glib.h>
#include <gdk/gdk.h>
#include <gdk/gdkx.h>
#include <gtk/gtk.h>

#include "LayoutIndicator.h"
#include "an-localization.h"
#include "intl.h"
#include "widgets-common.h"

#define MULTIPLE_LAYOUTS_TIP  _("Current layout: '%s'. Click to switch to the next layout.")
#define SINGLE_LAYOUT_TIP _("Current layout: '%s'. Add more layouts to enable switching.")
#define DEFAULT_LAYOUT "us"
#define DEFAULT_LABEL_MAX_CHAR_WIDTH 8
#define ANACONDA_BUS_ADDR_FILE "/run/anaconda/bus.address"
#define DBUS_ANACONDA_SESSION_ADDRESS "DBUS_ANACONDA_SESSION_BUS_ADDRESS"

/**
 * SECTION: AnacondaLayoutIndicator
 * @title: AnacondaLayoutIndicator
 * @short_description: An indicator of currently activated X layout
 *
 * An #AnacondaLayoutIndicator is a widget that can be used in any place where
 * indication of currently activated X layout should be shown.
 *
 * An #AnacondaLayoutIndicator is a subclass of a #GtkEventBox.
 *
 * # CSS nodes
 *
 * |[<!-- language="plain" -->
 * AnacondaLayoutIndicator
 * ├── #anaconda-layout-icon
 * ╰── #anaconda-layout-label
 * ]|
 *
 * The internal widgets are accessible by name for the purposes of CSS
 * selectors.
 *
 * - anaconda-layout-icon
 *
 *   The keyboard icon indicating that this is a keyboard layout widget
 *
 * - anaconda-layout-label
 *
 *   A label describing the current layout
 */

enum {
    PROP_LAYOUT = 1,
    PROP_LABEL_WIDTH
};

struct _AnacondaLayoutIndicatorPrivate {
    gchar *layout;
    guint label_width;
    GtkBox *main_box;
    GtkWidget *icon;
    GtkLabel *layout_label;
    GdkCursor *cursor;
    AnLocalization *localization_proxy;
};

G_DEFINE_TYPE(AnacondaLayoutIndicator, anaconda_layout_indicator, GTK_TYPE_EVENT_BOX)

static void anaconda_layout_indicator_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_layout_indicator_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);

static void anaconda_layout_indicator_dispose(GObject *indicator);
static void anaconda_layout_indicator_realize(GtkWidget *widget, gpointer user_data);

static void anaconda_layout_indicator_clicked(GtkWidget *widget, GdkEvent *event, gpointer user_data);
static void anaconda_layout_indicator_refresh_ui_elements(AnacondaLayoutIndicator *indicator);
static void anaconda_layout_indicator_refresh_layout(AnacondaLayoutIndicator *indicator);
static void anaconda_layout_indicator_refresh_tooltip(AnacondaLayoutIndicator *indicator);

static void anaconda_layout_indicator_class_init(AnacondaLayoutIndicatorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);
    GtkWidgetClass *widget_class = GTK_WIDGET_CLASS(klass);

    object_class->get_property = anaconda_layout_indicator_get_property;
    object_class->set_property = anaconda_layout_indicator_set_property;
    object_class->dispose = anaconda_layout_indicator_dispose;

    /**
     * AnacondaLayoutIndicator:layout:
     *
     * The #AnacondaLayoutIndicator:layout is the currently activated X layout.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_LAYOUT,
                                    g_param_spec_string("layout",
                                                        P_("layout"),
                                                        P_("Current layout"),
                                                        DEFAULT_LAYOUT,
                                                        G_PARAM_READABLE));

    /**
     * AnacondaLayoutIndicator:label-width:
     *
     * Width of the label showing the current layout in number of characters.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_LABEL_WIDTH,
                                    g_param_spec_uint("label-width",
                                                      P_("Label width"),
                                                      P_("Width of the label showing the current layout"),
                                                      0, 20, DEFAULT_LABEL_MAX_CHAR_WIDTH,
                                                      G_PARAM_READWRITE));

    g_type_class_add_private(object_class, sizeof(AnacondaLayoutIndicatorPrivate));

    gtk_widget_class_set_css_name(widget_class, "AnacondaLayoutIndicator");
}

/**
 * anaconda_layout_indicator_new:
 *
 * Creates a new #AnacondaLayoutIndicator, which is an indicator of the
 * currently activated X layout. When the indicator is clicked, it activates
 * the next layout in the list of configured layouts.
 *
 * Returns: A new #AnacondaLayoutIndicator.
 */
GtkWidget *anaconda_layout_indicator_new() {
    return g_object_new(ANACONDA_TYPE_LAYOUT_INDICATOR, NULL);
}

static void anaconda_localization_on_layouts_changed(AnLocalization *proxy,
                                                     const gchar *const *layouts,
                                                     AnacondaLayoutIndicator *self) {
    anaconda_layout_indicator_refresh_layout(self);
}

static void anaconda_localization_on_selected_layout_changed(AnLocalization *proxy,
                                                     const gchar *layout,
                                                     AnacondaLayoutIndicator *self) {
    anaconda_layout_indicator_refresh_layout(self);
}

static gchar *anaconda_localization_get_bus_addr(void) {
    gchar *bus_addr;
    gboolean res;

    bus_addr = (gchar *)g_getenv(DBUS_ANACONDA_SESSION_ADDRESS);
    if (bus_addr) {
        return g_strdup(bus_addr);
    }

    res = g_file_get_contents(ANACONDA_BUS_ADDR_FILE,
                              &bus_addr,
                              NULL,
                              NULL);
    if (res) {
        return bus_addr;
    }

    return NULL;
}

static void anaconda_localization_connect(AnacondaLayoutIndicator *self) {
    gchar *bus_addr;
    GDBusConnection *bus;
    AnLocalization *proxy;
    g_autoptr(GError) error = NULL;

    bus_addr = anaconda_localization_get_bus_addr();
    if (!bus_addr) {
        g_warning("Error getting Anaconda bus address");
        return;
    }

    bus = g_dbus_connection_new_for_address_sync(bus_addr,
                                                 G_DBUS_CONNECTION_FLAGS_AUTHENTICATION_CLIENT | G_DBUS_CONNECTION_FLAGS_MESSAGE_BUS_CONNECTION,
                                                 NULL,
                                                 NULL,
                                                 &error);
    g_free(bus_addr);
    if (!bus) {
        g_warning("Error getting Anaconda bus: %s", error->message);
        return;
    }

    proxy = an_localization_proxy_new_sync(bus,
                                           G_DBUS_PROXY_FLAGS_NONE,
                                           "org.fedoraproject.Anaconda.Modules.Localization",
                                           "/org/fedoraproject/Anaconda/Modules/Localization",
                                           NULL,
                                           &error);
    if (!proxy) {
        g_warning("Failed to connect to Anaconda's localization module: %s", error->message);
        return;
    }

    g_signal_connect_object(G_OBJECT(proxy),
                            "compositor-layouts-changed",
                            G_CALLBACK(anaconda_localization_on_layouts_changed),
                            self,
                            G_CONNECT_DEFAULT);
    g_signal_connect_object(G_OBJECT(proxy),
                            "compositor-selected-layout-changed",
                            G_CALLBACK(anaconda_localization_on_selected_layout_changed),
                            self,
                            G_CONNECT_DEFAULT);

    self->priv->localization_proxy = proxy;
}

static gchar *anaconda_localization_get_current_layout(AnacondaLayoutIndicator *self) {
    gboolean result;
    gchar *layout = NULL;
    g_autoptr(GError) error = NULL;

    result = an_localization_call_get_compositor_selected_layout_sync(self->priv->localization_proxy,
                                                                      &layout,
                                                                      NULL,
                                                                      &error);
    if (!result || g_str_equal(layout, "")) {
        if (layout)
            g_free(layout);
        return g_strdup(DEFAULT_LAYOUT);
    }

    return layout;    
}

static int anaconda_localization_get_num_layouts(AnacondaLayoutIndicator *self) {
    gboolean result;
    gchar **layouts = NULL;
    g_autoptr(GError) error = NULL;
    int n_groups;

    result = an_localization_call_get_compositor_layouts_sync(self->priv->localization_proxy,
                                                              &layouts,
                                                              NULL,
                                                              &error);
    if (!result) {
        g_warning("Error getting compositor layouts: %s", error->message);
        return -1;
    }

    n_groups = g_strv_length(layouts);
    g_strfreev(layouts);
    return n_groups;
}

static void anaconda_localization_select_next_layout(AnacondaLayoutIndicator *self) {
    an_localization_call_select_next_compositor_layout_sync(self->priv->localization_proxy,
                                                            NULL,
                                                            NULL);
}

static void anaconda_layout_indicator_init(AnacondaLayoutIndicator *self) {
    AtkObject *atk;

    self->priv = G_TYPE_INSTANCE_GET_PRIVATE(self,
                                             ANACONDA_TYPE_LAYOUT_INDICATOR,
                                             AnacondaLayoutIndicatorPrivate);

    /* layout indicator should not change focus when it is clicked */
    gtk_widget_set_can_focus(GTK_WIDGET(self), FALSE);

    /* layout indicator should have a tooltip saying what is the current layout
       and what clicking it does
    */
    gtk_widget_set_has_tooltip(GTK_WIDGET(self), TRUE);

    /* layout indicator activates next layout when it is clicked */
    gtk_widget_add_events(GTK_WIDGET(self), GDK_BUTTON_RELEASE_MASK);
    g_signal_connect(self, "button-release-event",
                     G_CALLBACK(anaconda_layout_indicator_clicked),
                     NULL);

    /* layout indicator should have a hand cursor so that looks like clickable widget */
    self->priv->cursor = gdk_cursor_new_for_display(gdk_display_get_default(), GDK_HAND2);
    g_signal_connect(self, "realize",
                     G_CALLBACK(anaconda_layout_indicator_realize),
                     NULL);

    /* init layout attribute with the current layout */
    anaconda_localization_connect(self);
    self->priv->layout = anaconda_localization_get_current_layout(self);

    /* create layout label and set desired properties */
    self->priv->layout_label = GTK_LABEL(gtk_label_new(NULL));
    gtk_widget_set_hexpand(GTK_WIDGET(self->priv->layout_label), FALSE);
    gtk_label_set_max_width_chars(self->priv->layout_label, DEFAULT_LABEL_MAX_CHAR_WIDTH);
    gtk_label_set_width_chars(self->priv->layout_label, DEFAULT_LABEL_MAX_CHAR_WIDTH);
    gtk_label_set_ellipsize(self->priv->layout_label, PANGO_ELLIPSIZE_END);
    gtk_label_set_xalign(self->priv->layout_label, 0.0);
    gtk_label_set_yalign(self->priv->layout_label, 0.5);
    gtk_widget_set_name(GTK_WIDGET(self->priv->layout_label), "anaconda-layout-label");

    /* initialize the label with the current layout name */
    anaconda_layout_indicator_refresh_ui_elements(self);

    /* create the little keyboard icon and set its left margin */
    self->priv->icon = gtk_image_new_from_icon_name("input-keyboard-symbolic",
                                                    GTK_ICON_SIZE_SMALL_TOOLBAR);
    gtk_widget_set_name(self->priv->icon, "anaconda-layout-icon");

    /* create and populate the main box */
    self->priv->main_box = GTK_BOX(gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 4));
    gtk_box_pack_start(self->priv->main_box, self->priv->icon, FALSE, FALSE, 0);
    gtk_box_pack_end(self->priv->main_box, GTK_WIDGET(self->priv->layout_label), FALSE, FALSE, 0);
    gtk_widget_set_margin_start(GTK_WIDGET(self->priv->main_box), 4);
    gtk_widget_set_margin_end(GTK_WIDGET(self->priv->main_box), 4);
    gtk_widget_set_margin_top(GTK_WIDGET(self->priv->main_box), 3);
    gtk_widget_set_margin_bottom(GTK_WIDGET(self->priv->main_box), 3);

    /* add box to the main container (self) */
    gtk_container_add(GTK_CONTAINER(self), GTK_WIDGET(self->priv->main_box));

    atk = gtk_widget_get_accessible(GTK_WIDGET(self));
    atk_object_set_name(atk, "Keyboard Layout");
    atk_object_set_description(atk, self->priv->layout);

    /* Apply stylesheets to widgets that have them */
    anaconda_widget_apply_stylesheet(GTK_WIDGET(self), "LayoutIndicator");
    anaconda_widget_apply_stylesheet(GTK_WIDGET(self->priv->layout_label), "LayoutIndicator-label");
}

static void anaconda_layout_indicator_dispose(GObject *object) {
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(object);

    /* unref all objects we reference (may be called multiple times) */
    if (self->priv->layout_label) {
        gtk_widget_destroy(GTK_WIDGET(self->priv->layout_label));
        self->priv->layout_label = NULL;
    }
    if (self->priv->cursor) {
        g_object_unref(self->priv->cursor);
        self->priv->cursor = NULL;
    }
    if (self->priv->layout) {
        g_free(self->priv->layout);
        self->priv->layout = NULL;
    }
    if (self->priv->localization_proxy) {
        g_clear_object(&self->priv->localization_proxy);
    }

    G_OBJECT_CLASS(anaconda_layout_indicator_parent_class)->dispose(object);
}

static void anaconda_layout_indicator_realize(GtkWidget *widget, gpointer data) {
    /* set cursor for the widget's GdkWindow */
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(widget);

    gdk_window_set_cursor(gtk_widget_get_window(widget), self->priv->cursor);
}

static void anaconda_layout_indicator_get_property(GObject *object, guint prop_id,
                                                   GValue *value, GParamSpec *pspec) {
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(object);

    switch (prop_id) {
        case PROP_LAYOUT:
            g_value_set_string(value, self->priv->layout);
            break;
        case PROP_LABEL_WIDTH:
            g_value_set_uint(value, self->priv->label_width);
            break;
    }
}

static void anaconda_layout_indicator_set_property(GObject *object, guint prop_id,
                                                   const GValue *value, GParamSpec *pspec) {
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(object);

    switch (prop_id) {
        case PROP_LABEL_WIDTH:
            self->priv->label_width = g_value_get_uint(value);
            gtk_label_set_max_width_chars(self->priv->layout_label, self->priv->label_width);
            gtk_label_set_width_chars(self->priv->layout_label, self->priv->label_width);
            break;
    }
}

static void anaconda_layout_indicator_clicked(GtkWidget *widget, GdkEvent *event, gpointer data) {
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(widget);

    if (event->type != GDK_BUTTON_RELEASE)
        return;

    int n_groups = anaconda_localization_get_num_layouts(self);
    if (n_groups > 1)
        anaconda_localization_select_next_layout(self);
}

static void anaconda_layout_indicator_refresh_ui_elements(AnacondaLayoutIndicator *self) {
    gtk_label_set_text(self->priv->layout_label, self->priv->layout);

    anaconda_layout_indicator_refresh_tooltip(self);
}

static void anaconda_layout_indicator_refresh_layout(AnacondaLayoutIndicator *self) {
    AtkObject *atk;

    g_free(self->priv->layout);
    self->priv->layout = anaconda_localization_get_current_layout(self);

    atk = gtk_widget_get_accessible(GTK_WIDGET(self));
    atk_object_set_description(atk, self->priv->layout);

    anaconda_layout_indicator_refresh_ui_elements(self);
}

static void anaconda_layout_indicator_refresh_tooltip(AnacondaLayoutIndicator *self) {
    int n_groups = anaconda_localization_get_num_layouts(self);
    gchar *tooltip;

    if (n_groups > 1)
        tooltip = g_strdup_printf(MULTIPLE_LAYOUTS_TIP, self->priv->layout);
    else
        tooltip = g_strdup_printf(SINGLE_LAYOUT_TIP, self->priv->layout);

    gtk_widget_set_tooltip_text(GTK_WIDGET(self), tooltip);
    g_free(tooltip);
}

/**
 * anaconda_layout_indicator_get_current_layout:
 * @indicator: a #AnacondaLayoutIndicator
 *
 * Returns: (transfer full): the currently activated X layout.
 *
 * Since: 1.0
 */
gchar* anaconda_layout_indicator_get_current_layout(AnacondaLayoutIndicator *indicator) {
    g_return_val_if_fail(indicator->priv->layout, NULL);

    /* TODO: return description instead of raw layout name? */
    return g_strdup(indicator->priv->layout);
}

/**
 * anaconda_layout_indicator_get_label_width:
 * @indicator: a #AnacondaLayoutIndicator
 *
 * Returns: the current width of the layout label in number of chars
 *
 * Since: 1.0
 */
guint anaconda_layout_indicator_get_label_width(AnacondaLayoutIndicator *indicator) {
    g_return_val_if_fail(indicator->priv->layout, 0);

    return indicator->priv->label_width;
}

/**
 * anaconda_layout_indicator_set_label_width:
 * @indicator: a #AnacondaLayoutIndicator
 * @new_width: a new requested width of the layout label in number of chars
 *
 *
 * Since: 1.0
 */
void anaconda_layout_indicator_set_label_width(AnacondaLayoutIndicator *indicator,
                                               guint new_width) {
    g_return_if_fail(indicator->priv->layout);

    GValue width = G_VALUE_INIT;
    g_value_init(&width, G_TYPE_UINT);
    g_value_set_uint(&width, new_width);

    anaconda_layout_indicator_set_property(G_OBJECT(indicator), PROP_LABEL_WIDTH,
                                           &width, NULL);
}

/**
 * anaconda_layout_indicator_retranslate:
 * @indicator: a #AnacondaLayoutIndicator
 *
 * Reload translations for this widget as needed.  Generally, this is not
 * needed.  However when changing the language during installation, we need to
 * be able to make sure the screen gets retranslated.  This function must be
 * called after the LANG environment variable, locale and gettext magic are set.
 *
 * Since: 1.0
 */
void anaconda_layout_indicator_retranslate(AnacondaLayoutIndicator *indicator) {
    anaconda_layout_indicator_refresh_tooltip(indicator);
}
