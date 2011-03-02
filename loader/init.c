/*
 * init.c: This is the install type init
 *
 * Copyright (C) 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004
 * Red Hat, Inc.  All rights reserved.
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
 * Author(s): Erik Troan (ewt@redhat.com)
 *            Jeremy Katz (katzj@redhat.com)
 */

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <execinfo.h>
#include <fcntl.h>
#include <net/if.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/reboot.h>
#include <linux/vt.h>
#include <termios.h>
#include <libgen.h>
#include <glib.h>

#include "init.h"
#include "copy.h"
#include "modules.h"
#include "readvars.h"

#include <asm/types.h>
#include <linux/serial.h>

/* 
 * this needs to handle the following cases:
 *
 *	1) run from a CD root filesystem
 *	2) run from a read only nfs rooted filesystem
 *      3) run from a floppy
 *	4) run from a floppy that's been loaded into a ramdisk 
 *
 */

struct termios ts;

static void printstr(char * string) {
    write(1, string, strlen(string));
}

static void fatal_error(int usePerror) {
    printf("failed.\n");

    printf("\nI can't recover from this.\n");
#if !defined(__s390__) && !defined(__s390x__)
    while (1) ;
#endif
}

static char *setupMallocPerturb(char *value)
{
    FILE *f;
    unsigned char x;
    size_t rc;
    char *ret = NULL;
    
    f = fopen("/dev/urandom", "r");
    if (!f)
        return NULL;

    rc = fread(&x, 1, 1, f);
    fclose(f);
    if (rc < 1)
        return NULL;

    rc = asprintf(&ret, "MALLOC_PERTURB_=%hhu", x);
    if (rc < 0)
        return NULL;
    return ret;
}

/* these functions return a newly allocated string that never gets freed;
 * their lifetime is essentially that of main(), and we'd have to track which
 * are allocated and which aren't, which is pretty pointless... */
typedef char *(*setupEnvCallback)(char *entry);

static void setupEnv(void)
{
    struct {
        char *name;
        setupEnvCallback cb;
    } setupEnvCallbacks[] = {
        { "MALLOC_PERTURB_", setupMallocPerturb },
        { NULL, NULL }
    };
    int x;

    /* neither array is very big, so this algorithm isn't so bad.  If env[]
     * gets bigger for some reason, we should probably just alphebatize both
     * (manually) and then only initialize y one time.
     */
    for (x = 0; setupEnvCallbacks[x].name != NULL; x++) {
        int y;
        int l = strlen(setupEnvCallbacks[x].name) + 1;
        char cmpstr[l + 1];

        strncpy(cmpstr, setupEnvCallbacks[x].name, l);
        strcat(cmpstr, "=");

        for (y = 0; env[y] != NULL; y++) {
            if (!strncmp(env[y], cmpstr, l)) {
                char *new = setupEnvCallbacks[x].cb(env[y] + l);
                if (new)
                    env[y] = new;
            }
        }
    }
}

int main(int argc, char **argv) {
    pid_t installpid;
    int waitStatus;
    int doShutdown =0;
    reboot_action shutdown_method = HALT;
    int isSerial = 0;
    gboolean isDevelMode = FALSE;
    char * console = NULL;
    int doKill = 1;
    char * argvc[15];
    char ** argvp = argvc;
    int i;
    int ret;
    gpointer value = NULL;

    /* turn off screen blanking */
    printstr("\033[9;0]");
    printstr("\033[8]");

    umask(022);

    /* set up any environment variables that aren't totally static */
    setupEnv();

    printstr("\nGreetings.\n");

    printf("anaconda installer init version %s starting\n", VERSION);

    /* if anaconda dies suddenly we are doomed, so at least make a coredump */
    struct rlimit corelimit = { RLIM_INFINITY,  RLIM_INFINITY};
    ret = setrlimit(RLIMIT_CORE, &corelimit);
    if (ret) {
        perror("setrlimit failed - no coredumps will be available");
    }


    if (!(installpid = fork())) {
        /* child */
        *argvp++ = "/sbin/loader";

        if (isSerial == 3) {
            *argvp++ = "--virtpconsole";
            *argvp++ = console;
        }

        *argvp++ = NULL;

        printf("running %s\n", argvc[0]);
        execve(argvc[0], argvc, env);
    }

    while (!doShutdown) {
        pid_t childpid;
        childpid = wait(&waitStatus);

        if (childpid == installpid) {
            doShutdown = 1;
            ioctl(0, VT_ACTIVATE, 1);
        }
    }

    if (!WIFEXITED(waitStatus) ||
        (WIFEXITED(waitStatus) && WEXITSTATUS(waitStatus))) {

        restore_console(&orig_cmode, orig_flags);

        shutdown_method = DELAYED_REBOOT;
        printf("install exited abnormally [%d/%d] ", WIFEXITED(waitStatus),
                                                     WEXITSTATUS(waitStatus));
        if (WIFSIGNALED(waitStatus)) {
            printf("-- received signal %d", WTERMSIG(waitStatus));
        }
        printf("\n");

    } else {
        shutdown_method = REBOOT;
    }

    return 0;
}

/* vim:tw=78:ts=4:et:sw=4
 */
