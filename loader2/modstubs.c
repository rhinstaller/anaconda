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
#include <stdlib.h>
#include <sys/utsname.h>
#include <sys/wait.h>

#include "modstubs.h"
#include "modules.h"

#include "../isys/cpio.h"
#include "../isys/stubs.h"

static int usage() {
    fprintf(stderr, "usage: insmod [-p <path>] <module>.o\n");
    return 1;
}

int ourInsmodCommand(int argc, char ** argv) {
    char * file;
    char finalName[100];
    char * chptr;
    gzFile fd;
    int rc, rmObj = 0;
    char * ballPath = NULL;
    char fullName[100];
    int version = 1;

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
        } else {
            return usage();
        }
    }

    if (!ballPath) {
        ballPath = strdup("/modules/modules.cgz");
    }

    file = argv[1];

    if (access(file, R_OK)) {
        /* it might be having a ball */
        fd = gunzip_open(ballPath);
        if (!fd) {
            free(ballPath);
            return 1;
        }
        
        chptr = strrchr(file, '/');
        if (chptr) file = chptr + 1;
        sprintf(finalName, "/tmp/%s", file);
        
        /* XXX: leak */
        sprintf(fullName, "%s/%s", getModuleLocation(version), file);
        
        if (installCpioFile(fd, fullName, finalName, 0)) {
            free(ballPath);
            return 1;
        }
        
        rmObj = 1;
        file = finalName;
    }

    free(ballPath);

    argv[0] = "insmod";
    argv[1] = file;

    rc = combined_insmod_main(argc, argv);
    
    if (rmObj) unlink(file);

    return rc;
}

int rmmod(char * modName) {
    pid_t child;
    int status;
    char * argv[] = { "/bin/rmmod", modName, NULL };
    int argc = 2;
    int rc = 0;

    if ((child = fork()) == 0) {
        exit(combined_insmod_main(argc, argv));
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
        execv("/bin/loader", argv);
        exit(1);
    }

    waitpid(child, &status, 0);

    if (WIFEXITED(status))
       rc = WEXITSTATUS(status);
    else
       rc = -1;

    return rc;
}
