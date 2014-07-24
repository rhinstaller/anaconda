/* Copyright (C) 2013 Red Hat, Inc
 *
 * Common functions for AnacondaWidgets
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
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
 *
 * Author: David Shea <dshea@redhat.com>
 *
 */

#include "config.h"

#include "widgets-common.h"

#include <stdlib.h>
#include <string.h>

/**
 * anaconda_get_widgets_datadir:
 *
 * Return the directory containing the anaconda widgets data files.
 *
 * The widgets data directory contains the pixmaps used by the anaconda
 * widgets. This directory defaults to ${prefix}/share/anaconda/pixmaps, but
 * it may be overriden at runtime using the ANACONDA_WIDGETS_DATA environment
 * variable.
 *
 * Returns: the widgets data directory.
 */
const gchar *anaconda_get_widgets_datadir(void) {
    gchar *env_value;

    env_value = getenv("ANACONDA_WIDGETS_DATA");
    if (env_value == NULL)
        return WIDGETS_DATADIR;
    else
        return env_value;
}

static void free_pixbuf(guchar *pixels, gpointer data) {
    g_free(pixels);
}

/**
 * anaconda_make_pixbuf:
 * @data: (array): The data that would be passed to gdk_pixbuf_new_from_data() were
 * that actually possible
 * @has_alpha: Whether the data has an opacity channel
 * @width: Width of the image in pixels, must be > 0
 * @height: Height of the image in pixels, must be > 0
 * @rowstride: Distance in bytes between row starts
 *
 * Create a GdkPixbuf in a way that actually works in gobject-introspection bindings.
 *
 * See also: https://bugzilla.gnome.org/show_bug.cgi?id=732297
 *
 * colorspace and bits_per_sample are not provided as parameters because it would break
 * something if they were ever not GDK_COLORSPACE_RGB and 8, respectively.
 *
 * Returns: (transfer full): A new GdkPixbuf
 *
 * Since: 3.0
 */
GdkPixbuf * anaconda_make_pixbuf(const guint8 *data, gboolean has_alpha,
        int width, int height, int rowstride) {
    guchar *data_copy;

    /* Length of the data is max_y * rowstride + max_x * n_channels */
    size_t data_len = (width * rowstride) + (height * (has_alpha ? 4 : 3));

    /* Create a copy of the data because whoever wrote gdk-pixbuf doesn't understand
     * reference ownership. */
    data_copy = g_malloc(data_len);
    memcpy(data_copy, data, data_len);
    return gdk_pixbuf_new_from_data(data_copy,
            GDK_COLORSPACE_RGB,
            has_alpha,
            8,
            width,
            height,
            rowstride,
            free_pixbuf,
            NULL
            );
}
