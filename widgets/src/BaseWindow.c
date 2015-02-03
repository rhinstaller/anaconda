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

#include "config.h"

#include <libintl.h>
#include <locale.h>
#include <stdlib.h>
#include <string.h>

#include "LayoutIndicator.h"
#include "BaseWindow.h"
#include "intl.h"

 #include <atk/atk.h>

/**
 * SECTION: BaseWindow
 * @title: AnacondaBaseWindow
 * @short_description: Top-level, non-resizeable window
 *
 * A #AnacondaBaseWindow is a widget that contains other widgets and serves as
 * the base class from which all other specialized Anaconda windows are
 * derived.
 *
 * The AnacondaBaseWindow consists of two areas:
 *
 * - A navigation area in the top of the screen, consisting of some basic
 *   information about what is being displayed and what is being installed.
 *
 * - An action area in the majority of the screen.  This area is where
 *   subclasses should add their particular widgets.
 *
 * <refsect2 id="AnacondaBaseWindow-BUILDER-UI"><title>AnacondaBaseWindow as GtkBuildable</title>
 * <para>
 * The AnacondaBaseWindow implementation of the #GtkBuildable interface exposes
 * the @nav_area as an internal child with the name "nav_area" and the
 * @action_area as an internal child with the name "action_area".
 * </para>
 * <example>
 * <title>A <structname>AnacondaBaseWindow</structname> UI definition fragment.</title>
 * <programlisting><![CDATA[
 * <object class="AnacondaBaseWindow" id="window1">
 *     <child internal-child="main_box">
 *         <object class="GtkBox" id="main_box1">
 *             <child internal-child="nav_box">
 *                 <object class="GtkEventBox" id="nav_box1">
 *                     <child internal-child="nav_area">
 *                         <object class="GtkGrid" id="nav_area1">
 *                             <child>...</child>
 *                             <child>...</child>
 *                         </object>
 *                     </child>
 *                 </object>
 *             </child>
 *             <child internal-child="alignment">
 *                 <object class="GtkAlignment" id="alignment1">
 *                     <child internal-child="action_area">
 *                         <object class="GtkBox" id="action_area1">
 *                             <child>
 *                                 <object class="GtkLabel" id="label1">
 *                                     <property name="label" translatable="yes">THIS IS ONE LABEL</property>
 *                                 </object>
 *                             </child>
 *                             <child>
 *                                 <object class="GtkLabel" id="label2">
 *                                     <property name="label" translatable="yes">THIS IS ANOTHER LABEL</property>
 *                                 </object>
 *                             </child>
 *                         </object>
 *                     </child>
 *                 </object>
 *             </child>
 *         </object>
 *     </child>
 * </object>
 * ]]></programlisting>
 * </example>
 * </refsect2>
 */

enum {
    SIGNAL_INFO_BAR_CLICKED,
    SIGNAL_HELP_BUTTON_CLICKED,
    LAST_SIGNAL
};

static guint window_signals[LAST_SIGNAL] = { 0 };

enum {
    PROP_DISTRIBUTION = 1,
    PROP_WINDOW_NAME
};

#define DEFAULT_DISTRIBUTION  N_("DISTRIBUTION INSTALLATION")
#define DEFAULT_WINDOW_NAME   N_("SPOKE NAME")
#define DEFAULT_BETA          N_("PRE-RELEASE / TESTING")
#define LAYOUT_INDICATOR_LABEL_WIDTH 10
#define HELP_BUTTON_LABEL N_("Help!")

struct _AnacondaBaseWindowPrivate {
    gboolean    is_beta, info_shown;
    GtkWidget  *main_box, *event_box, *info_bar;
    GtkWidget  *alignment;
    GtkWidget  *nav_box, *nav_area, *action_area;
    GtkWidget  *name_label, *distro_label, *beta_label;
    GtkWidget  *layout_indicator;
    GtkWidget  *help_button;

    /* Untranslated versions of various things. */
    gchar *orig_name, *orig_distro, *orig_beta;
};

static void anaconda_base_window_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_base_window_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_base_window_buildable_init(GtkBuildableIface *iface);
static void format_beta_label(AnacondaBaseWindow *window, const char *markup);

static gboolean anaconda_base_window_info_bar_clicked(GtkWidget *widget, GdkEvent *event, AnacondaBaseWindow *win);
static void anaconda_base_window_help_button_clicked(GtkButton *button, AnacondaBaseWindow *win);

G_DEFINE_TYPE_WITH_CODE(AnacondaBaseWindow, anaconda_base_window, GTK_TYPE_BIN,
                        G_IMPLEMENT_INTERFACE(GTK_TYPE_BUILDABLE, anaconda_base_window_buildable_init))

static void anaconda_base_window_class_init(AnacondaBaseWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->set_property = anaconda_base_window_set_property;
    object_class->get_property = anaconda_base_window_get_property;

    /**
     * AnacondaBaseWindow:distribution:
     *
     * The :distribution string is displayed in the upper right corner of all
     * windows throughout installation.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_DISTRIBUTION,
                                    g_param_spec_string("distribution",
                                                        P_("Distribution"),
                                                        P_("The distribution being installed"),
                                                        DEFAULT_DISTRIBUTION,
                                                        G_PARAM_READWRITE));

    /**
     * AnacondaBaseWindow:window-name:
     *
     * The name of the currently displayed window, displayed in the upper
     * left corner of all windows with a title throughout installation.
     * StandaloneWindows should not have a title, so no name will be displayed
     * for those.
     *
     * Since: 1.0
     */
    g_object_class_install_property(object_class,
                                    PROP_WINDOW_NAME,
                                    g_param_spec_string("window-name",
                                                        P_("Window Name"),
                                                        P_("The name of this spoke"),
                                                        DEFAULT_WINDOW_NAME,
                                                        G_PARAM_READWRITE));

    klass->info_bar_clicked = NULL;
    klass->help_button_clicked = NULL;

    /**
     * AnacondaBaseWindow::info-bar-clicked:
     * @window: the window that received the signal
     *
     * Emitted when a visible info bar at the bottom of the window has been clicked
     * (pressed and released).  This allows, for instance, popping up a dialog with
     * more detailed information.
     *
     * Since: 1.0
     */
    window_signals[SIGNAL_INFO_BAR_CLICKED] = g_signal_new("info-bar-clicked",
                                                           G_TYPE_FROM_CLASS(object_class),
                                                           G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                           G_STRUCT_OFFSET(AnacondaBaseWindowClass, info_bar_clicked),
                                                           NULL, NULL,
                                                           g_cclosure_marshal_VOID__VOID,
                                                           G_TYPE_NONE, 0);

    /**
     * AnacondaBaseWindow::help-button-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the help button in the right corner has been activated
     * (pressed and released). This is commonly used to open the help view with
     * help content for the given spoke or hub
     *
     * Since: 3.1
     */
    window_signals[SIGNAL_HELP_BUTTON_CLICKED] = g_signal_new("help-button-clicked",
                                                              G_TYPE_FROM_CLASS(object_class),
                                                              G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                              G_STRUCT_OFFSET(AnacondaBaseWindowClass, help_button_clicked),
                                                              NULL, NULL,
                                                              g_cclosure_marshal_VOID__VOID,
                                                              G_TYPE_NONE, 0);

    g_type_class_add_private(object_class, sizeof(AnacondaBaseWindowPrivate));
}

/**
 * anaconda_base_window_new:
 *
 * Creates a new #AnacondaBaseWindow, which is a toplevel, non-resizeable
 * window that contains other widgets.  This is the base class for all other
 * Anaconda windows and creates the window style that all windows will share.
 *
 * Returns: A new #AnacondaBaseWindow.
 */
GtkWidget *anaconda_base_window_new() {
    return g_object_new(ANACONDA_TYPE_BASE_WINDOW, NULL);
}

static void anaconda_base_window_init(AnacondaBaseWindow *win) {
    char *markup;
    AtkObject *atk;
    GtkStyleContext *context;

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_BASE_WINDOW,
                                            AnacondaBaseWindowPrivate);

    win->priv->is_beta = FALSE;
    win->priv->info_shown = FALSE;

    /* These store the original English strings so that when we retranslate
     * later, we have the source strings available to feed into _().
     */
    win->priv->orig_name = NULL;
    win->priv->orig_distro = NULL;
    win->priv->orig_beta = NULL;

    /* Set properties on the parent (Gtk.Bin) class. */
    gtk_widget_set_hexpand(GTK_WIDGET(win), TRUE);
    gtk_widget_set_vexpand(GTK_WIDGET(win), TRUE);
    gtk_container_set_border_width(GTK_CONTAINER(win), 0);

    /* First, construct a top-level box that everything will go in.  Remember
     * a Window can only hold one widget, and we may very well need to add
     * more things later.
     */
    win->priv->main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_container_add(GTK_CONTAINER(win), win->priv->main_box);

    /* GtkBoxes don't draw a background by default, which causes issues during
     * transitions in a GtkStack. Work around this by forcing a "background"
     * style class. See https://bugzilla.gnome.org/show_bug.cgi?id=742552
     */
    context = gtk_widget_get_style_context(win->priv->main_box);
    gtk_style_context_add_class(context, "background");

    /* Then the navigation area that sits as the first item in the main box
     * for every Window class.
     */

    win->priv->nav_box = gtk_event_box_new();
    gtk_widget_set_name(win->priv->nav_box, "nav-box");
    gtk_box_pack_start(GTK_BOX(win->priv->main_box), win->priv->nav_box, FALSE, FALSE, 0);

    win->priv->nav_area = gtk_grid_new();
    gtk_grid_set_row_homogeneous(GTK_GRID(win->priv->nav_area), FALSE);
    gtk_grid_set_column_homogeneous(GTK_GRID(win->priv->nav_area), FALSE);
    gtk_widget_set_margin_start(win->priv->nav_area, 18);
    gtk_widget_set_margin_end(win->priv->nav_area, 18);
    gtk_widget_set_margin_top(win->priv->nav_area, 12);
    gtk_widget_set_margin_bottom(win->priv->nav_area, 6);

    gtk_container_add(GTK_CONTAINER(win->priv->nav_box), win->priv->nav_area);

    /* Second in the main box is an alignment, because we want to be able
     * to control the amount of space the Window's content takes up on the
     * screen.
     */
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    /*
     * GtkAlignment is deprecated, but getting rid of it would have severe downstream
     * repurcusions, so put that off for as long as we can.
     */
    win->priv->alignment = gtk_alignment_new(0.5, 0.0, 1.0, 1.0);
G_GNUC_END_IGNORE_DEPRECATIONS
    gtk_box_pack_start(GTK_BOX(win->priv->main_box), win->priv->alignment, TRUE, TRUE, 0);

    /* The action_area goes inside the alignment and represents the main
     * place for content to go.
     */
    win->priv->action_area = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_container_add(GTK_CONTAINER(win->priv->alignment), win->priv->action_area);

    /* And now we can finally create the widgets that go in all those layout
     * pieces up above.
     */

    /* Create the name label. */
    win->priv->name_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", _(DEFAULT_WINDOW_NAME));
    gtk_label_set_markup(GTK_LABEL(win->priv->name_label), markup);
    g_free(markup);
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    /*
     * GtkMisc is deprecated, but if you don't set the GtkMisc properties then they
     * still default to everything being centered. A+ work everyone.
     */
    gtk_misc_set_alignment(GTK_MISC(win->priv->name_label), 0, 0);
G_GNUC_END_IGNORE_DEPRECATIONS
    gtk_widget_set_hexpand(win->priv->name_label, TRUE);

    win->priv->orig_name = g_strdup(DEFAULT_WINDOW_NAME);

    /* Create the distribution label. */
    win->priv->distro_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span size='large'>%s</span>", _(DEFAULT_DISTRIBUTION));
    gtk_label_set_markup(GTK_LABEL(win->priv->distro_label), markup);
    g_free(markup);
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    gtk_misc_set_alignment(GTK_MISC(win->priv->distro_label), 0, 0);
G_GNUC_END_IGNORE_DEPRECATIONS

    win->priv->orig_distro = g_strdup(DEFAULT_DISTRIBUTION);

    /* Create the beta label. */
    win->priv->beta_label = gtk_label_new(NULL);
    format_beta_label(win, _(DEFAULT_BETA));
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    gtk_misc_set_alignment(GTK_MISC(win->priv->beta_label), 0, 0);
G_GNUC_END_IGNORE_DEPRECATIONS
    gtk_widget_set_no_show_all(win->priv->beta_label, TRUE);

    win->priv->orig_beta = g_strdup(DEFAULT_BETA);

    /* Create the layout indicator */
    win->priv->layout_indicator = anaconda_layout_indicator_new();
    anaconda_layout_indicator_set_label_width(ANACONDA_LAYOUT_INDICATOR(win->priv->layout_indicator),
                                              LAYOUT_INDICATOR_LABEL_WIDTH);
    gtk_widget_set_name(win->priv->layout_indicator, "layout-indicator");
    gtk_widget_set_halign(win->priv->layout_indicator, GTK_ALIGN_START);
    gtk_widget_set_hexpand(win->priv->layout_indicator, FALSE);
    gtk_widget_set_margin_top(win->priv->layout_indicator, 6);
    gtk_widget_set_margin_bottom(win->priv->layout_indicator, 6);

    /* Create the help button. */
    win->priv->help_button = gtk_button_new_with_label(HELP_BUTTON_LABEL);
    gtk_widget_set_halign(win->priv->help_button, GTK_ALIGN_END);
    gtk_widget_set_vexpand(win->priv->help_button, FALSE);
    gtk_widget_set_valign(win->priv->help_button, GTK_ALIGN_END);
    gtk_widget_set_margin_bottom(win->priv->help_button, 6);

    atk = gtk_widget_get_accessible(win->priv->help_button);
    atk_object_set_name(atk, HELP_BUTTON_LABEL);

    /* Hook up some signals for that button.  The signal handlers here will
     * just raise our own custom signals for the whole window.
     */
    g_signal_connect(win->priv->help_button, "clicked",
                     G_CALLBACK(anaconda_base_window_help_button_clicked), win);

    /* Add everything to the nav area. */
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->name_label, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->distro_label, 1, 0, 2, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->beta_label, 1, 1, 1, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->layout_indicator, 1, 2, 1, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->help_button, 2, 1, 1, 2);
}

static void anaconda_base_window_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaBaseWindow *widget = ANACONDA_BASE_WINDOW(object);
    AnacondaBaseWindowPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_DISTRIBUTION:
            g_value_set_string(value, gtk_label_get_text(GTK_LABEL(priv->distro_label)));
            break;

        case PROP_WINDOW_NAME:
            g_value_set_string(value, gtk_label_get_text(GTK_LABEL(priv->name_label)));
            break;
    }
}

static void anaconda_base_window_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaBaseWindow *widget = ANACONDA_BASE_WINDOW(object);
    AnacondaBaseWindowPrivate *priv = widget->priv;

    switch(prop_id) {
        case PROP_DISTRIBUTION: {
            char *markup = g_markup_printf_escaped("<span size='large'>%s</span>", _(g_value_get_string(value)));
            gtk_label_set_markup(GTK_LABEL(priv->distro_label), markup);
            g_free(markup);

            if (priv->orig_distro)
                g_free(priv->orig_distro);
            priv->orig_distro = g_strdup(g_value_get_string(value));
            break;
        }

        case PROP_WINDOW_NAME: {
            char *markup;

            /* Do not translate an empty string here. */
            if (strcmp(g_value_get_string(value), "") == 0)
                markup = g_markup_printf_escaped("<span weight='bold' size='large'></span>");
            else
                markup = g_markup_printf_escaped("<span weight='bold' size='large'>%s</span>", _(g_value_get_string(value)));

            gtk_label_set_markup(GTK_LABEL(priv->name_label), markup);
            g_free(markup);

            if (priv->orig_name)
                g_free(priv->orig_name);
            priv->orig_name = g_strdup(g_value_get_string(value));
            break;
        }
    }
}

/**
 * anaconda_base_window_get_beta:
 * @win: a #AnacondaBaseWindow
 *
 * Returns whether or not this window is set to display the beta label.
 *
 * Returns: Whether @win is set to display the betanag warning
 *
 * Since: 1.0
 */
gboolean anaconda_base_window_get_beta(AnacondaBaseWindow *win) {
    return win->priv->is_beta;
}

/**
 * anaconda_base_window_set_beta:
 * @win: a #AnacondaBaseWindow
 * @is_beta: %TRUE to display the betanag warning
 *
 * Sets up the window to display the beta label in red along the top of the
 * screen.
 *
 * Since: 1.0
 */
void anaconda_base_window_set_beta(AnacondaBaseWindow *win, gboolean is_beta) {
    win->priv->is_beta = is_beta;

    if (is_beta)
        gtk_widget_show(win->priv->beta_label);
    else
        gtk_widget_hide(win->priv->beta_label);
}

/**
 * anaconda_base_window_get_action_area:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the action area of @win.  This is the area of the screen where most
 * of the widgets the user interacts with will live.
 *
 * Returns: (transfer none): The action area
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_action_area(AnacondaBaseWindow *win) {
    return win->priv->action_area;
}

/**
 * anaconda_base_window_get_nav_area:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the navigation area of @win.  This is the area at the top of the
 * screen displaying the window's title (if it has one), distribution, and
 * so forth.
 *
 * Returns: (transfer none): The navigation area
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_nav_area(AnacondaBaseWindow *win) {
    return win->priv->nav_area;
}

/**
 * anaconda_base_window_get_help_button:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the help button.
 *
 * Returns: (transfer none): the help button
 *
 * Since: 3.1
 */
GtkWidget *anaconda_base_window_get_help_button(AnacondaBaseWindow *win) {
    return win->priv->help_button;
}

/**
 * anaconda_base_window_get_nav_area_background_window:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the event box that houses background window of the navigation area of @win.
 * Currently, this is only used by #AnacondaSpokeWindow to have a place to store the
 * gradient image.  This function should probably not be used elsewhere.
 *
 * Returns: (transfer none): The event box
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_nav_area_background_window(AnacondaBaseWindow *win) {
    return win->priv->nav_box;
}

/**
 * anaconda_base_window_get_main_box:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the main content area of @win.  This widget holds both the action_area
 * and the nav_area.  Currently, this is only used by #AnacondaStandaloneWindow
 * as a place to store the extra Continue button.  This function should probably
 * not be used elsewhere.
 *
 * Returns: (transfer none): The main content area
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_main_box(AnacondaBaseWindow *win) {
    return win->priv->main_box;
}

/**
 * anaconda_base_window_get_alignment:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the internal alignment widget of @win.  Currently, this is only used
 * by #AnacondaHubWindow to set different alignment values than the spokes have.
 * This function should probably not be used elsewhere.
 *
 * Returns: (transfer none): The alignment widget
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_alignment(AnacondaBaseWindow *win) {
    return win->priv->alignment;
}

static void anaconda_base_window_set_info_bar(AnacondaBaseWindow *win, GtkMessageType ty, const char *msg) {
    GtkWidget *label, *image, *content_area;

    if (win->priv->info_shown)
        return;

    label = gtk_label_new(_(msg));
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(label), PANGO_WRAP_WORD);
    gtk_widget_show(label);

    win->priv->info_bar = gtk_info_bar_new();
    gtk_widget_set_no_show_all(win->priv->info_bar, TRUE);

    /* Wrap the info bar in an event box so clicking on it will do something. */
    win->priv->event_box = gtk_event_box_new();
    gtk_container_add(GTK_CONTAINER(win->priv->event_box), win->priv->info_bar);

    gtk_box_pack_end(GTK_BOX(win->priv->main_box), win->priv->event_box, FALSE, FALSE, 0);

    /* Hook up the signal handler for the info bar.  It will just raise our own
     * custom signal for the whole window.  It will be disconnected when the info
     * bar is hidden.
     */
    gtk_widget_add_events(GTK_WIDGET(win->priv->event_box), GDK_BUTTON_RELEASE_MASK);
    g_signal_connect(win->priv->event_box, "button-release-event",
                     G_CALLBACK(anaconda_base_window_info_bar_clicked), win);

    content_area = gtk_info_bar_get_content_area(GTK_INFO_BAR(win->priv->info_bar));

    image = gtk_image_new_from_icon_name("dialog-warning", GTK_ICON_SIZE_MENU);
    gtk_widget_show(image);
    gtk_container_add(GTK_CONTAINER(content_area), image);

    gtk_container_add(GTK_CONTAINER(content_area), label);
    gtk_info_bar_set_message_type(GTK_INFO_BAR(win->priv->info_bar), ty);
    gtk_widget_show(win->priv->info_bar);
    gtk_widget_show(win->priv->event_box);

    win->priv->info_shown = TRUE;
}

/**
 * anaconda_base_window_set_error:
 * @win: a #AnacondaBaseWindow
 * @msg: a message
 *
 * Causes an info bar to be shown at the bottom of the screen with the provided
 * message.  Only one message may be shown at a time.  In order to show
 * a second message, anaconda_base_window_clear_info must first be called.
 *
 * Since: 1.0
 */
void anaconda_base_window_set_error(AnacondaBaseWindow *win, const char *msg) {
    anaconda_base_window_set_info_bar(win, GTK_MESSAGE_ERROR, msg);
}

/**
 * anaconda_base_window_set_info:
 * @win: a #AnacondaBaseWindow
 * @msg: a message
 *
 * Causes an info bar to be shown at the bottom of the screen with the provided
 * message.  Only one message may be shown at a time.  In order to show
 * a second message, anaconda_base_window_clear_info must first be called.
 *
 * Since: 1.0
 */
void anaconda_base_window_set_info(AnacondaBaseWindow *win, const char *msg) {
    anaconda_base_window_set_info_bar(win, GTK_MESSAGE_INFO, msg);
}

/**
 * anaconda_base_window_set_warning:
 * @win: a #AnacondaBaseWindow
 * @msg: a message
 *
 * Causes an info bar to be shown at the bottom of the screen with the provided
 * message.  Only one message may be shown at a time.  In order to show
 * a second message, anaconda_base_window_clear_info must first be called.
 *
 * Since: 1.0
 */
void anaconda_base_window_set_warning(AnacondaBaseWindow *win, const char *msg) {
    anaconda_base_window_set_info_bar(win, GTK_MESSAGE_WARNING, msg);
}

static gboolean anaconda_base_window_info_bar_clicked(GtkWidget *wiget, GdkEvent *event, AnacondaBaseWindow *win) {
    g_signal_emit(win, window_signals[SIGNAL_INFO_BAR_CLICKED], 0);
    return FALSE;
}

static void anaconda_base_window_help_button_clicked(GtkButton *button,
                                                     AnacondaBaseWindow *win) {
        g_signal_emit(win, window_signals[SIGNAL_HELP_BUTTON_CLICKED], 0);
}

/**
 * anaconda_base_window_clear_info:
 * @win: a #AnacondaBaseWindow
 *
 * Clear and hide any info bar being shown at the bottom of the screen.  This
 * must be called before a second call to anaconda_base_window_set_info takes
 * effect.
 *
 * Since: 1.0
 */
void anaconda_base_window_clear_info(AnacondaBaseWindow *win) {
    if (!win->priv->info_shown)
        return;

    gtk_widget_hide(win->priv->info_bar);
    gtk_widget_destroy(win->priv->info_bar);
    gtk_widget_destroy(win->priv->event_box);
    win->priv->info_shown = FALSE;
}

/**
 * anaconda_base_window_retranslate:
 * @win: a #AnacondaBaseWindow
 *
 * Reload translations for this widget as needed.  Generally, this is not
 * needed.  However when changing the language during installation, we need
 * to be able to make sure the screen gets retranslated.  This function is
 * kind of ugly but avoids having to destroy and reload the screen.
 *
 * Since: 1.0
 */
void anaconda_base_window_retranslate(AnacondaBaseWindow *win) {
    GValue distro = G_VALUE_INIT;

    /* This bit is internal gettext magic. */
    {
        extern int _nl_msg_cat_cntr;
        ++_nl_msg_cat_cntr;
    }

    g_value_init(&distro, G_TYPE_STRING);
    g_value_set_string(&distro, _(win->priv->orig_distro));

    anaconda_base_window_set_property((GObject *) win, PROP_DISTRIBUTION, &distro, NULL);

    /* A window name is not necessarily set. */
    if (strcmp(gtk_label_get_text(GTK_LABEL(win->priv->name_label)), "") != 0) {
        GValue name = G_VALUE_INIT;

        g_value_init(&name, G_TYPE_STRING);
        g_value_set_string(&name, _(win->priv->orig_name));

        anaconda_base_window_set_property((GObject *) win, PROP_WINDOW_NAME, &name, NULL);
    }

    format_beta_label(win, _(win->priv->orig_beta));

    /* retranslate the layout indicator */
    anaconda_layout_indicator_retranslate(ANACONDA_LAYOUT_INDICATOR(win->priv->layout_indicator));
}

static GtkBuildableIface *parent_buildable_iface;

static void
anaconda_base_window_buildable_add_child (GtkBuildable *window,
                                          GtkBuilder *builder,
                                          GObject *child,
                                          const gchar *type) {
    gtk_container_add(GTK_CONTAINER(anaconda_base_window_get_action_area(ANACONDA_BASE_WINDOW(window))),
                      GTK_WIDGET(child));
}

static GObject *
anaconda_base_window_buildable_get_internal_child (GtkBuildable *buildable,
                                                   GtkBuilder *builder,
                                                   const gchar *childname) {
    /* Note that if you add more internal children and want them to be accessible,
     * all their parents must also be made accessible.  This goes all the way up
     * to the top level.
     */
    if (!strcmp(childname, "main_box"))
        return G_OBJECT(anaconda_base_window_get_main_box(ANACONDA_BASE_WINDOW(buildable)));
    else if (!strcmp(childname, "nav_area"))
        return G_OBJECT(ANACONDA_BASE_WINDOW(buildable)->priv->nav_area);
    else if (!strcmp(childname, "nav_box"))
        return G_OBJECT(ANACONDA_BASE_WINDOW(buildable)->priv->nav_box);
    else if (!strcmp(childname, "alignment"))
        return G_OBJECT(ANACONDA_BASE_WINDOW(buildable)->priv->alignment);
    else if (!strcmp(childname, "action_area"))
        return G_OBJECT(anaconda_base_window_get_action_area(ANACONDA_BASE_WINDOW(buildable)));

    return parent_buildable_iface->get_internal_child (buildable, builder, childname);
}

static void anaconda_base_window_buildable_init (GtkBuildableIface *iface) {
    parent_buildable_iface = g_type_interface_peek_parent (iface);
    iface->add_child = anaconda_base_window_buildable_add_child;
    iface->get_internal_child = anaconda_base_window_buildable_get_internal_child;
}

static void format_beta_label (AnacondaBaseWindow *window, const char *markup) {
    gchar *escaped;
    PangoAttrList *attrs;

    /* define attributes -- medium size, bold weight and red text color */
    attrs = pango_attr_list_new();
    pango_attr_list_insert(attrs, pango_attr_scale_new(PANGO_SCALE_MEDIUM));
    pango_attr_list_insert(attrs, pango_attr_weight_new(PANGO_WEIGHT_BOLD));
    pango_attr_list_insert(attrs, pango_attr_foreground_new(0xfdfd, 0x1010, 0x1010));

    /* Some characters may need to be escaped. */
    escaped = g_markup_escape_text(markup, -1);

    gtk_label_set_markup(GTK_LABEL(window->priv->beta_label), escaped);
    gtk_label_set_attributes(GTK_LABEL(window->priv->beta_label), attrs);

    pango_attr_list_unref(attrs);
    g_free(escaped);
}



