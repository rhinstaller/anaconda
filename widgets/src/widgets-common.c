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

/* Returns path to anaconda widgets data directory using the value of the
 * environment variable ANACONDA_WIDGETS_DATA or WIDGETS_DATADIR macro
 * (defined in Makefile.am) if the environment variable is not defined.
 */
gchar *get_widgets_datadir() {
    gchar *env_value;

    env_value = getenv("ANACONDA_WIDGETS_DATA");
    if (env_value == NULL)
        return WIDGETS_DATADIR;
    else
        return env_value;
}
