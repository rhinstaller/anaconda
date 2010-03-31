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

#if USE_MINILIBC
#include "minilibc.h"
#ifndef SOCK_STREAM
# define SOCK_STREAM 1
#endif 
#define klogctl syslog
#else
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
#include "devt.h"
#include "devices.h"

#endif

#include <asm/types.h>
#include <linux/serial.h>

#ifndef MS_REMOUNT
#define MS_REMOUNT          32
#endif

#define ENV_PATH            0
#define ENV_LD_LIBRARY_PATH 1
#define ENV_HOME            2
#define ENV_TERM            3
#define ENV_DEBUG           4
#define ENV_TERMINFO        5
#define ENV_PYTHONPATH      6
#define ENV_MALLOC_CHECK    7
#define ENV_MALLOC_PERTURB  8

char * env[] = {
    "PATH=/usr/bin:/bin:/sbin:/usr/sbin:/mnt/sysimage/bin:"
    "/mnt/sysimage/usr/bin:/mnt/sysimage/usr/sbin:/mnt/sysimage/sbin:"
    "/mnt/sysimage/usr/X11R6/bin",

    /* we set a nicer ld library path specifically for bash -- a full
       one makes anaconda unhappy */
#if defined(__x86_64__) || defined(__s390x__) || defined(__powerpc64__) || (defined(__sparc__) && defined(__arch64__))
    "LD_LIBRARY_PATH=/lib64:/usr/lib64:/lib:/usr/lib",
#else
    "LD_LIBRARY_PATH=/lib:/usr/lib",
#endif
    "HOME=/",
    "TERM=linux",
    "DEBUG=",
    "TERMINFO=/etc/linux-terminfo",
    "PYTHONPATH=/tmp/updates",
    "MALLOC_CHECK_=2",
    "MALLOC_PERTURB_=204",
    NULL
};

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
static void getSyslog(char*);
struct termios ts;

static int expected_exit = 0;

static void doExit(int) __attribute__ ((noreturn));
static void doExit(int result)
{
    expected_exit = 1;
    exit(result);
}

static void printstr(char * string) {
    int ret;
    ret = write(1, string, strlen(string));
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
    int ret;
    char addr[128];
    char forwardtcp[] = "*.* @@";
    
    /* update the config file with command line arguments first */
    getSyslog(addr);
    if (strlen(addr) > 0) {
        conf_fd = open("/etc/rsyslog.conf", O_WRONLY|O_APPEND);
        if (conf_fd < 0) {
            printf("error opening /etc/rsyslog.conf: %d\n", errno);
            printf("syslog forwarding will not be enabled\n");
            sleep(5);
        } else {
            ret = write(conf_fd, forwardtcp, strlen(forwardtcp));
            ret = write(conf_fd, addr, strlen(addr));
            ret = write(conf_fd, "\n", 1);
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
    int fdn, len;
    char buf[65535];

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
        if ((fdn = open("/proc/cmdline", O_RDONLY, 0)) != -1) {
            len = read(fdn, buf, sizeof(buf) - 1);
            close(fdn);
            if (len > 0 && strstr(buf, "utf8"))
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

static void createDevices(void) {
    int i;

    /*	unset the umask so devices are created with correct perms
	and not complemented by the previous umask call */

    mode_t previous_umask = umask(0); 

    for (i = 0; devnodes[i].devname != NULL; i++) {
        char devname[64];
        int type = -1;

        snprintf(devname, 63, "/dev/%s", devnodes[i].devname);
        switch (devnodes[i].type) {
        case DIRTYPE:
            if (mkdir(devname, devnodes[i].perms) < 0) {
                fprintf(stderr, "Unable to create directory %s: %m\n",
                        devname);
            }
            break;
        case CHARDEV:
            type = S_IFCHR;
            break;
        case BLOCKDEV:
            type = S_IFBLK;
            break;
        }
        if (type == -1) continue;

        if (mknod(devname, type | devnodes[i].perms, 
                  makedev(devnodes[i].major, devnodes[i].minor)) < 0)
            fprintf(stderr, "Unable to create device %s: %m\n", devname);
    }

    /* Hurray for hacks, this stops /lib/udev/rules.d/65-md-incremental.rules
       from medling with mdraid sets. */
    i = creat("/dev/.in_sysinit", 0644);
    close(i);

    /* Restore umask for minimal side affects */
    umask(previous_umask); 
}

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
    int fd;
    int len;
    char buf[1024];

    /* look through /proc/cmdline for special options */
    if ((fd = open("/proc/cmdline", O_RDONLY,0)) > 0) {
        len = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if ((len > 0) && strstr(buf, "nokill"))
            return 0;
    }
    return 1;
}

/* Looks through /proc/cmdline for remote syslog paramters. */
static void getSyslog(char *addr) {
    int fd;
    int len;
    char buf[1024];

    /* assume nothing gets found */
    addr[0] = '\0';
    if ((fd = open("/proc/cmdline", O_RDONLY,0)) <= 0) {
        return;
    }
    len = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    buf[len] = '\0';
    
    /* Parse the command line into argument vector using glib */
    int i;
    int argc;
    char** argv;
    GError* err = NULL;
    if (!g_shell_parse_argv(buf, &argc, &argv, &err )) {
        g_error_free(err);
        return;
    }
    for (i = 0; i < argc; ++i) {
        /* find what we are looking for */
        if (!strncmp(argv[i], "syslog=", 7)) {
            strncpy(addr, argv[i] + 7, 127);
            addr[127] = '\0';
            break;
        }
    }
    g_strfreev(argv);

    /* address can be either a hostname or IPv4 or IPv6, with or without port;
       thus we only allow the following characters in the address: letters and
       digits, dots, colons, slashes, dashes and square brackets */
    if (!g_regex_match_simple("^[\\w.:/\\-\\[\\]]*$", addr, 0, 0)) {
        /* the parameter is malformed, disable its use */
        addr[0] = '\0';
        printf("The syslog= command line parameter is malformed and will be\n");
        printf("ignored by the installer.\n");
        sleep(5);
    }

}

static int getInitPid(void) {
    int fd = 0, pid = -1, ret;
    char * buf = calloc(1, 10);

    fd = open("/var/run/init.pid", O_RDONLY);
    if (fd < 0) {
        fprintf(stderr, "Unable to find pid of init!!!\n");
        return -1;
    }
    ret = read(fd, buf, 9);
    close(fd);
    ret = sscanf(buf, "%d", &pid);
    return pid;
}

static void copyErrorFn (char *msg) {
    printf(msg);
}

void initSegvHandler(int signum) {
    void *array[30];
    size_t i;
    const char const * const errmsgs[] = {
        "init received SIG",
        "!  Backtrace:\n",
        "init exited unexpectedly!  Backtrace:\n",
    };

    /* XXX This should really be in a glibc header somewhere... */
    extern const char *const sys_sigabbrev[NSIG];

    signal(signum, SIG_DFL); /* back to default */

    if (signum == 0) {
        i = write(STDERR_FILENO, errmsgs[2], strlen(errmsgs[2]));
    } else {
        i = write(STDERR_FILENO, errmsgs[0], strlen(errmsgs[0]));
        i = write(STDERR_FILENO, sys_sigabbrev[signum],
                strlen(sys_sigabbrev[signum]));
        i = write(STDERR_FILENO, errmsgs[1], strlen(errmsgs[1]));
    }

    i = backtrace (array, 30);
    backtrace_symbols_fd(array, i, STDERR_FILENO);
    _exit(1);
}

void initExitHandler(void)
{
    if (expected_exit)
        return;

    initSegvHandler(0);
}

static void setupBacktrace(void)
{
    void *array;

    signal(SIGSEGV, initSegvHandler);
    signal(SIGABRT, initSegvHandler);
    atexit(initExitHandler);

    /* Turns out, there's an initializer at the top of backtrace() that
     * (on some arches) calls dlopen(). dlopen(), unsurprisingly, calls
     * malloc(). So, call backtrace() early in signal handler setup so
     * we can later safely call it from the signal handler itself. */
    backtrace(&array, 1);
}

int main(int argc, char **argv) {
    pid_t installpid, childpid;
    int waitStatus;
    int fd = -1;
    int doShutdown =0;
    reboot_action shutdown_method = HALT;
    int isSerial = 0;
    char * console = NULL;
    int doKill = 1;
    char * argvc[15];
    char ** argvp = argvc;
    char twelve = 12;
    struct serial_struct si;
    int i, disable_keys;

    if (!strncmp(basename(argv[0]), "poweroff", 8)) {
        printf("Running poweroff...\n");
        fd = getInitPid();
        if (fd > 0)
            kill(fd, SIGUSR2);
        doExit(0);
    } else if (!strncmp(basename(argv[0]), "halt", 4)) {
        printf("Running halt...\n");
        fd = getInitPid();
        if (fd > 0)
            kill(fd, SIGUSR1);
        doExit(0);
    } else if (!strncmp(basename(argv[0]), "reboot", 6)) {
        printf("Running reboot...\n");
        fd = getInitPid();
        if (fd > 0)
            kill(fd, SIGINT);
        doExit(0);
    }

    /* turn off screen blanking */
    printstr("\033[9;0]");
    printstr("\033[8]");

    umask(022);

    /* set up signal handler */
    setupBacktrace();

    printstr("\nGreetings.\n");

    printf("anaconda installer init version %s starting\n", VERSION);

    printf("mounting /proc filesystem... "); 
    if (mount("/proc", "/proc", "proc", 0, NULL))
        fatal_error(1);
    printf("done\n");

    printf("creating /dev filesystem... "); 
    if (mount("/dev", "/dev", "tmpfs", 0, NULL))
        fatal_error(1);
    createDevices();
    printf("done\n");
    printf("starting udev...");
    if ((childpid = fork()) == 0) {
        execl("/sbin/udevd", "/sbin/udevd", "--daemon", NULL);
        exit(1);
    }
    
    /* wait at least until the udevd process that we forked exits */
    do {
        pid_t retpid;
        int waitstatus;

        retpid = waitpid(childpid, &waitstatus, 0);
        if (retpid == -1) {
            if (errno == EINTR)
                continue;
            /* if the child exited before we called waitpid, we can get
             * ECHILD without anything really being wrong; we just lost
             * the race.*/
            if (errno == ECHILD)
                break;
            printf("init: error waiting on udevd: %m\n");
            exit(1);
        } else if (WIFEXITED(waitstatus)) {
            break;
        }
    } while (1);
    
    if (fork() == 0) {
        execl("/sbin/udevadm", "udevadm", "control", "--env=ANACONDA=1", NULL);
        exit(1);
    }
    printf("done\n");

    printf("mounting /dev/pts (unix98 pty) filesystem... "); 
    if (mount("/dev/pts", "/dev/pts", "devpts", 0, NULL))
        fatal_error(1);
    printf("done\n");

    printf("mounting /sys filesystem... "); 
    if (mount("/sys", "/sys", "sysfs", 0, NULL))
        fatal_error(1);
    printf("done\n");

    /* these args are only for testing from commandline */
    for (i = 1; i < argc; i++) {
        if (!strcmp (argv[i], "serial")) {
            isSerial = 1;
            break;
        }
    }

    doKill = getKillPolicy();

#if !defined(__s390__) && !defined(__s390x__)
    static struct termios orig_cmode;
    struct termios cmode, mode;
    int cfd;
    
    cfd =  open("/dev/console", O_RDONLY);
    tcgetattr(cfd,&orig_cmode);
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

    int ret;
    ret = sethostname("localhost.localdomain", 21);
    /* the default domainname (as of 2.0.35) is "(none)", which confuses 
     glibc */
    ret = setdomainname("", 0);

    printf("trying to remount root filesystem read write... ");
    if (mount("/", "/", "ext2", MS_REMOUNT | MS_MGC_VAL, NULL)) {
        fatal_error(1);
    }
    printf("done\n");

    /* we want our /tmp to be tmpfs, but we also want to let people hack
     * their initrds to add things like a ks.cfg, so this has to be a little
     * tricky */
    rename("/tmp", "/oldtmp");
    mkdir("/tmp", 0755);

    printf("mounting /tmp as tmpfs... ");
    if (mount("none", "/tmp", "tmpfs", 0, "size=250m"))
        fatal_error(1);
    printf("done\n");

    copyDirectory("/oldtmp", "/tmp", copyErrorFn, copyErrorFn);
    unlink("/oldtmp");

    /* Now we have some /tmp space set up, and /etc and /dev point to
       it. We should be in pretty good shape. */
    startSyslog();

    /* write out a pid file */
    if ((fd = open("/var/run/init.pid", O_WRONLY|O_CREAT, 0644)) > 0) {
        char * buf = malloc(10);
        int ret;

        snprintf(buf, 9, "%d", getpid());
        ret = write(fd, buf, strlen(buf));
        close(fd);
        free(buf);
    } else {
        printf("unable to write init.pid (%d): %m\n", errno);
        sleep(2);
    }

    /* D-Bus */
    if (fork() == 0) {
        execl("/sbin/dbus-uuidgen", "/sbin/dbus-uuidgen", "--ensure", NULL);
        doExit(1);
    }

    if (fork() == 0) {
        execl("/sbin/dbus-daemon", "/sbin/dbus-daemon", "--system", NULL);
        doExit(1);
    }

    sleep(2);

    /* Go into normal init mode - keep going, and then do a orderly shutdown
       when:

       1) /bin/install exits
       2) we receive a SIGHUP 
    */

    printf("running install...\n"); 

    setsid();

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
    if ((fd = open("/proc/sys/kernel/cad_pid", O_WRONLY)) != -1) {
        char buf[7];
        size_t count;
        sprintf(buf, "%d", getpid());
        count = write(fd, buf, strlen(buf));
        close(fd);
        /* if we succeeded in writing our pid, turn off the hard reboot
           ctrl-alt-del handler */
        if (count == strlen(buf) &&
            (fd = open("/proc/sys/kernel/ctrl-alt-del", O_WRONLY)) != -1) {
            int ret;

            ret = write(fd, "0", 1);
            close(fd);
        }
    }
    
    while (!doShutdown) {
        pid_t childpid;
        childpid = waitpid(-1, &waitStatus, 0);

        if (childpid == installpid) {
            doShutdown = 1;
            ioctl(0, VT_ACTIVATE, 1);
        }
    }

    if (!WIFEXITED(waitStatus) ||
        (WIFEXITED(waitStatus) && WEXITSTATUS(waitStatus))) {
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
