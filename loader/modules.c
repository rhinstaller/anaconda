/*
 * modules.c - module loading functionality
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007,
 *               2008, 2009  Red Hat, Inc.
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
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 *            David Cantrell <dcantrell@redhat.com>
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#include <glib.h>

#include "../isys/log.h"

#include "loader.h"
#include "modules.h"
#include "windows.h"

/* boot flags */
extern uint64_t flags;

static GSList *modopts = NULL;
static GSList *blacklist = NULL;

static gboolean _isValidModule(gchar *module) {
    gint fd = -1, i = 0;
    gchar *path = NULL, *buf = NULL, *modname = NULL;
    gchar *ends[] = { ".ko.gz:", ".ko:", NULL };
    struct utsname utsbuf;
    struct stat sbuf;

    if (uname(&utsbuf) == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        return FALSE;
    }

    if (asprintf(&path, "/lib/modules/%s/modules.dep", utsbuf.release) == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        return FALSE;
    }

    if (stat(path, &sbuf) == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        free(path);
        return FALSE;
    }

    if ((fd = open(path, O_RDONLY)) == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        free(path);
        return FALSE;
    } else {
        free(path);
    }

    buf = mmap(0, sbuf.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (!buf || buf == MAP_FAILED) {
        close(fd);
        return FALSE;
    }

    close(fd);

    while (ends[i] != NULL) {
        if (asprintf(&modname, "/%s%s", module, ends[i]) == -1) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
            return FALSE;
        }

        if (g_strstr_len(buf, -1, modname) != NULL) {
            munmap(buf, sbuf.st_size);
            free(modname);
            return TRUE;
        }

        free(modname);
        modname = NULL;
        i++;
    }

    munmap(buf, sbuf.st_size);
    return FALSE;
}

static void _addOption(const gchar *module, const gchar *option) {
    gboolean found = FALSE;
    GSList *iterator = modopts;
    module_t *modopt = NULL;
    gchar *tmpopt = g_strdup(option);

    while (iterator != NULL) {
        modopt = (module_t *) iterator->data;

        if (!strncmp(modopt->name, module, strlen(modopt->name))) {
            found = TRUE;
            break;
        }

        iterator = g_slist_next(iterator);
    }

    if (found) {
        modopt->options = g_slist_append(modopt->options, tmpopt);
    } else {
        if ((modopt = g_malloc0(sizeof(module_t))) == NULL) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
            abort();
        }

        modopt->name = g_strdup(module);
        modopt->options = NULL;
        modopt->options = g_slist_append(modopt->options, tmpopt);
        modopts = g_slist_append(modopts, modopt);
    }

    return;
}

static gboolean _writeModulesConf(gchar *conf) {
    gint fd = -1, rc = 0, len = 0;
    GSList *iterator = modopts;
    GString *buf = g_string_new("# Module options and blacklists written by anaconda\n");

    if (conf == NULL) {
        /* XXX: should this use mkstemp() ? */
        conf = "/tmp/modprobe.conf";
    }

    if ((fd = open(conf, O_WRONLY | O_CREAT, 0644)) == -1) {
        logMessage(ERROR, "error opening to %s: %m", conf);
        return FALSE;
    }

    while (iterator != NULL) {
        module_t *modopt = iterator->data;
        GSList *optiterator = modopt->options;
        g_string_append_printf(buf, "options %s", modopt->name);

        while (optiterator != NULL) {
            gchar *option = (gchar *) optiterator->data;
            g_string_append_printf(buf, " %s", option);
            optiterator = g_slist_next(optiterator);
        }

        g_string_append(buf, "\n");
        iterator = g_slist_next(iterator);
    }

    iterator = blacklist;

    while (iterator != NULL) {
        gchar *module = (gchar *) iterator->data;
        g_string_append_printf(buf, "blacklist %s\n", module);
        iterator = g_slist_next(iterator);
    }

    len = buf->len;
    rc = write(fd, buf->str, len);
    close(fd);
    g_string_free(buf, TRUE);

    return (rc == len);
}

static gboolean _doLoadModule(const gchar *module, gchar **args) {
    gint child;
    gint status;

    if (!(child = fork())) {
        gint i, rc;
        gchar **argv = NULL;
        gint fd = -1;

        if ((argv = g_malloc0(3 * sizeof(*argv))) == NULL) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
            abort();
        }

        if ((fd = open("/dev/tty3", O_RDWR)) == -1) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        } else {
            dup2(fd, 0);
            dup2(fd, 1);
            dup2(fd, 2);
            close(fd);
        }

        argv[0] = "/sbin/modprobe";
        argv[1] = g_strdup(module);
        argv[2] = NULL;

        if (args) {
            for (i = 0; args[i] ; i++) {
                _addOption(module, args[i]);
            }
            _writeModulesConf(MODULES_CONF);
        }

        rc = execv("/sbin/modprobe", argv);
        g_strfreev(argv);
        _exit(rc);
    }

    waitpid(child, &status, 0);

    if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status))) {
        return TRUE;
    } else {
        return FALSE;
    }
}

gboolean mlInitModuleConfig(void) {
    gint i = 0;
    gchar *cmdline = NULL;
    gchar **options = NULL;
    GError *readErr = NULL;

    /* read module options out of /proc/cmdline and into a structure */
    if (!g_file_get_contents("/proc/cmdline", &cmdline, NULL, &readErr)) {
        logMessage(ERROR, "unable to read /proc/cmdline: %s", readErr->message);
        g_error_free(readErr);
        return _writeModulesConf(MODULES_CONF);
    }

    cmdline = g_strchomp(cmdline);
    options = g_strsplit(cmdline, " ", 0);
    g_free(cmdline);

    if (options == NULL) {
        return _writeModulesConf(MODULES_CONF);
    }

    while (options[i] != NULL) {
        gchar *tmpmod = NULL;
        gchar **fields = NULL;

        if (g_strstr_len(options[i], -1, "=") == NULL) {
            i++;
            continue;
        }

        if (!strncmp(options[i], "blacklist=", 10)) {
            if ((fields = g_strsplit(options[i], "=", 0)) != NULL) {
                if (g_strv_length(fields) == 2) {
                    tmpmod = g_strdup(fields[1]);
                    blacklist = g_slist_append(blacklist, tmpmod);
                }
            }
        } else if ((fields = g_strsplit(options[i], ".", 0)) != NULL) {
            if (g_strv_length(fields) == 2) {
                if (_isValidModule(fields[0])) {
                    _addOption(fields[0], fields[1]);
                }
            }
        }

        if (fields != NULL) {
            g_strfreev(fields);
        }

        i++;
    }

    if (options != NULL) {
        g_strfreev(options);
    }

    return _writeModulesConf(MODULES_CONF);
}

/* load a module with a given list of arguments */
gboolean mlLoadModule(const gchar *module, gchar **args) {
    return _doLoadModule(module, args);
}

/* loads a : separated list of modules */
gboolean mlLoadModuleSet(const gchar *modNames) {
    gchar **mods = NULL, **iterator = NULL;
    gboolean rc = FALSE;

    if (modNames == NULL) {
        return FALSE;
    }

    if ((mods = g_strsplit(modNames, ":", 0)) != NULL) {
        iterator = mods;

        while (*iterator != NULL) {
            rc |= _doLoadModule(*iterator, NULL);
            iterator++;
        }
    } else {
        return FALSE;
    }

    g_strfreev(mods);
    return rc;
}

gboolean mlAddBlacklist(gchar *module) {
    gchar *tmpmod = NULL;

    if (module == NULL) {
        return FALSE;
    }

    tmpmod = g_strdup(module);
    blacklist = g_slist_append(blacklist, tmpmod);
    return _writeModulesConf(MODULES_CONF);
}

gboolean mlRemoveBlacklist(gchar *module) {
    GSList *iterator = blacklist;

    if (module == NULL) {
        return FALSE;
    }

    while (iterator != NULL) {
        if (!strcmp((gchar *) iterator->data, module)) {
            iterator = g_slist_delete_link(blacklist, iterator);
            continue;
        } else {
            iterator = g_slist_next(iterator);
        }
    }

    return TRUE;
}

void loadKickstartModule(struct loaderData_s * loaderData,
                         int argc, char **argv) {
    gchar *opts = NULL;
    gchar *module = NULL;
    gchar **args = NULL, **remaining = NULL;
    gboolean rc;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksDeviceOptions[] = {
        { "opts", 0, 0, G_OPTION_ARG_STRING, &opts, NULL, NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksDeviceOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to device kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if ((remaining != NULL) && (g_strv_length(remaining) == 1)) {
        module = remaining[0];
    }

    if (!module) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("A module name must be specified for "
                         "the kickstart device command."));
        return;
    }

    if (opts) {
        args = g_strsplit(opts, " ", 0);
    }

    rc = mlLoadModule(module, args);
    g_strfreev(args);
    return;
}
