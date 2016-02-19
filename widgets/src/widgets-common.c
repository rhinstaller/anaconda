/* Copyright (C) 2013 Red Hat, Inc
 *
 * Common functions for AnacondaWidgets
 *
 * This copyrighted material is made available to anyone wishing to use,
 * modify, copy, or redistribute it subject to the terms and conditions of
 * the GNU General Public License v.2, or (at your option) any later version.
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY expressed or implied, including the implied warranties of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 * Public License for more details.  You should have received a copy of the
 * GNU General Public License along with this program; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
 * 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
 * source code or documentation are not subject to the GNU General Public
 * License and may only be used or replicated with the express permission of
 * Red Hat, Inc.
 *
 * Author: David Shea <dshea@redhat.com>
 *
 */

#include "config.h"
#include "widgets-common.h"

#include <gtk/gtk.h>

/**
 * anaconda_widget_apply_stylesheet:
 * @widget: The widget to apply the style data to.
 * @name: The name of the widget's stylesheet.
 *
 * Apply CSS data to a widget's #GtkStyleContext. The data will not affect any
 * other widgets, including children of this widget.
 *
 * The CSS data lives in the resource bundle, the advantage of which is that
 * the stylesheet is just a normal stylesheet in the source tree with normal
 * syntax highlighting and no weird C string stuff or anything. The
 * disadvantage is that the stylesheet can only be applied to one widget at a
 * time so there's a bunch of tiny little stylesheets in the resources
 * directory, but that's the world we live in.
 *
 * The stylesheet should live in the resources/ directory in the source tree
 * and will be fetched as /org/fedoraproject/anaconda/widgets/<name>.css.
 *
 * The stylesheet is added to the style context at one less than
 * #GTK_STYLE_PROVIDER_PRIORITY_APPLICATION so that the style will not
 * overridden by a sloppy wildcard in a theme somewhere, but it will be
 * overridden by the application-level stylesheet, which may include
 * product-specific customizations.
 *
 */
void anaconda_widget_apply_stylesheet(GtkWidget *widget, const gchar *name)
{
    GtkCssProvider *style_provider;
    GtkStyleContext *style_context;
    gchar *resource_path;

    resource_path = g_strdup_printf("/org/fedoraproject/anaconda/widgets/%s.css", name);

    style_provider = gtk_css_provider_new();
    gtk_css_provider_load_from_resource(style_provider, resource_path);
    g_free(resource_path);

    style_context = gtk_widget_get_style_context(widget);
    gtk_style_context_add_provider(style_context, GTK_STYLE_PROVIDER(style_provider),
            GTK_STYLE_PROVIDER_PRIORITY_APPLICATION - 1);
}
