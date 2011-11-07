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
#include "SpokeWindow.h"

void anaconda_standalone_window_post_create(GladeWidgetAdaptor *adaptor,
                                            GObject *object, GladeCreateReason reason) {
    GladeWidget *widget, *actionarea_widget;
    AnacondaBaseWindow *window;

    if (reason != GLADE_CREATE_USER)
        return;

    g_return_if_fail(ANACONDA_IS_BASE_WINDOW(object));

    widget = glade_widget_get_from_gobject(GTK_WIDGET(object));
    if (!widget)
        return;

    window = ANACONDA_BASE_WINDOW(object);
    actionarea_widget = glade_widget_get_from_gobject(anaconda_base_window_get_action_area(window));

    if (ANACONDA_IS_SPOKE_WINDOW(object))
        glade_widget_property_set(actionarea_widget, "size", 2);
    else
        glade_widget_property_set(actionarea_widget, "size", 3);
}

void anaconda_standalone_window_write_widget(GladeWidgetAdaptor *adaptor,
                                             GladeWidget *widget,
                                             GladeXmlContext *context, GladeXmlNode *node) {
    GladeProperty *startup_id_prop;

    if (!glade_xml_node_verify (node, GLADE_XML_TAG_WIDGET))
        return;

    /* Set a bogus startup-id in the output XML file.  This doesn't really seem
     * like it should be necessary, but glade will crash if I don't.
     */
    startup_id_prop = glade_widget_get_property(widget, "startup-id");
    glade_property_set(startup_id_prop, "filler");
    glade_property_write(startup_id_prop, context, node);

    /* Chain up and write the parent's properties */
    GWA_GET_CLASS (GTK_TYPE_WINDOW)->write_widget (adaptor, widget, context, node);
}
