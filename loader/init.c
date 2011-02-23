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

static char *VIRTIO_PORT = "/dev/virtio-ports/org.fedoraproject.anaconda.log.0";

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
static int getSyslog(gchar **, gchar **);
static int onQEMU(void);
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

/* sets up and launches syslog */
static void startSyslog(void) {
    int conf_fd;
    gchar *addr = NULL, *virtiolog = NULL;
    const char *forward_tcp = "*.* @@";
    const char *forward_format_tcp = "\n";
    const char *forward_virtio = "*.* ";
    const char *forward_format_virtio = ";virtio_ForwardFormat\n";

    /* update the config file with command line arguments first */
    
    if (getSyslog(&addr, &virtiolog)) {
        conf_fd = open("/etc/rsyslog.conf", O_WRONLY|O_APPEND);
        if (conf_fd < 0) {
            printf("error opening /etc/rsyslog.conf: %d\n", errno);
            printf("syslog forwarding will not be enabled\n");
            sleep(5);
        } else {
            if (addr != NULL) {
                write(conf_fd, forward_tcp, strlen(forward_tcp));
                write(conf_fd, addr, strlen(addr));
                write(conf_fd, forward_format_tcp, strlen(forward_format_tcp));
            }
            if (virtiolog != NULL) {
                write(conf_fd, forward_virtio, strlen(forward_virtio));
                write(conf_fd, virtiolog, strlen(virtiolog));
                write(conf_fd, forward_format_virtio, strlen(forward_format_virtio));
            }
            close(conf_fd);
        }
    }

    /* rsyslog is going to take care of things, so disable console logging */
    klogctl(8, NULL, 1);
    /* now we really start the daemon. */
    int status;
    status = system("/sbin/rsyslogd -c 4");
    if (status < 0 || 
        !WIFEXITED(status) || 
        WEXITSTATUS(status)  != 0) {
        printf("Unable to start syslog daemon.\n");
        fatal_error(1);
    }
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

/*
 * Detects the non-static part of rsyslog configuration.
 *
 * Remote TCP logging is enabled if syslog= is found on the kernel command
 * line.  Remote virtio-serial logging is enabled if the declared virtio port
 * exists.
 */
static int getSyslog(gchar **addr, gchar **virtiolog) {
    gpointer value = NULL;
    int ret = 0;

    if (g_hash_table_lookup_extended(cmdline, "syslog", NULL, &value)) {
        *addr = (gchar *) value;
        /* address can be either a hostname or IPv4 or IPv6, with or without port;
           thus we only allow the following characters in the address: letters and
           digits, dots, colons, slashes, dashes and square brackets */
        if (g_regex_match_simple("^[\\w.:/\\-\\[\\]]*$", *addr, 0, 0)) {
            ++ret;
        } else {
            /* malformed, disable use */
            *addr = NULL;
            printf("The syslog= command line parameter is malformed and will be\n");
            printf("ignored by the installer.\n");
            sleep(5);
        }
    }

    if (onQEMU()) {
        /* look for virtio-serial logging on a QEMU machine. */
        printf("Looking for the virtio ports... ");
        if (system("/sbin/udevadm trigger --action=add --sysname-match='vport*'") ||
            system("/sbin/udevadm settle")) {
            fprintf(stderr, "Error calling udevadm trigger to get virtio ports.\n");
            sleep(5);
        } else {
            printf("done.\n");
        }
        if (!access(VIRTIO_PORT, W_OK)) {
            /* that means we really have virtio-serial logging */
            *virtiolog = VIRTIO_PORT;
            ++ret;
        }
    }

    return ret;
}

/* 
 * Use anything you can find to determine if we are running on a QEMU virtual
 * machine.
 */
static int onQEMU(void)
{
    const gchar *lookfor = "QEMU Virtual CPU";
    gchar *contents = NULL;
    GError *fileErr = NULL;
    int ret = 0;

    if (!g_file_get_contents("/proc/cpuinfo", &contents, NULL, &fileErr)) {
        fprintf(stderr, "Unable to read /proc/cpuinfo.\n");
        sleep(5);
        return 0;
    }
    if (strstr(contents, lookfor)) {
        ret = 1;
    }
    g_free(contents);
    return ret;
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

    /* Now we have some /tmp space set up, and /etc and /dev point to
       it. We should be in pretty good shape. */
    startSyslog();

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
