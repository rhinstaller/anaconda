/*
 * modules.h
 *
 * Copyright (C) 2007, 2009  Red Hat, Inc.  All rights reserved.
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
 * Author(s): David Cantrell <dcantrell@redhat.com>
 */

#ifndef H_MODULES
#define H_MODULES

#include <glib.h>
#include "loader.h"
#include "moduleinfo.h"

#define MODULES_CONF "/etc/modprobe.d/anaconda.conf"

typedef struct _module_t {
    gchar *name;
    GSList *options;
} module_t;

gboolean mlInitModuleConfig(void);
gboolean mlLoadModule(const gchar *, gchar **);
gboolean mlLoadModuleSet(const gchar *);
gboolean mlAddBlacklist(gchar *);
gboolean mlRemoveBlacklist(gchar *);
void loadKickstartModule(struct loaderData_s *, int, char **);

#endif
