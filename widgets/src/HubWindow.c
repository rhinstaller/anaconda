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

#include "config.h"

#include "BaseStandalone.h"
#include "HubWindow.h"
#include "intl.h"

/**
 * SECTION: HubWindow
 * @title: AnacondaHubWindow
 * @short_description: Window for displaying a Hub
 *
 * A #AnacondaHubWindow is a widget that displays a hub on the screen.  A Hub
 * allows selection of multiple configuration spokes from a single interface,
 * as well as a place to display current configuration selections.
 *
 * The AnacondaHubWindow consists of three areas:
 *
 * - A navigation area in the top of the screen, inherited from #AnacondaBaseWindow.
 *
 * - A selection area in the middle of the screen, taking up a majority of the space.
 *   This is where spokes will be displayed and the user can decide what to do.
 *
 * - An action area on the bottom of the screen.  This area is different for
 *   different kinds of hubs.  It may have buttons, or it may have progress
 *   information.
 *
 * <refsect2 id="AnacondaHubWindow-BUILDER-UI"><title>AnacondaHubWindow as GtkBuildable</title>
 * <para>
 * The AnacondaHubWindow implementation of the #GtkBuildable interface exposes
 * the @nav_area, @action_area and @scrolled_window as internal children with the names
 * "nav_area", "action_area" and "scrolled_window".  action_area, in this case,
 * is largely there to give a box to contain both the scrolled_window and a
 * #GtkButtonBox.
 * </para>
 * <example>
 * <title>A <structname>AnacondaHubWindow</structname> UI definition fragment.</title>
 * <programlisting><![CDATA[
 * <object class="AnacondaHubWindow" id="hub1">
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
 *                             <child internal-child="scrolled_window">
 *                                 <object class="GtkScrolledWindow" id="scrolled_window1">
 *                                     <child>...</child>
 *                                 </object>
 *                             </child>
 *                         </object>
 *                     </child>
 *                 </object>
 *             </child>
 *         </object>
 *     <child>
 *         <object class="GtkButtonBox" id="buttonbox1">
 *             <child>...</child>
 *         </object>
 *     </child>
 * </object>
 * ]]></programlisting>
 * </example>
 * </refsect2>
 */

struct _AnacondaHubWindowPrivate {
    GtkWidget *scrolled_window;
};

static void anaconda_hub_window_buildable_init(GtkBuildableIface *iface);

G_DEFINE_TYPE_WITH_CODE(AnacondaHubWindow, anaconda_hub_window, ANACONDA_TYPE_BASE_STANDALONE,
                        G_IMPLEMENT_INTERFACE(GTK_TYPE_BUILDABLE, anaconda_hub_window_buildable_init))

static void anaconda_hub_window_class_init(AnacondaHubWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    g_type_class_add_private(object_class, sizeof(AnacondaHubWindowPrivate));
}

/**
 * anaconda_hub_window_new:
 *
 * Creates a new #AnacondaHubWindow, which is a window designed for displaying
 * multiple spokes in one location.
 *
 * Returns: A new #AnacondaHubWindow.
 */
GtkWidget *anaconda_hub_window_new() {
    return g_object_new(ANACONDA_TYPE_HUB_WINDOW, NULL);
}

static void anaconda_hub_window_init(AnacondaHubWindow *win) {
    GtkWidget *action_area = anaconda_base_window_get_action_area(ANACONDA_BASE_WINDOW(win));

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_HUB_WINDOW,
                                            AnacondaHubWindowPrivate);

    win->priv->scrolled_window = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(win->priv->scrolled_window),
                                   GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_box_pack_start(GTK_BOX(action_area), win->priv->scrolled_window, TRUE, TRUE, 0);

    /* The hub has different alignment requirements than a spoke. */
G_GNUC_BEGIN_IGNORE_DEPRECATIONS
    gtk_alignment_set_padding(GTK_ALIGNMENT(anaconda_base_window_get_alignment(ANACONDA_BASE_WINDOW(win))),
            0, 0, 12, 6);
G_GNUC_END_IGNORE_DEPRECATIONS
}

/**
 * anaconda_hub_window_get_spoke_area:
 * @win: a #AnacondaHubWindow
 *
 * Returns the scrolled window of @win where spokes may be displayed
 *
 * Returns: (transfer none): The spoke area
 *
 * Since: 1.0
 */
GtkWidget *anaconda_hub_window_get_spoke_area(AnacondaHubWindow *win) {
    return win->priv->scrolled_window;
}

static GtkBuildableIface *parent_buildable_iface;

static GObject *
anaconda_hub_window_buildable_get_internal_child (GtkBuildable *buildable,
                                                  GtkBuilder *builder,
                                                  const gchar *childname) {
    if (strcmp (childname, "scrolled_window") == 0)
        return G_OBJECT(anaconda_hub_window_get_spoke_area(ANACONDA_HUB_WINDOW(buildable)));

    return parent_buildable_iface->get_internal_child (buildable, builder, childname);
}

static void anaconda_hub_window_buildable_init (GtkBuildableIface *iface) {
    parent_buildable_iface = g_type_interface_peek_parent (iface);
    iface->get_internal_child = anaconda_hub_window_buildable_get_internal_child;
}
