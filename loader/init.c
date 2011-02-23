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

void shutDown(int doKill, reboot_action rebootAction);
static int getKillPolicy(void);
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

static int setupTerminal(int fd) {
    struct winsize winsize;
    gpointer value = NULL;

    if (ioctl(fd, TIOCGWINSZ, &winsize)) {
        printf("failed to get winsize");
        fatal_error(1);
    }

    winsize.ws_row = 24;
    winsize.ws_col = 80;

    if (ioctl(fd, TIOCSWINSZ, &winsize)) {
        printf("failed to set winsize");
        fatal_error(1);
    }

    if (!strcmp(ttyname(fd), "/dev/hvc0")) {
        /* using an HMC on a POWER system, use vt320 */
        env[ENV_TERM] = "TERM=vt320";
    } else {
        /* use the no-advanced-video vt100 definition */
        env[ENV_TERM] = "TERM=vt100-nav";

        /* unless the user specifies that they want utf8 */
        if (g_hash_table_lookup_extended(cmdline, "utf8", NULL, &value)) {
            env[ENV_TERM] = "TERM=vt100";
        }
    }

    return 0;
}
#if defined(__sparc__)
static int termcmp(struct termios *a, struct termios *b) {
    if (a->c_iflag != b->c_iflag || a->c_oflag != b->c_oflag ||
    a->c_cflag != b->c_cflag || a->c_lflag != b->c_lflag)
    return 1;
    return memcmp(a->c_cc, b->c_cc, sizeof(a->c_cc));
}
#endif

#if !defined(__s390__) && !defined(__s390x__) && !defined(__sparc__)
static int termcmp(struct termios *a, struct termios *b) {
    if (a->c_iflag != b->c_iflag || a->c_oflag != b->c_oflag ||
        a->c_cflag != b->c_cflag || a->c_lflag != b->c_lflag ||
        a->c_ispeed != b->c_ispeed || a->c_ospeed != b->c_ospeed)
        return 1;
    return memcmp(a->c_cc, b->c_cc, sizeof(a->c_cc));
}
#endif

static void termReset(void) {
    /* change to tty1 */
    ioctl(0, VT_ACTIVATE, 1);
    /* reset terminal */
    tcsetattr(0, TCSANOW, &ts);
    /* Shift in, default color, move down 100 lines */
    /* ^O        ^[[0m          ^[[100E */
    printf("\017\033[0m\033[100E\n");
}

/* reboot handler */
static void sigintHandler(int signum) {
    termReset();
    shutDown(getKillPolicy(), REBOOT);
}

/* halt handler */
static void sigUsr1Handler(int signum) {
    termReset();
    shutDown(getKillPolicy(), HALT);
}

/* poweroff handler */
static void sigUsr2Handler(int signum) {
    termReset();
    shutDown(getKillPolicy(), POWEROFF);
}

static int getKillPolicy(void) {
    gpointer value = NULL;

    if (g_hash_table_lookup_extended(cmdline, "nokill", NULL, &value)) {
        return 0;
    }

    return 1;
}

static void copyErrorFn (char *msg) {
    printf(msg);
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
    int fd = -1;
    int doShutdown =0;
    reboot_action shutdown_method = HALT;
    int isSerial = 0;
    gboolean isDevelMode = FALSE;
    char * console = NULL;
    int doKill = 1;
    char * argvc[15];
    char ** argvp = argvc;
    char twelve = 12;
    struct serial_struct si;
    int i, disable_keys;
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

    /* these args are only for testing from commandline */
    for (i = 1; i < argc; i++) {
        if (!strcmp (argv[i], "serial")) {
            isSerial = 1;
            break;
        }
    }

    /* if anaconda dies suddenly we are doomed, so at least make a coredump */
    struct rlimit corelimit = { RLIM_INFINITY,  RLIM_INFINITY};
    ret = setrlimit(RLIMIT_CORE, &corelimit);
    if (ret) {
        perror("setrlimit failed - no coredumps will be available");
    }

    doKill = getKillPolicy();

#if !defined(__s390__) && !defined(__s390x__)
    static struct termios orig_cmode;
    static int            orig_flags;
    struct termios cmode, mode;
    int cfd;
    
    cfd =  open("/dev/console", O_RDONLY);
    tcgetattr(cfd,&orig_cmode);
    orig_flags = fcntl(cfd, F_GETFL);
    close(cfd);

    cmode = orig_cmode;
    cmode.c_lflag &= (~ECHO);

    cfd = open("/dev/console", O_WRONLY);
    tcsetattr(cfd,TCSANOW,&cmode);
    close(cfd);

    /* handle weird consoles */
#if defined(__powerpc__)
    char * consoles[] = { "/dev/hvc0", /* hvc for JS20 */

                          "/dev/hvsi0", "/dev/hvsi1",
                          "/dev/hvsi2", /* hvsi for POWER5 */
                          NULL };
#elif defined (__ia64__)
    char * consoles[] = { "/dev/ttySG0", "/dev/xvc0", "/dev/hvc0", NULL };
#elif defined (__i386__) || defined (__x86_64__)
    char * consoles[] = { "/dev/xvc0", "/dev/hvc0", NULL };
#else
    char * consoles[] = { NULL };
#endif
    for (i = 0; consoles[i] != NULL; i++) {
        if ((fd = open(consoles[i], O_RDWR)) >= 0 && !tcgetattr(fd, &mode) && !termcmp(&cmode, &mode)) {
            printf("anaconda installer init version %s using %s as console\n",
                   VERSION, consoles[i]);
            isSerial = 3;
            console = strdup(consoles[i]);
            break;
        }
        close(fd);
    }

    cfd = open("/dev/console", O_WRONLY);
    tcsetattr(cfd,TCSANOW,&orig_cmode);
    close(cfd); 

    if ((fd < 0) && (ioctl (0, TIOCLINUX, &twelve) < 0)) {
        isSerial = 2;

        if (ioctl(0, TIOCGSERIAL, &si) == -1) {
            isSerial = 0;
        }
    }

    if (isSerial && (isSerial != 3)) {
        char *device = "/dev/ttyS0";

        printf("anaconda installer init version %s using a serial console\n", 
               VERSION);

        if (isSerial == 2)
            device = "/dev/console";
        fd = open(device, O_RDWR, 0);
        if (fd < 0)
            device = "/dev/tts/0";

        if (fd < 0) {
            printf("failed to open %s\n", device);
            fatal_error(1);
        }

        setupTerminal(fd);
    } else if (isSerial == 3) {
        setupTerminal(fd);
    } else if (fd < 0)  {
        fd = open("/dev/tty1", O_RDWR, 0);
        if (fd < 0)
            fd = open("/dev/vc/1", O_RDWR, 0);

        if (fd < 0) {
            printf("failed to open /dev/tty1 and /dev/vc/1");
            fatal_error(1);
        }
    }

    setsid();
    if (ioctl(0, TIOCSCTTY, NULL)) {
        printf("could not set new controlling tty\n");
    }

    dup2(fd, 0);
    dup2(fd, 1);
    dup2(fd, 2);
    if (fd > 2)
        close(fd);
#else
    dup2(0, 1);
    dup2(0, 2);
#endif

    /* disable Ctrl+Z, Ctrl+C, etc ... but not in rescue mode */
    disable_keys = 1;
    if (argc > 1)
        if (strstr(argv[1], "rescue"))
            disable_keys = 0;

    if (disable_keys) {
        tcgetattr(0, &ts);
        ts.c_iflag &= ~BRKINT;
        ts.c_iflag |= IGNBRK;
        ts.c_iflag &= ~ISIG;
        tcsetattr(0, TCSANOW, &ts);
    }


    /* Go into normal init mode - keep going, and then do a orderly shutdown
       when:

       1) /bin/install exits
       2) we receive a SIGHUP 
    */

    printf("running install...\n"); 

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

        shutDown(1, HALT);
    }

    /* signal handlers for halt/poweroff */
    signal(SIGUSR1, sigUsr1Handler);
    signal(SIGUSR2, sigUsr2Handler);

    /* set up the ctrl+alt+delete handler to kill our pid, not pid 1 */
    signal(SIGINT, sigintHandler);

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

        /* Restore terminal */
        cfd =  open("/dev/console", O_RDONLY);
        tcsetattr(cfd, TCSANOW, &orig_cmode);
        fcntl(cfd, F_SETFL, orig_flags);
        close(cfd);

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

    shutDown(doKill, shutdown_method);

    return 0;
}

/* vim:tw=78:ts=4:et:sw=4
 */
