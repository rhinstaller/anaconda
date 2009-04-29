/*
 * init.c
 * 
 * This is the install type init 
 *
 * Erik Troan (ewt@redhat.com)
 * Jeremy Katz (katzj@redhat.com)
 *
 * Copyright 1996 - 2004 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#if USE_MINILIBC
#include "minilibc.h"
#ifndef SOCK_STREAM
# define SOCK_STREAM 1
#endif 
#else
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
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

#include "devt.h"
#include "devices.h"

#define syslog klogctl
#endif

#include <asm/types.h>
#include <linux/cdrom.h>
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

/*
 * Snakes On A Plane...
 *
 * Define this macro if you want init to launch /bin/bash instead of loader.
 * You will want to populate initrd.img with bash, libraries, other commands
 * like strace or something, and whatever else you want.  This is purely for
 * debugging loader.  Things you will likely want in a debugging initrd:
 *    /lib/libc.so.6
 *    /lib/libtermcap.so.2
 *    /lib/ld-linux.so.2
 *    /lib/libdl.so.2
 *    /bin/bash
 *    /bin/strace
 * You get the idea.  Be creative.  Be imaginative.  Be bold.
 */
#undef SNAKES_ON_A_PLANE
/* #define SNAKES_ON_A_PLANE 1 */

char * env[] = {
    "PATH=/usr/bin:/bin:/sbin:/usr/sbin:/mnt/sysimage/bin:"
    "/mnt/sysimage/usr/bin:/mnt/sysimage/usr/sbin:/mnt/sysimage/sbin:"
    "/mnt/sysimage/usr/X11R6/bin",

    /* we set a nicer ld library path specifically for bash -- a full
       one makes anaconda unhappy */
#if defined(__x86_64__) || defined(__s390x__) || defined(__ppc64__)
    "LD_LIBRARY_PATH=/lib64:/usr/lib64:/lib:/usr/lib",
#else
    "LD_LIBRARY_PATH=/lib:/usr/lib",
#endif
    "HOME=/",
    "TERM=linux",
    "DEBUG=",
    "TERMINFO=/etc/linux-terminfo",
    "PYTHONPATH=/tmp/updates",
    "_MALLOC_CHECK=2",
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

int testing=0;
void unmountFilesystems(void);
void disableSwap(void);
void shutDown(int noKill, int doReboot, int doPowerOff);
static int getNoKill(void);
struct termios ts;

static int mystrstr(char *str1, char *str2) {
    char *p;
    int rc=0;

    for (p=str1; *p; p++) {
        if (*p == *str2) {
            char *s, *t;

            rc = 1;
            for (s=p, t=str2; *s && *t; s++, t++)
                if (*s != *t) {
                    rc = 0;
                    p++;
                }

            if (rc)
                return rc;
        } 
    }
    return rc;
}

static void printstr(char * string) {
    int ret;
    ret = write(1, string, strlen(string));
}

static void fatal_error(int usePerror) {
/* FIXME */
#if 0
    if (usePerror) 
        perror("failed:");
    else
#endif
    printf("failed.\n");

    printf("\nI can't recover from this.\n");
    if (testing)
        exit(0);
#if !defined(__s390__) && !defined(__s390x__)
    while (1) ;
#endif
}

static int logChunk(int len, char *inbuf, char *outbuf) {
    int inctr, outctr;

    for (inctr = 0, outctr = 0; inctr < len; inctr++) {
        /* If the character is a NULL that's immediately followed by a open
         * bracket, we've found the beginning of a new kernel message.  Put in
         * a line separator.
         */
        if (inbuf[inctr] == '\0' && inctr+1 < len && inbuf[inctr+1] == '<') {
            outbuf[outctr] = '\n';
            outctr++;
        }

        /* Or, if we see a NULL right before the end of the chunk, that's also
         * a good place to add a separator.
         */
        else if (inbuf[inctr] == '\0' && inctr+1 == len) {
            outbuf[outctr] = '\n';
            outctr++;
        }

        /* Otherwise, simply output the character as long as it's not NULL. */
        else if (inbuf[inctr] != '\0') {
            outbuf[outctr] = inbuf[inctr];
            outctr++;
        }
    }

    return outctr;
}

static void doklog(char * fn) {
    fd_set readset, unixs;
    int in, out, i;
    int log;
    socklen_t s;
    int sock = -1;
    struct sockaddr_un sockaddr;
    char inbuf[1024], outbuf[1024];
    int readfd;
    int ret;

    in = open("/proc/kmsg", O_RDONLY,0);
    if (in < 0) {
        /* FIXME: was perror */
        printstr("open /proc/kmsg");
        return;
    }

    out = open(fn, O_WRONLY, 0);
    if (out < 0) 
        printf("couldn't open %s for syslog -- still using /tmp/syslog\n", fn);

    log = open("/tmp/syslog", O_WRONLY | O_CREAT, 0644);
    if (log < 0) {
        /* FIXME: was perror */
        printstr("error opening /tmp/syslog");
        sleep(5);
	
        close(in);
        return;
    }

    /* if we get this far, we should be in good shape */

    if (fork()) {
        /* parent */
        close(in);
        close(out);
        close(log);
        return;
    }
    close(0); 
    close(1);
    close(2);

    dup2(1, log);

#if defined(USE_LOGDEV)
    /* now open the syslog socket */
    sockaddr.sun_family = AF_UNIX;
    strcpy(sockaddr.sun_path, "/dev/log");
    sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) {
        printf("error creating socket: %d\n", errno);
        sleep(5);
    }
    printstr("got socket\n");
    if (bind(sock, (struct sockaddr *) &sockaddr, sizeof(sockaddr.sun_family) + 
			strlen(sockaddr.sun_path))) {
        printf("bind error: %d\n", errno);
        sleep(5);
    }
    printstr("bound socket\n");
    chmod("/dev/log", 0666);
    if (listen(sock, 5)) {
        printf("listen error: %d\n", errno);
        sleep(5);
    }
#endif

    syslog(8, NULL, 1);

    FD_ZERO(&unixs);
    while (1) {
        memcpy(&readset, &unixs, sizeof(unixs));

        if (sock >= 0)
            FD_SET(sock, &readset);

        FD_SET(in, &readset);

        i = select(20, &readset, NULL, NULL, NULL);
        if (i <= 0) continue;

        if (FD_ISSET(in, &readset)) {
            i = read(in, inbuf, sizeof(inbuf));
            if (i > 0) {
                int loggedLen = logChunk(i, inbuf, outbuf);

                if (out >= 0)
                    ret = write(out, outbuf, loggedLen);
                ret = write(log, outbuf, loggedLen);
            }
        } 

        for (readfd = 0; readfd < 20; ++readfd) {
            if (FD_ISSET(readfd, &readset) && FD_ISSET(readfd, &unixs)) {
                i = read(readfd, inbuf, sizeof(inbuf));
                if (i > 0) {
                    int loggedLen = logChunk(i, inbuf, outbuf);

                    if (out >= 0)
                        ret = write(out, outbuf, loggedLen);

                    ret = write(log, outbuf, loggedLen);
                } else if (i == 0) {
                    /* socket closed */
                    close(readfd);
                    FD_CLR(readfd, &unixs);
                }
            }
        }

        if (sock >= 0 && FD_ISSET(sock, &readset)) {
            s = sizeof(sockaddr);
            readfd = accept(sock, (struct sockaddr *) &sockaddr, &s);
            if (readfd < 0) {
                if (out >= 0)
                    ret = write(out, "error in accept\n", 16);
                ret = write(log, "error in accept\n", 16);
                close(sock);
                sock = -1;
            } else {
                FD_SET(readfd, &unixs);
            }
        }
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
            if (len > 0 && mystrstr(buf, "utf8"))
                env[ENV_TERM] = "TERM=vt100";
        }
    }

    return 0;
}

#if !defined(__s390__) && !defined(__s390x__)
static int termcmp(struct termios *a, struct termios *b) {
    if (a->c_iflag != b->c_iflag || a->c_oflag != b->c_oflag ||
        a->c_cflag != b->c_cflag || a->c_lflag != b->c_lflag ||
        a->c_ispeed != b->c_ispeed || a->c_ospeed != b->c_ospeed)
        return 1;
    return memcmp(a->c_cc, b->c_cc, sizeof(a->c_cc));
}
#endif

/* Recursive -- copied (and tweaked)from loader2/method.c */ 
static int copyDirectory(char * from, char * to) {
    DIR * dir;
    struct dirent * ent;
    int fd, outfd;
    char buf[4096];
    int i;
    struct stat sb;
    char filespec[256];
    char filespec2[256];
    char link[1024];
    int ret;

    mkdir(to, 0755);

    if (!(dir = opendir(from))) {
        printf("Failed to read directory %s: %s", from, strerror(errno));
        return 1;
    }

    errno = 0;
    while ((ent = readdir(dir))) {
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..")) continue;

        sprintf(filespec, "%s/%s", from, ent->d_name);
        sprintf(filespec2, "%s/%s", to, ent->d_name);

        lstat(filespec, &sb);

        if (S_ISDIR(sb.st_mode)) {
            if (copyDirectory(filespec, filespec2)) return 1;
        } else if (S_ISLNK(sb.st_mode)) {
            i = readlink(filespec, link, sizeof(link) - 1);
            link[i] = '\0';
            if (symlink(link, filespec2)) {
                printf("failed to symlink %s to %s: %s", filespec2, 
                       link, strerror(errno));
            }
        } else {
            fd = open(filespec, O_RDONLY);
            if (fd == -1) {
                printf("failed to open %s: %s", filespec, strerror(errno));
                return 1;
            } 
            outfd = open(filespec2, O_RDWR | O_TRUNC | O_CREAT, 0644);
            if (outfd == -1) {
                printf("failed to create %s: %s", filespec2, strerror(errno));
            } else {
                fchmod(outfd, sb.st_mode & 07777);

                while ((i = read(fd, buf, sizeof(buf))) > 0)
                    ret = write(outfd, buf, i);
                close(outfd);
            }

            close(fd);
        }

        errno = 0;
    }

    closedir(dir);

    return 0;
}

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
                fprintf(stderr, "Unable to create directory %s: %s\n", 
                        devname, strerror(errno));
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
            fprintf(stderr, "Unable to create device %s: %s\n", devname, 
                    strerror(errno));
    }

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
    shutDown(getNoKill(), 1, 0);
}

/* halt handler */
static void sigUsr1Handler(int signum) {
    termReset();
    shutDown(getNoKill(), 0, 0);
}

/* poweroff handler */
static void sigUsr2Handler(int signum) {
    termReset();
    shutDown(getNoKill(), 0, 1);
}

static int getNoKill(void) {
    int fd;
    int len;
    char buf[1024];

    /* look through /proc/cmdline for special options */
    if ((fd = open("/proc/cmdline", O_RDONLY,0)) > 0) {
        len = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (len > 0 && mystrstr(buf, "nokill"))
            return 1;
    }
    return 0;
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

int main(int argc, char **argv) {
    pid_t installpid, childpid;
    int waitStatus;
    int fd = -1;
    int doReboot = 0;
    int doShutdown =0;
    int isSerial = 0;
    char * console = NULL;
    int noKill = 0;
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
        exit(0);
    } else if (!strncmp(basename(argv[0]), "halt", 4)) {
        printf("Running halt...\n");
        fd = getInitPid();
        if (fd > 0)
            kill(fd, SIGUSR1);
        exit(0);
    } else if (!strncmp(basename(argv[0]), "reboot", 6)) {
        printf("Running reboot...\n");
        fd = getInitPid();
        if (fd > 0)
            kill(fd, SIGINT);
        exit(0);
    }

#if !defined(__s390__) && !defined(__s390x__)
    testing = (getppid() != 0) && (getppid() != 1);
#endif

    if (!testing) {
        /* turn off screen blanking */
        printstr("\033[9;0]");
        printstr("\033[8]");
    } else {
        printstr("(running in test mode).\n");
    }

    umask(022);

    printstr("\nGreetings.\n");

    printf("anaconda installer init version %s starting\n", VERSION);

    printf("mounting /proc filesystem... "); 
    if (!testing) {
        if (mount("/proc", "/proc", "proc", 0, NULL))
            fatal_error(1);
    }
    printf("done\n");

    printf("creating /dev filesystem... "); 
    if (!testing) {
        if (mount("/dev", "/dev", "tmpfs", 0, NULL))
            fatal_error(1);
        createDevices();
    }
    printf("done\n");

    printf("mounting /dev/pts (unix98 pty) filesystem... "); 
    if (!testing) {
        if (mount("/dev/pts", "/dev/pts", "devpts", 0, NULL))
            fatal_error(1);
    }
    printf("done\n");

    printf("mounting /sys filesystem... "); 
    if (!testing) {
        if (mount("/sys", "/sys", "sysfs", 0, NULL))
            fatal_error(1);
    }
    printf("done\n");

    /* these args are only for testing from commandline */
    for (i = 1; i < argc; i++) {
        if (!strcmp (argv[i], "serial")) {
            isSerial = 1;
            break;
        }
    }

    noKill = getNoKill();

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
    char * consoles[] = { "/dev/ttySG0", "/dev/xvc0", NULL };
#elif defined (__i386__) || defined (__x86_64__)
    char * consoles[] = { "/dev/xvc0", NULL };
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

    if (testing)
        exit(0);

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
#ifdef SNAKES_ON_A_PLANE
    disable_keys = 0;
#else
    disable_keys = 1;
    if (argc > 1)
        if (mystrstr(argv[1], "rescue"))
            disable_keys = 0;
#endif

    if (disable_keys) {
        tcgetattr(0, &ts);
        ts.c_iflag &= ~BRKINT;
        ts.c_iflag |= IGNBRK;
        ts.c_iflag &= ~ISIG;
        tcsetattr(0, TCSANOW, &ts);
    }

    if (!testing) {
        int ret;
        ret = sethostname("localhost.localdomain", 21);
        /* the default domainname (as of 2.0.35) is "(none)", which confuses 
         glibc */
        ret = setdomainname("", 0);
    }

    printf("trying to remount root filesystem read write... ");
    if (mount("/", "/", "ext2", MS_REMOUNT | MS_MGC_VAL, NULL)) {
        fatal_error(1);
    }
    printf("done\n");
        
    /* we want our /tmp to be ramfs, but we also want to let people hack
     * their initrds to add things like a ks.cfg, so this has to be a little
     * tricky */
    if (!testing) {
        rename("/tmp", "/oldtmp");
        mkdir("/tmp", 0755);

        printf("mounting /tmp as ramfs... ");
        if (mount("none", "/tmp", "ramfs", 0, NULL))
            fatal_error(1);
        printf("done\n");

        copyDirectory("/oldtmp", "/tmp");
        unlink("/oldtmp");
    }

    /* Now we have some /tmp space set up, and /etc and /dev point to
       it. We should be in pretty good shape. */

    if (!testing) 
        doklog("/dev/tty4");

    /* write out a pid file */
    if ((fd = open("/var/run/init.pid", O_WRONLY|O_CREAT, 0644)) > 0) {
        char * buf = malloc(10);
        int ret;

        snprintf(buf, 9, "%d", getpid());
        ret = write(fd, buf, strlen(buf));
        close(fd);
        free(buf);
    } else {
        printf("unable to write init.pid (%d): %s\n", errno, strerror(errno));
        sleep(2);
    }

    /* Go into normal init mode - keep going, and then do a orderly shutdown
       when:

       1) /bin/install exits
       2) we receive a SIGHUP 
    */

    printf("running install...\n"); 

    setsid();

#ifdef SNAKES_ON_A_PLANE
    printf("> Snakes on a Plane <\n");

    /* hack to load core modules for debugging mode */
    char * modvc[15];
    char ** modvp = modvc;
    *modvp++ = "/bin/modprobe";
    *modvp++ = "ehci-hcd";
    *modvp++ = "uhci-hcd";
    *modvp++ = "ohci-hcd";
    *modvp++ = NULL;
    pid_t blah = fork();
    int qux;
    if (blah == 0) {
        printf("loading core debugging modules...\n");
        execve(modvc[0], modvc, env);
    } else {
        waitpid(blah, &qux, WNOHANG);
    }
#endif

    if (!(installpid = fork())) {
        /* child */
#ifdef SNAKES_ON_A_PLANE
        *argvp++ = "/bin/strace";
#endif
        *argvp++ = "/sbin/loader";

        if (isSerial == 3) {
            *argvp++ = "--virtpconsole";
            *argvp++ = console;
        }

        *argvp++ = NULL;

        printf("running %s\n", argvc[0]);
        execve(argvc[0], argvc, env);

        shutDown(1, 0, 0);
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
        childpid = waitpid(-1, &waitStatus, 0);

        if (childpid == installpid) 
            doShutdown = 1;
    }

    if (!WIFEXITED(waitStatus) ||
        (WIFEXITED(waitStatus) && WEXITSTATUS(waitStatus))) {
        printf("install exited abnormally [%d/%d] ", WIFEXITED(waitStatus),
                                                     WEXITSTATUS(waitStatus));
        if (WIFSIGNALED(waitStatus)) {
            printf("-- received signal %d", WTERMSIG(waitStatus));
        }
        printf("\n");
    } else {
        doReboot = 1;
    }

    if (testing)
        exit(0);

    shutDown(noKill, doReboot, 0);

    return 0;
}

/* vim:set shiftwidth=4 softtabstop=4 ts=4: */
