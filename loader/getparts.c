/*
 * getparts.c - functions associated with getting partitions for a disk
 *
 * Copyright (C) 1997-2010  Red Hat, Inc.
 * All rights reserved.
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
 * Author(s): Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 *            David Cantrell <dcantrell@redhat.com>
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <ctype.h>
#include <string.h>
#include <glib.h>

#include "../pyanaconda/isys/log.h"

/* see if this is a partition name or not */
static int isPartitionName(char *pname) {

    /* if it doesnt start with a alpha its not one */
    if (!isalpha(*pname) || strstr(pname, "ram"))
	return 0;

    /* if it has a '/' in it then treat it specially */
    if (strchr(pname, '/') && !strstr(pname, "iseries") && 
        !strstr(pname, "i2o")) {
	/* assume its either a /dev/ida/ or /dev/cciss device */
	/* these have form of c?d?p? if its a partition */
	return strchr(pname, 'p') != NULL;
    } else {
	/* if it ends with a digit we're ok */
	return isdigit(pname[strlen(pname)-1]);
    }
}

/* Return array of the names of partitons in /proc/partitions */
gchar **getPartitionsList(gchar *disk) {
    guint i, j;
    gchar *contents = NULL;
    gchar *tokens[] = { NULL, NULL, NULL, NULL };
    gchar **lines, **iter, **rc;
    gsize len;
    GError *e = NULL;
    GSList *parts = NULL, *list = NULL;

    /* read in /proc/partitions and split in to an array of lines */
    if (!g_file_get_contents("/proc/partitions", &contents, &len, &e)) {
        return NULL;
    }

    if (contents == NULL) {
        return NULL;
    }

    iter = lines = g_strsplit_set(contents, "\n", 0);
    g_free(contents);

    /* extract partition names from /proc/partitions lines */
    while (*iter != NULL) {
        /* split the line in to fields */
        gchar **fields = g_strsplit_set(*iter, " ", 0);
        i = j = 0;

        if (g_strv_length(fields) > 0) {
            /* if we're on a non-empty line, toss empty fields so we
             * end up with the major, minor, #blocks, and name fields
             * in positions 0, 1, 2, and 3
             */
            while ((j < g_strv_length(fields)) && (i < 4)) {
                if (g_strcmp0(fields[j], "")) {
                    tokens[i++] = fields[j];
                }

                j++;
            }

            /* skip lines where:
             * - the 'major' column is a non-digit
             * - the '#blocks' column is '1' (indicates extended partition)
             * - the 'name' column is not a valid partition name
             */
            if (isdigit(*tokens[0]) && g_strcmp0(tokens[2], "1") &&
                isPartitionName(tokens[3])) {
                /* if disk is specified, only return a list of partitions
                 * for that device
                 */
                if (disk != NULL && !g_str_has_prefix(tokens[3], disk)) {
                    g_strfreev(fields);
                    iter++;
                    continue;
                }

                parts = g_slist_prepend(parts, g_strdup(tokens[3]));
            }
        }

        g_strfreev(fields);
        iter++;
    }

    i = g_slist_length(parts);
    rc = g_new(gchar *, i + 1);
    rc[i] = NULL;

    for (list = parts; list != NULL; list = list->next) {
        rc[--i] = list->data;
    }

    g_strfreev(lines);
    g_slist_free(parts);
    return rc;
}
