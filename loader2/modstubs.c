/*
 * modstubs.c - stubs around modutils commands
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1999 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdlib.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <sys/mman.h>

#include "log.h"
#include "modstubs.h"
#include "modules.h"

#include "../isys/cpio.h"
#include "../isys/stubs.h"

extern long init_module(void *, unsigned long, const char *);
extern long delete_module(const char *, unsigned int);

static int usage() {
    fprintf(stderr, "usage: insmod [-p <path>] <module>.ko\n");
    return 1;
}

static int rmmod_usage() {
    fprintf(stderr, "usage: rmmod <module>\n");
    return 1;
}

static char * extractModule(char * file, char * ballPath, int version, 
                            int *rmObj) {
    gzFile fd;
    /* Make finaleName and fullName REALLY static, otherwise they get dropped
       from the stack after the function returns and the addresses are no
       longer valid. */
    static char finalName[100], fullName[100];
    char * chptr = NULL;
    char *loc = NULL;

    if (access(file, R_OK)) {
        /* it might be having a ball */
        fd = gunzip_open(ballPath);
        if (!fd)
            return NULL;
        
        chptr = strrchr(file, '/');
        if (chptr) file = chptr + 1;
        sprintf(finalName, "/tmp/%s", file);

        loc = getModuleLocation(version);
        sprintf(fullName, "%s/%s", loc, file);
        free(loc);

        if (installCpioFile(fd, fullName, finalName, 0))
            return NULL;
        
        *rmObj = 1;
        file = finalName;
    }

    return file;
}

int ourInsmodCommand(int argc, char ** argv) {
    char * file;
    int rc, rmObj = 0;
    char * ballPath = NULL;
    int version = 1;
    int fd;
    void * modbuf = NULL;
    struct stat sb;

    if (argc < 2) {
        return usage();
    }

    while (argc > 2) {
        if (!strcmp(argv[1], "-p")) {
            ballPath = malloc(strlen(argv[2]) + 30);
            sprintf(ballPath, "%s/modules.cgz", argv[2]);
            argv += 2;
            argc -= 2;
        } else if (!strcmp(argv[1], "--modballversion")) {
            version = atoi(argv[2]);
            argv += 2;
            argc -= 2;
        } else if (!strncmp(argv[1], "-", 1)) { /* ignore all other options */
            argc -= 1;
            argv += 1;
        } else {
            break;
        }
    }

    if (!ballPath) {
        ballPath = strdup("/modules/modules.cgz");
    }

    file = extractModule(argv[1], ballPath, version, &rmObj);
    free(ballPath);

    if (file == NULL)
        return 1;

    if (stat(file, &sb) == -1) {
        logMessage(ERROR, "unable to stat file %s: %s", file, strerror(errno));
        return 1;
    }

    fd = open(file, O_RDONLY);
    if (fd < 0) {
        logMessage(ERROR, "unable to open file %s: %s", file, strerror(errno));
        return 1;
    }

    modbuf = mmap(0, sb.st_size, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, 0);
    if (modbuf == NULL) {
        logMessage(ERROR, "error reading file %s: %s", file, strerror(errno));
        return 1;
    }

    if (argc > 2) {
        /* FIXME: only allows one param */
        rc = init_module(modbuf, sb.st_size, argv[2]);
    } else {
        rc = init_module(modbuf, sb.st_size, "");
    }
    if (rc != 0)
        logMessage(WARNING, "failed to insert module (%d)", errno);
    return rc;
}

int ourRmmodCommand(int argc, char ** argv) {
    if (argc < 2) {
        return rmmod_usage();
    }

    return rmmod(argv[1]);
}

static char * modNameMunge(char * mod) {
    unsigned int i;

    for (i = 0; mod[i]; i++) {
        if (mod[i] == '-')
            mod[i] = '_';
    }
    return mod;
}

int rmmod(char * modName) {
    pid_t child;
    int status;
    int rc = 0;

    modName = modNameMunge(modName);
    if ((child = fork()) == 0) {
        rc = delete_module(modName, O_NONBLOCK|O_EXCL);
        exit(rc);
    }

    waitpid(child, &status, 0);

    if (WIFEXITED(status))
       rc = WEXITSTATUS(status);
    else
       rc = -1;

    return rc;
}

int insmod(char * modName, char * path, char ** args) {
    int argc;
    char ** argv;
    int rc = 0;
    pid_t child;
    int status;
    int count;

    argc = 0;
    for (argv = args; argv && *argv; argv++, argc++);

    argv = alloca(sizeof(*argv) * (argc + 5));
    argv[0] = "/bin/insmod";
    count = 1;
    if (path) {
        argv[1] = "-p";
        argv[2] = path;
        count += 2;
    }

    argv[count] = modName;
    count++;

    if (args)
        memcpy(argv + count, args, sizeof(*args) * argc);

    argv[argc + count] = NULL;

    argc += count;

    if ((child = fork()) == 0) {
        exit(ourInsmodCommand(argc, argv));
    }

    waitpid(child, &status, 0);

    if (WIFEXITED(status))
       rc = WEXITSTATUS(status);
    else
       rc = -1;

    return rc;
}
