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
