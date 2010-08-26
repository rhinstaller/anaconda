/*
 * readvars.c
 * Copyright (C) 2009, 2010  Red Hat, Inc.
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

#include <stdio.h>
#include <ctype.h>
#include <glib.h>

#include "../pyanaconda/isys/log.h"

/*
 * Given a string with shell-style variables listed (e.g., the contents of an
 * /etc/sysconfig file), parse the contents and generate a hash table of the
 * variables read.  Return the hash table to the caller.  Caller is
 * responsible for freeing memory associated with the hash table:
 *
 *     table = readvars_read_conf("VAR1=val1\nVAR2=val2\n");
 *     g_hash_table_destroy(table);
 *
 * Errors encountered during parsing will result in this function returning
 * NULL.
 *
 * Variables can also be standalone (done so this function can parse the
 * contents of /proc/cmdline).  If they lack a value and are just in the
 * string as a single token, they will become a hash table key with an
 * NULL value.
 */
GHashTable *readvars_parse_string(gchar *contents) {
    gint argc = 0, i = 0;
    gchar **argv = NULL;
    GError *e = NULL;
    GHashTable *conf = g_hash_table_new_full(g_str_hash, g_str_equal,
                                             g_free, g_free);

    if (contents == NULL) {
        return NULL;
    }

    if (!g_shell_parse_argv(contents, &argc, &argv, &e)) {
        if (e != NULL) {
            logMessage(ERROR, "%s(%d): %s", __func__, __LINE__, e->message);
            g_error_free(e);
        }

        return NULL;
    }

    while (i < argc) {
        gchar **tokens = g_strsplit(argv[i], "=", 2);
        guint len = g_strv_length(tokens);
        gchar *key = NULL, *value = NULL;
        e = NULL;

        if (len == 1 || len == 2) {
            key = g_strdup(tokens[0]);
        }

        if (len == 2) {
            value = g_shell_unquote(tokens[1], &e);

            if (value == NULL && e != NULL) {
                logMessage(ERROR, "%s(%d): %s", __func__, __LINE__,
                           e->message);
                g_error_free(e);
            }
        }

        if (key != NULL) {
            g_hash_table_insert(conf, key, value);
        }

        g_strfreev(tokens);
        i++;
    }

    g_strfreev(argv);
    return conf;
}

/*
 * Read contents of file and call readvars_parse_string() with that string,
 * caller is responsible for cleanup in the same style as
 * readvars_parse_string().
 */
GHashTable *readvars_parse_file(gchar *filename) {
    gsize len = 0;
    gchar *input = NULL;
    GError *e = NULL;
    GHashTable *ret = NULL;

    if (filename == NULL) {
        return NULL;
    }

    if (!g_file_get_contents(filename, &input, &len, &e)) {
        if (e != NULL) {
            logMessage(ERROR, "%s(%d): %s", __func__, __LINE__, e->message);
            g_error_free(e);
        }

        g_free(input);
        return NULL;
    }

    ret = readvars_parse_string(input);
    g_free(input);

    return ret;
}
