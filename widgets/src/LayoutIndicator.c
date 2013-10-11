/*
 * Copyright (C) 2013  Red Hat, Inc.
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
 *
 * Author: Vratislav Podzimek <vpodzime@redhat.com>
 */

#include <glib.h>
#include <gdk/gdk.h>
#include <gdk/gdkx.h>
#include <gtk/gtk.h>
#include <libxklavier/xklavier.h>

#include "LayoutIndicator.h"
#include "intl.h"

#define MULTIPLE_LAYOUTS_TIP  _("Current layout: '%s'. Click to switch to the next layout.")
#define SINGLE_LAYOUT_TIP _("Current layout: '%s'. Add more layouts to enable switching.")
#define DEFAULT_LAYOUT "us"
#define DEFAULT_LABEL_MAX_CHAR_WIDTH 8
#define MARKUP_FORMAT_STR "<span fgcolor='black' weight='bold'>%s</span>"

/**
 * SECTION: LayoutIndicator
 * @title: AnacondaLayoutIndicator
 * @short_description: An indicator of currently activated X layout
 *
 * An #AnacondaLayoutIndicator is a widget that can be used in any place where
 * indication of currently activated X layout should be shown.
 *
 * An #AnacondaLayoutIndicator is a subclass of a #GtkEventBox.
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
    XklConfigRec *config_rec;
    gulong state_changed_handler_id;
    gulong config_changed_handler_id;
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

/* helper functions */
static gchar* get_current_layout(XklEngine *engine, XklConfigRec *conf_rec);
static void x_state_changed(XklEngine *engine, XklEngineStateChange type,
                            gint arg2, gboolean arg3, gpointer indicator);
static void x_config_changed(XklEngine *engine, gpointer indicator);
static GdkFilterReturn handle_xevent(GdkXEvent *xev, GdkEvent *event, gpointer engine);

static void anaconda_layout_indicator_class_init(AnacondaLayoutIndicatorClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->get_property = anaconda_layout_indicator_get_property;
    object_class->set_property = anaconda_layout_indicator_set_property;
    object_class->dispose = anaconda_layout_indicator_dispose;

    /**
     * AnacondaLayoutIndicator:layout:
     *
     * The :layout is the currently activated X layout.
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

static void anaconda_layout_indicator_init(AnacondaLayoutIndicator *self) {
    GdkDisplay *display;
    GdkRGBA background_color = { 0.0, 0.0, 0.0, 0.0 };
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(self);

    if (!klass->engine) {
        /* This code cannot go to class_init because that way it would be called
           when GObject type system is initialized and Gdk won't give us the
           display. Thus the first instance being created has to populate this
           class-wide stuff */

        /* initialize XklEngine instance that will be used by all LayoutIndicator instances */
        display = gdk_display_get_default();
        klass->engine = xkl_engine_get_instance(GDK_DISPLAY_XDISPLAY(display));

        /* make XklEngine listening */
        xkl_engine_start_listen(klass->engine, XKLL_TRACK_KEYBOARD_STATE);

        /* hook up X events with XklEngine
         * (passing NULL as the first argument means we want X events from all windows)
         */
        gdk_window_add_filter(NULL, (GdkFilterFunc) handle_xevent, klass->engine);
    }

    g_return_if_fail(gdk_rgba_parse(&background_color, "#fdfdfd"));

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
    self->priv->cursor = gdk_cursor_new(GDK_HAND2);
    g_signal_connect(self, "realize",
                     G_CALLBACK(anaconda_layout_indicator_realize),
                     NULL);

    /* layout indicator should have a different background color
       TODO: should be "exported" to allow changes in glade from code? */
    gtk_widget_override_background_color(GTK_WIDGET(self),
                                         GTK_STATE_FLAG_NORMAL, &background_color);

    /* initialize XklConfigRec instance providing data */
    self->priv->config_rec = xkl_config_rec_new();
    xkl_config_rec_get_from_server(self->priv->config_rec, klass->engine);

    /* hook up handler for "X-state-changed" and "X-config-changed" signals */
    self->priv->state_changed_handler_id = g_signal_connect(klass->engine, "X-state-changed",
                                                              G_CALLBACK(x_state_changed),
                                                              g_object_ref(self));
    self->priv->config_changed_handler_id = g_signal_connect(klass->engine, "X-config-changed",
                                                             G_CALLBACK(x_config_changed),
                                                             g_object_ref(self));

    /* init layout attribute with the current layout */
    self->priv->layout = get_current_layout(klass->engine, self->priv->config_rec);

    /* create layout label and set desired properties */
    self->priv->layout_label = GTK_LABEL(gtk_label_new(NULL));
    gtk_widget_set_hexpand(GTK_WIDGET(self->priv->layout_label), FALSE);
    gtk_label_set_max_width_chars(self->priv->layout_label, DEFAULT_LABEL_MAX_CHAR_WIDTH);
    gtk_label_set_width_chars(self->priv->layout_label, DEFAULT_LABEL_MAX_CHAR_WIDTH);
    gtk_label_set_ellipsize(self->priv->layout_label, PANGO_ELLIPSIZE_END);
    gtk_misc_set_alignment(GTK_MISC(self->priv->layout_label), 0.0, 0.5);

    /* initialize the label with the current layout name */
    anaconda_layout_indicator_refresh_ui_elements(self);

    /* create the little keyboard icon and set its left margin */
    self->priv->icon = gtk_image_new_from_icon_name("input-keyboard-symbolic",
                                                    GTK_ICON_SIZE_SMALL_TOOLBAR);

    /* create and populate the main box */
    self->priv->main_box = GTK_BOX(gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 4));
    gtk_box_pack_start(self->priv->main_box, self->priv->icon, FALSE, FALSE, 0);
    gtk_box_pack_end(self->priv->main_box, GTK_WIDGET(self->priv->layout_label), FALSE, FALSE, 0);
    gtk_widget_set_margin_left(GTK_WIDGET(self->priv->main_box), 4);
    gtk_widget_set_margin_right(GTK_WIDGET(self->priv->main_box), 4);
    gtk_widget_set_margin_top(GTK_WIDGET(self->priv->main_box), 3);
    gtk_widget_set_margin_bottom(GTK_WIDGET(self->priv->main_box), 3);

    /* add box to the main container (self) */
    gtk_container_add(GTK_CONTAINER(self), GTK_WIDGET(self->priv->main_box));
}

static void anaconda_layout_indicator_dispose(GObject *object) {
    AnacondaLayoutIndicator *self = ANACONDA_LAYOUT_INDICATOR(object);
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(self);

    /* disconnect signals (XklEngine will outlive us) */
    g_signal_handler_disconnect(klass->engine, self->priv->state_changed_handler_id);
    g_signal_handler_disconnect(klass->engine, self->priv->config_changed_handler_id);

    /* unref all objects we reference (may be called multiple times) */
    if (self->priv->layout_label) {
        gtk_widget_destroy(GTK_WIDGET(self->priv->layout_label));
        self->priv->layout_label = NULL;
    }
    if (self->priv->cursor) {
        g_object_unref(self->priv->cursor);
        self->priv->cursor = NULL;
    }
    if (self->priv->config_rec) {
        g_object_unref(self->priv->config_rec);
        self->priv->config_rec = NULL;
    }
    if (self->priv->layout) {
        g_free(self->priv->layout);
        self->priv->layout = NULL;
    }
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
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(self);

    if (event->type != GDK_BUTTON_RELEASE)
        return;

    XklState *state = xkl_engine_get_current_state(klass->engine);
    guint n_groups = xkl_engine_get_num_groups(klass->engine);

    /* cycle over groups */
    guint next_group = (state->group + 1) % n_groups;

    /* activate next group */
    xkl_engine_lock_group(klass->engine, next_group);
}

static void anaconda_layout_indicator_refresh_ui_elements(AnacondaLayoutIndicator *self) {
    gchar *markup;

    markup = g_markup_printf_escaped(MARKUP_FORMAT_STR, self->priv->layout);
    gtk_label_set_markup(self->priv->layout_label, markup);
    g_free(markup);

    anaconda_layout_indicator_refresh_tooltip(self);
}

static void anaconda_layout_indicator_refresh_layout(AnacondaLayoutIndicator *self) {
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(self);

    g_free(self->priv->layout);
    self->priv->layout = get_current_layout(klass->engine, self->priv->config_rec);

    anaconda_layout_indicator_refresh_ui_elements(self);
}

static void anaconda_layout_indicator_refresh_tooltip(AnacondaLayoutIndicator *self) {
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(self);
    guint n_groups = xkl_engine_get_num_groups(klass->engine);
    gchar *tooltip;

    if (n_groups > 1)
        tooltip = g_strdup_printf(MULTIPLE_LAYOUTS_TIP, self->priv->layout);
    else
        tooltip = g_strdup_printf(SINGLE_LAYOUT_TIP, self->priv->layout);

    gtk_widget_set_tooltip_text(GTK_WIDGET(self), tooltip);
    g_free(tooltip);
}

/**
 * get_current_layout:
 *
 * Returns: newly allocated string with the currently activated layout as
 *          'layout (variant)'
 */
static gchar* get_current_layout(XklEngine *engine, XklConfigRec *conf_rec) {
    /* engine has to be listening with XKLL_TRACK_KEYBOARD_STATE mask */
    gchar *layout = NULL;
    gchar *variant = NULL;
    gint32 cur_group;

    /* returns statically allocated buffer, shouldn't be freed */
    XklState *state = xkl_engine_get_current_state(engine);
    cur_group = state->group;

    guint n_groups = xkl_engine_get_num_groups(engine);

    /* BUG?: if the last layout in the list is activated and removed,
             state->group may be equal to n_groups that would result in
             layout being NULL
    */
    if (cur_group >= n_groups)
        cur_group = n_groups - 1;

    layout = conf_rec->layouts[cur_group];

    /* variant defined for the current layout */
    variant = conf_rec->variants[cur_group];

    /* variant may be NULL or "" if not defined */
    if (variant && g_strcmp0("", variant))
        return g_strdup_printf("%s (%s)", layout, variant);
    else
        return g_strdup(layout);
}

static GdkFilterReturn handle_xevent(GdkXEvent *xev, GdkEvent *event, gpointer data) {
    XklEngine *engine = XKL_ENGINE(data);
    XEvent *xevent = (XEvent *) xev;

    xkl_engine_filter_events(engine, xevent);

    return GDK_FILTER_CONTINUE;
}

static void x_state_changed(XklEngine *engine, XklEngineStateChange type,
                            gint arg2, gboolean arg3, gpointer data) {
    g_return_if_fail(data);
    AnacondaLayoutIndicator *indicator = ANACONDA_LAYOUT_INDICATOR(data);

    anaconda_layout_indicator_refresh_layout(indicator);
}

static void x_config_changed(XklEngine *engine, gpointer data) {
    g_return_if_fail(data);
    AnacondaLayoutIndicator *indicator = ANACONDA_LAYOUT_INDICATOR(data);
    AnacondaLayoutIndicatorClass *klass = ANACONDA_LAYOUT_INDICATOR_GET_CLASS(indicator);

    /* load current configuration from the X server */
    xkl_config_rec_get_from_server(indicator->priv->config_rec, klass->engine);

    anaconda_layout_indicator_refresh_layout(indicator);
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
 * Returns: (transfer none): the current width of the layout label in number of chars
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
