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

#ifndef _INTL_H
#define _INTL_H

#include "config.h"
#include "gettext.h"

#define _(x) dgettext("anaconda", x)
#define N_(String) String

#ifdef ENABLE_NLS
#define P_(String) g_dgettext("anaconda-properties",String)
#else
#define P_(String) (String)
#endif

#endif
