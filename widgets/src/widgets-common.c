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

#include <glib.h>
#include <stdlib.h>

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
