/*
 * modules.c - module loading functionality
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
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
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

#include "loader.h"
#include "log.h"
#include "modules.h"
#include "windows.h"

#include "../isys/cpio.h"

/* boot flags */
extern uint64_t flags;

static int writeModulesConf(char *conf);
struct moduleOptions {
    char *name;
    int numopts;
    char **options;
};

static struct moduleOptions * modopts = NULL;
static int nummodopts = -1;

static char ** blacklists = NULL;
static int numblacklists = 0;

static void readBlacklist() {
    int fd;
    size_t len = 0;
    char buf[1024];
    char *start, *end;

    if ((fd = open("/proc/cmdline", O_RDONLY)) < 0)
        return;

    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    buf[len] = '\0';
    start = buf;
    
    while (start) {
        end = strstr(start, " ");
        if (end)
            *end = '\0';
        if (strncmp(start,"blacklist=",10)) {
            if (!end)
                break;
            start = end + 1;
            continue;
        }
        printf("found %s\n",start);

        blacklists = realloc(blacklists, sizeof(*blacklists) * (numblacklists + 1));
        blacklists[numblacklists] = strdup(start+10);
        numblacklists++;

        if (!end)
            break;
        start = end + 1;
    }
}

void mlAddBlacklist(char *module) {
    blacklists = realloc(blacklists, sizeof(*blacklists) * (numblacklists + 1));
    blacklists[numblacklists] = strdup(module);
    numblacklists++;
    writeModulesConf("/etc/modprobe.d/anaconda");
}

static void addOption(const char *module, const char *option) {
    int found = 0, i;

    found = 0;
    for (i = 0; i < nummodopts; i++) {
        if (strncmp(modopts[i].name, module, strlen(modopts[i].name)))
            continue;
        modopts[i].numopts++;
        found = 1;
        break;
    }
    if (found == 0) {
        modopts = realloc(modopts, sizeof(*modopts) * (nummodopts + 1));
        modopts[nummodopts].name = strdup(module);
        modopts[nummodopts].numopts = 1;
        modopts[nummodopts++].options = NULL;
    }
    modopts[i].options = realloc(modopts[i].options,
                                sizeof(modopts[i].options) *
                                (modopts[i].numopts + 1));
    modopts[i].options[modopts[i].numopts - 1] = strdup(option);
    modopts[i].options[modopts[i].numopts] = NULL;
}

static int isValidModule(char *module) {
    char mod_name[64], path[512];
    struct utsname utsbuf;
    struct stat sbuf;
    char *buf;
    
    uname(&utsbuf);
    snprintf(path, 512, "/lib/modules/%s/modules.dep", utsbuf.release);
    if (!stat(path, &sbuf)) {
        int fd;

        fd = open(path, O_RDONLY);
        buf = mmap(0, sbuf.st_size, PROT_READ, MAP_SHARED, fd, 0);
        if (!buf || buf == MAP_FAILED)
            return 0;
        close(fd);
        snprintf(mod_name, 64, "/%s.ko.gz:", module);
        if (strstr(buf, mod_name)) {
            munmap(buf, sbuf.st_size);
            return 1;
        }
        snprintf(mod_name, 64, "/%s.ko:", module);
        if (strstr(buf, mod_name)) {
            munmap(buf, sbuf.st_size);
            return 1;
        }
        munmap(buf, sbuf.st_size);
    }
    return 0;
}

/* read module options out of /proc/cmdline and into a structure */
static void readModuleOpts() {
    int fd;
    size_t len = 0;
    char buf[1024];
    char *start, *end, *sep;

    nummodopts = 0;
    if ((fd = open("/proc/cmdline", O_RDONLY)) < 0)
        return;

    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    buf[len] = '\0';
    start = buf;

    while (start) {
        end = strstr(start, " ");
        if (end)
            *end = '\0';
        sep = strstr(start, "=");
        if (sep == NULL) {
            if (!end)
                break;
            start = end + 1;
            continue;
        }
        sep = strstr(start, ".");
        if (sep == NULL) {
            if (!end)
                break;
            start = end + 1;
            continue;
        }
        *sep = '\0'; sep++;

        if (isValidModule(start))
            addOption(start, sep);

        if (!end)
            break;
        start = end + 1;
    }
}

static int doLoadModule(const char *module, char ** args) {
    int child;
    int status;

    if (!(child = fork())) {
        int i, rc;
        char **argv = malloc(3 * sizeof(*argv));
        int fd = open("/dev/tty3", O_RDWR);

        dup2(fd, 0);
        dup2(fd, 1);
        dup2(fd, 2);
        close(fd);

        argv[0] = "/sbin/modprobe";
        argv[1] = strdup(module);
        argv[2] = NULL;
        if (args) {
            for (i = 0; args[i] ; i++) {
                addOption(module, args[i]);
            }
            writeModulesConf("/etc/modprobe.d/anaconda");
        }
        rc = execv("/sbin/modprobe", argv);
        _exit(rc);
    }

    waitpid(child, &status, 0);

    if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status))) {
        return 1;
    } else {
        return 0;
    }
}

void mlRemoveBlacklist(char *module) {
    int i;

    for (i = 0 ; i < numblacklists ; i++) {
        if (!strcmp(blacklists[i], module))
            blacklists[i] = NULL;
    }
}

void mlInitModuleConfig() {
    readModuleOpts();
    readBlacklist();
    writeModulesConf("/etc/modprobe.d/anaconda");
}

/* load a module with a given list of arguments */
int mlLoadModule(const char * module, char ** args) {
    return doLoadModule(module, args);
}

/* loads a : separated list of modules */
int mlLoadModuleSet(const char * modNames) {
    char *ptr, *name;
    int rc = 0;

    if (!modNames) return 1;
    name = strdup(modNames); while (name) {
        ptr = strchr(name, ':');
        if (ptr) *ptr = '\0';
        rc |= doLoadModule(name, NULL);
        if (ptr)
            name = ptr+1;
        else
            name = NULL;
    }
    return rc;
}

static int writeModulesConf(char *conf) {
    int i;
    char buf[16384];
    int fd, rc;

    if (!conf)
        conf = "/tmp/modprobe.conf";

    fd = open(conf, O_WRONLY | O_CREAT, 0644);
    if (fd == -1) {
        logMessage(ERROR, "error opening to %s: %m\n", conf);
        return 0;
    }
    strcat(buf, "# Module options and blacklists written by anaconda\n");
    for (i = 0; i < nummodopts ; i++) {
        int j;

        strcat(buf, "options ");
        strcat(buf, modopts[i].name);
        for (j = 0; j < modopts[i].numopts ; j++) {
            strcat(buf, " ");
            strcat(buf, modopts[i].options[j]);
        }
        strcat(buf, "\n");
    }
    for (i = 0; i < numblacklists ; i++) {
        if (blacklists[i]) {
            strcat(buf, "blacklist ");
            strcat(buf, blacklists[i]);
            strcat(buf, "\n");
        }
    }
    
    rc = write(fd, buf, strlen(buf));
    close(fd);
    return (rc != strlen(buf));
}

void loadKickstartModule(struct loaderData_s * loaderData, int argc, 
                         char ** argv) {
    char * opts = NULL;
    char * module = NULL;
    char ** args = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksDeviceOptions[] = {
        { "opts", '\0', POPT_ARG_STRING, &opts, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };
    
    optCon = poptGetContext(NULL, argc, (const char **) argv, 
                            ksDeviceOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to device kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    module = (char *) poptGetArg(optCon);

    if (!module) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("A module name must be specified for "
                         "the kickstart device command."));
        return;
    }

    if (opts) {
        int numAlloced = 5, i = 0;
        char * start;
        char * end;

        args = malloc((numAlloced + 1) * sizeof(args));
        start = opts;
        while (start && *start) {
            end = start;
            while (!isspace(*end) && *end) end++;
            *end = '\0';
            (args)[i++] = strdup(start);
            start = end + 1;
            *end = ' ';
            start = strchr(end, ' ');
            if (start) start++;

            if (i >= numAlloced) {
                numAlloced += 5;
                args = realloc(args, sizeof(args) * (numAlloced + 1));
            }
        }
        args[i] = NULL;
    }


    mlLoadModule(module, args);
}
