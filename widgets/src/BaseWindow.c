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

#include <string.h>

#include "BaseWindow.h"
#include "intl.h"

/**
 * SECTION: BaseWindow
 * @title: AnacondaBaseWindow
 * @short_description: Top-level, non-resizeable window
 *
 * A #AnacondaBaseWindow is a top-level, non-resizeable window that contains
 * other widgets and serves as the base class from which all other specialized
 * Anaconda windows are derived.  It is undecorated.
 *
 * The window consists of two areas:
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
 * the @action_area as an internal child with the name "action_area".
 * </para>
 * <example>
 * <title>A <structname>AnacondaBaseWindow</structname> UI definition fragment.</title>
 * <programlisting><![CDATA[
 * <object class="AnacondaBaseWindow" id="window1">
 *     <child internal-child="action_area">
 *         <object class="GtkVBox" id="vbox1">
 *             <child>
 *                 <object class="GtkLabel" id="label1">
 *                     <property name="label" translatable="yes">THIS IS ONE LABEL</property>
 *                 </object>
 *             </child>
 *             <child>
 *                 <object class="GtkLabel" id="label2">
 *                     <property name="label" translatable="yes">THIS IS ANOTHER LABEL</property>
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
    PROP_DISTRIBUTION = 1,
    PROP_WINDOW_NAME
};

#define DEFAULT_DISTRIBUTION  "DISTRIBUTION INSTALLATION"
#define DEFAULT_WINDOW_NAME   "SPOKE NAME"

struct _AnacondaBaseWindowPrivate {
    gboolean    is_beta, info_shown;
    GtkWidget  *main_box, *info_bar;
    GtkWidget  *alignment;
    GtkWidget  *nav_area, *action_area;
    GtkWidget  *name_label, *distro_label, *beta_label;
};

static void anaconda_base_window_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_base_window_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_base_window_buildable_init(GtkBuildableIface *iface);

G_DEFINE_TYPE_WITH_CODE(AnacondaBaseWindow, anaconda_base_window, GTK_TYPE_WINDOW,
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

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_BASE_WINDOW,
                                            AnacondaBaseWindowPrivate);

    win->priv->is_beta = FALSE;
    win->priv->info_shown = FALSE;

    /* Set properties on the parent (Gtk.Window) class. */
    gtk_window_set_decorated(GTK_WINDOW(win), FALSE);
    gtk_window_maximize(GTK_WINDOW(win));
    gtk_container_set_border_width(GTK_CONTAINER(win), 6);

    /* First, construct a top-level box that everything will go in.  Remember
     * a Window can only hold one widget, and we may very well need to add
     * more things later.
     */
    win->priv->main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_box_set_spacing(GTK_BOX(win->priv->main_box), 6);
    gtk_container_add(GTK_CONTAINER(win), win->priv->main_box);

    /* Then the navigation area that sits as the first item in the main box
     * for every Window class.
     */
    win->priv->nav_area = gtk_grid_new();
    gtk_grid_set_row_homogeneous(GTK_GRID(win->priv->nav_area), FALSE);
    gtk_grid_set_column_homogeneous(GTK_GRID(win->priv->nav_area), FALSE);
    gtk_box_pack_start(GTK_BOX(win->priv->main_box), win->priv->nav_area, FALSE, FALSE, 0);

    /* Second in the main box is an alignment, because we want to be able
     * to control the amount of space the Window's content takes up on the
     * screen.
     */
    win->priv->alignment = gtk_alignment_new(0.5, 0.0, 0.0, 0.5);
    gtk_box_pack_start(GTK_BOX(win->priv->main_box), win->priv->alignment, TRUE, TRUE, 0);

    /* The action_area goes inside the alignment and represents the main
     * place for content to go.
     */
    win->priv->action_area = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_box_set_spacing(GTK_BOX(win->priv->action_area), 6);
    gtk_container_add(GTK_CONTAINER(win->priv->alignment), win->priv->action_area);

    /* And now we can finally create the widgets that go in all those layout
     * pieces up above.
     */

    /* Create the name label. */
    win->priv->name_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span weight='bold'>%s</span>", _(DEFAULT_WINDOW_NAME));
    gtk_label_set_markup(GTK_LABEL(win->priv->name_label), markup);
    g_free(markup);
    gtk_misc_set_alignment(GTK_MISC(win->priv->name_label), 0, 0);
    gtk_widget_set_hexpand(win->priv->name_label, TRUE);

    /* Create the distribution label. */
    win->priv->distro_label = gtk_label_new(_(DEFAULT_DISTRIBUTION));
    gtk_misc_set_alignment(GTK_MISC(win->priv->distro_label), 0, 0);

    /* Create the betanag label. */
    win->priv->beta_label = gtk_label_new(NULL);
    markup = g_markup_printf_escaped("<span foreground='red'>%s</span>", _("PRE-RELEASE / TESTING"));
    gtk_label_set_markup(GTK_LABEL(win->priv->beta_label), markup);
    g_free(markup);
    gtk_misc_set_alignment(GTK_MISC(win->priv->beta_label), 0, 0);
    gtk_widget_set_no_show_all(win->priv->beta_label, TRUE);

    /* Add everything to the nav area. */
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->name_label, 0, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->distro_label, 1, 0, 1, 1);
    gtk_grid_attach(GTK_GRID(win->priv->nav_area), win->priv->beta_label, 1, 1, 1, 1);
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
            gtk_label_set_text(GTK_LABEL(priv->distro_label), g_value_get_string(value));
            break;
        }

        case PROP_WINDOW_NAME: {
            char *markup = g_markup_printf_escaped("<span weight='bold'>%s</span>", g_value_get_string(value));
            gtk_label_set_markup(GTK_LABEL(priv->name_label), markup);
            g_free(markup);
            break;
        }
    }
}

/**
 * anaconda_base_window_get_beta:
 * @win: a #AnacondaBaseWindow
 *
 * Returns whether or not this window is set to display the betanag warning.
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
 * Sets up the window to display the betanag warning in red along the top of
 * the screen.
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
 * Returns the action area of @win.
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
 * Returns the navigation area of @win.
 *
 * Returns: (transfer none): The navigation area
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_nav_area(AnacondaBaseWindow *win) {
    return win->priv->nav_area;
}

/**
 * anaconda_base_window_get_main_box:
 * @win: a #AnacondaBaseWindow
 *
 * Returns the main content area of @win.
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
 * Returns the internal alignment widget of @win.
 *
 * Returns: (transfer none): The alignment widget
 *
 * Since: 1.0
 */
GtkWidget *anaconda_base_window_get_alignment(AnacondaBaseWindow *win) {
    return win->priv->alignment;
}

/**
 * anaconda_base_window_set_info:
 * @win: a #AnacondaBaseWindow
 * @ty: a #GtkMessageType
 * @msg: a message
 *
 * Causes an info bar to be shown at the bottom of the screen with the provided
 * message.  The type argument is used to determine the background color of the
 * info bar area.  Only one message may be shown at a time.  In order to show
 * a second message, anaconda_base_window_clear_info must first be called.
 *
 * Since: 1.0
 */
void anaconda_base_window_set_info(AnacondaBaseWindow *win, GtkMessageType ty, const char *msg) {
    GtkWidget *label, *image, *content_area;

    if (win->priv->info_shown)
        return;

    label = gtk_label_new(msg);
    gtk_widget_show(label);

    win->priv->info_bar = gtk_info_bar_new();
    gtk_widget_set_no_show_all(win->priv->info_bar, TRUE);
    gtk_box_pack_end(GTK_BOX(win->priv->main_box), win->priv->info_bar, FALSE, FALSE, 0);

    content_area = gtk_info_bar_get_content_area(GTK_INFO_BAR(win->priv->info_bar));

    image = gtk_image_new_from_stock(GTK_STOCK_DIALOG_WARNING, GTK_ICON_SIZE_MENU);
    gtk_widget_show(image);
    gtk_container_add(GTK_CONTAINER(content_area), image);

    gtk_container_add(GTK_CONTAINER(content_area), label);
    gtk_info_bar_set_message_type(GTK_INFO_BAR(win->priv->info_bar), ty);
    gtk_widget_show(win->priv->info_bar);

    win->priv->info_shown = TRUE;
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
    win->priv->info_shown = FALSE;
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
    if (!strcmp(childname, "main_box"))
        return G_OBJECT(anaconda_base_window_get_main_box(ANACONDA_BASE_WINDOW(buildable)));
    else if (!strcmp(childname, "nav_area"))
        return G_OBJECT(ANACONDA_BASE_WINDOW(buildable)->priv->nav_area);
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
