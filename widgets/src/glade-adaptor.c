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

/* This file contains code called by glade when it creates, reads, writes, or
 * otherwise manipulates anaconda-specific widgets.  Each function in this file
 * that glade should call must be referenced in a glade-widget-class stanza of
 * glade/AnacondaWidgets.xml.
 *
 * This file relies on a lot of halfway documented magic.  Good luck.
 */
#include <gladeui/glade-project.h>
#include <gladeui/glade-widget.h>
#include <gladeui/glade-widget-adaptor.h>

#include <gtk/gtk.h>

#include "BaseWindow.h"
#include "HubWindow.h"
#include "SpokeWindow.h"

void anaconda_standalone_window_post_create(GladeWidgetAdaptor *adaptor,
                                            GObject *object, GladeCreateReason reason) {
    GladeWidget *widget, *action_area_widget, *nav_area_widget, *alignment_widget;
    AnacondaBaseWindow *window;

    g_return_if_fail(ANACONDA_IS_BASE_WINDOW(object));

    widget = glade_widget_get_from_gobject(GTK_WIDGET(object));
    if (!widget)
        return;

    /* Set these properties both on creating a new widget and on loading a
     * widget from an existing file.  Too bad I have to duplicate this information
     * from the widget source files, but glade has no way of figuring it out
     * otherwise.
     */
    window = ANACONDA_BASE_WINDOW(object);
    action_area_widget = glade_widget_get_from_gobject(anaconda_base_window_get_action_area(window));
    glade_widget_property_set(action_area_widget, "size", 1);

    nav_area_widget = glade_widget_get_from_gobject(anaconda_base_window_get_nav_area(window));
    glade_widget_property_set(nav_area_widget, "n-rows", 2);
    glade_widget_property_set(nav_area_widget, "n-columns", 2);

    alignment_widget = glade_widget_get_from_gobject(anaconda_base_window_get_alignment(window));

    glade_widget_property_set(alignment_widget, "xalign", 0.5);
    glade_widget_property_set(alignment_widget, "yalign", 0.0);
    glade_widget_property_set(alignment_widget, "xscale", 1.0);
    glade_widget_property_set(alignment_widget, "yscale", 1.0);

    /* Set padding on hubs */
    if (ANACONDA_IS_HUB_WINDOW(object)) {
        glade_widget_property_set(alignment_widget, "left-padding", 12);
        glade_widget_property_set(alignment_widget, "right-padding", 6);
    }
}
