/*
 * init.c
 * 
 * This is the install type init 
 *
 * Erik Troan (ewt@redhat.com)
 *
 * Copyright 1996 - 2003 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
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
#include <termios.h>

#include "devt.h"

#define syslog klogctl
#endif

#include <asm/types.h>
#include <linux/cdrom.h>

#ifndef MS_REMOUNT
#define MS_REMOUNT      32
#endif

#define ENV_PATH 		0
#define ENV_LD_LIBRARY_PATH 	1
#define ENV_HOME		2
#define ENV_TERM		3
#define ENV_DEBUG		4

char * env[] = {
    "PATH=/usr/bin:/bin:/sbin:/usr/sbin:/mnt/sysimage/bin:"
    "/mnt/sysimage/usr/bin:/mnt/sysimage/usr/sbin:/mnt/sysimage/sbin:"
    "/mnt/sysimage/usr/X11R6/bin",

    /* we set a nicer ld library path specifically for bash -- a full
       one makes anaconda unhappy */
#if defined(__x86_64__) || defined(__s390x__) || defined(__ppc64__)
    "LD_LIBRARY_PATH=/lib64:/usr/lib64:/usr/X11R6/lib64:/usr/kerberos/lib64:/lib:/usr/lib:/usr/X11R6/lib:/usr/kerberos/lib",
#else
    "LD_LIBRARY_PATH=/lib:/usr/lib:/usr/X11R6/lib:/usr/kerberos/lib",
#endif
    "HOME=/",
    "TERM=linux",
    "DEBUG=",
    "TERMINFO=/etc/linux-terminfo",
    "PYTHONPATH=/tmp/updates",
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
void shutDown(int noKill, int doReboot);
struct termios ts;

int mystrstr(char *str1, char *str2) {
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
    write(1, string, strlen(string));
}

void fatal_error(int usePerror) {
/* FIXME */
#if 0
    if (usePerror) 
	perror("failed:");
    else
#endif
	printf("failed.\n");

    printf("\nI can't recover from this.\n");
    if (testing) exit(0);
#if !defined(__s390__) && !defined(__s390x__)
    while (1) ;
#endif
}

int doMke2fs(char * device, char * size) {
    char * args[] = { "/usr/sbin/mke2fs", NULL, NULL, NULL };
    int pid, status;

    args[1] = device;
    args[2] = size;

    if (!(pid = fork())) {
	/* child */
	execve("/usr/sbin/mke2fs", args, env);
	fatal_error(1);
    }

    wait4(-1, &status, 0, NULL);
    
    return 0;
}

int hasNetConfiged(void) {
    int rc;
    int s;
    struct ifconf configs;
    struct ifreq devs[10];

#ifdef __i386__
    return 0;
#endif

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) {
	/* FIXME was perror*/
	printf("error creating socket: %d\n", errno);
	return 0;
    } else {
	/* this is just good enough to tell us if we have anything 
	   configured */
	configs.ifc_len = sizeof(devs);
	configs.ifc_buf = (void *) devs;

	rc = ioctl(s, SIOCGIFCONF, &configs);
	if (rc < 0) {
	    /* FIXME was perror*/
	    printstr("SIOCGIFCONF");
	    return 0;
	}
	if (configs.ifc_len == 0) {
	    return 0;
	}

	return 1;
    }

    return 0;
}

void doklog(char * fn) {
    fd_set readset, unixs;
    int in, out, i;
    int log;
    int s;
    int sock = -1;
    struct sockaddr_un sockaddr;
    char buf[1024];
    int readfd;

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

	if (sock >= 0) FD_SET(sock, &readset);
	FD_SET(in, &readset);

	i = select(20, &readset, NULL, NULL, NULL);
	if (i <= 0) continue;

	if (FD_ISSET(in, &readset)) {
	    i = read(in, buf, sizeof(buf));
	    if (i > 0) {
		if (out >= 0) write(out, buf, i);
		write(log, buf, i);
	    }
	} 

	for (readfd = 0; readfd < 20; ++readfd) {
	    if (FD_ISSET(readfd, &readset) && FD_ISSET(readfd, &unixs)) {
		i = read(readfd, buf, sizeof(buf));
		if (i > 0) {
		    if (out >= 0) {
			write(out, buf, i);
			write(out, "\n", 1);
		    }

		    write(log, buf, i);
		    write(log, "\n", 1);
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
		if (out >= 0) write(out, "error in accept\n", 16);
		write(log, "error in accept\n", 16);
		close(sock);
		sock = -1;
	    } else {
		FD_SET(readfd, &unixs);
	    }
	}
    }    
}

int setupTerminal(int fd) {
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

    /* use the no-advanced-video vt100 definition */
    env[ENV_TERM] = "TERM=vt100-nav";

    /* unless the user specifies that they want utf8 */
    if ((fdn = open("/proc/cmdline", O_RDONLY, 0)) != -1) {
	len = read(fdn, buf, sizeof(buf) - 1);
	close(fdn);
	if (len > 0 && mystrstr(buf, "utf8"))
	    env[ENV_TERM] = "TERM=vt100";
    }

    return 0;
}

void ejectCdrom(void) {
  int ejectfd;
  struct stat sb;

  stat("/tmp/cdrom", &sb);

  if ((sb.st_mode & S_IFBLK) == S_IFBLK) {
    printf("ejecting /tmp/cdrom...");
    if ((ejectfd = open("/tmp/cdrom", O_RDONLY | O_NONBLOCK, 0)) >= 0) {
      if (ioctl(ejectfd, CDROMEJECT, 0))
	printf("eject failed %d ", errno);
      close(ejectfd);
    } else {
      printf("eject failed %d ", errno);
    }
    printf("\n");
  }
}

/* Recursive -- copied (and tweaked)from loader2/method.c */ 
int copyDirectory(char * from, char * to) {
    DIR * dir;
    struct dirent * ent;
    int fd, outfd;
    char buf[4096];
    int i;
    struct stat sb;
    char filespec[256];
    char filespec2[256];
    char link[1024];

    mkdir(to, 0755);

    if (!(dir = opendir(from))) {
        printf("Failed to read directory %s: %s", from, strerror(errno));
        return 1;
    }

    errno = 0;
    while ((ent = readdir(dir))) {
        if (ent->d_name[0] == '.') continue;

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
                    write(outfd, buf, i);
                close(outfd);
            }

            close(fd);
        }

        errno = 0;
    }

    closedir(dir);

    return 0;
}

void sigintHandler(int signum)
{
    /* reset terminal */
    tcsetattr(0, TCSANOW, &ts);
    /* Shift in, default color, move down 100 lines */
    /* ^O        ^[[0m          ^[[100E */
    printf("\017\033[0m\033[100E\n");
    shutDown(0, 1);
}

int main(int argc, char **argv) {
    pid_t installpid, childpid;
    int waitStatus;
    int fd; 
    int doReboot = 0;
    int doShutdown =0;
    int isSerial = 0;
    int noKill = 0;
    char * argvc[15];
    char ** argvp = argvc;
    char twelve = 12;
    int i, disable_keys;
    char buf[500];
    int len;

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

    printstr("Greetings.\n");

    printf("Red Hat install init version %s starting\n", VERSION);

    printf("mounting /proc filesystem... "); 
    if (!testing) {
	if (mount("/proc", "/proc", "proc", 0, NULL))
	    fatal_error(1);
    }
    printf("done\n");

    printf("mounting /dev/pts (unix98 pty) filesystem... "); 
    if (!testing) {
	if (mount("/dev/pts", "/dev/pts", "devpts", 0, NULL))
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

    /* look through /proc/cmdline for special options */
    if ((fd = open("/proc/cmdline", O_RDONLY,0)) > 0) {
	len = read(fd, buf, sizeof(buf) - 1);
	close(fd);
	if (len > 0 && mystrstr(buf, "nokill"))
	    noKill = 1;
    }

#if !defined(__s390__) && !defined(__s390x__)
    if (ioctl (0, TIOCLINUX, &twelve) < 0) {
	isSerial = 2;
    }
    
    if (isSerial) {
	char *device = "/dev/ttyS0";

	printf("Red Hat install init version %s using a serial console\n", 
		VERSION);

	printf("remember, cereal is an important part of a nutritionally "
	       "balanced breakfast.\n\n");

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
    } else {
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
    close(fd);
#else
    dup2(0, 1);
    dup2(0, 2);
#endif

    /* disable Ctrl+Z, Ctrl+C, etc ... but not in rescue mode */
    disable_keys = 1;
    if (argc > 1)
        if (mystrstr(argv[1], "rescue"))
            disable_keys = 0;

    if (disable_keys) {
        tcgetattr(0, &ts);
        ts.c_iflag &= ~BRKINT;
        ts.c_iflag |= IGNBRK;
        ts.c_iflag &= ~ISIG;
        tcsetattr(0, TCSANOW, &ts);
    }

    if (!testing) {
	sethostname("localhost.localdomain", 21);
	/* the default domainname (as of 2.0.35) is "(none)", which confuses 
	   glibc */
	setdomainname("", 0);
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
	*argvp++ = NULL;

	printf("running %s\n", argvc[0]);
	execve(argvc[0], argvc, env);
	
	exit(0);
    }

    /* set up the ctrl+alt+delete handler to kill our pid, not pid 1 */
    signal(SIGINT, sigintHandler);
    if ((fd = open("/proc/sys/kernel/cad_pid", O_WRONLY)) != -1) {
	char buf[7];
	int count;
	sprintf(buf, "%d", getpid());
	count = write(fd, buf, strlen(buf));
	close(fd);
	/* if we succeeded in writing our pid, turn off the hard reboot
	   ctrl-alt-del handler */
	if (count == strlen(buf) &&
	    (fd = open("/proc/sys/kernel/ctrl-alt-del", O_WRONLY)) != -1) {
	    write(fd, "0", 1);
	    close(fd);
	}
    }
    
    while (!doShutdown) {
	childpid = wait4(-1, &waitStatus, 0, NULL);

	if (childpid == installpid) 
	    doShutdown = 1;
    }

    if (!WIFEXITED(waitStatus) || WEXITSTATUS(waitStatus)) {
	printf("install exited abnormally ");
	if (WIFSIGNALED(waitStatus)) {
	    printf("-- received signal %d", WTERMSIG(waitStatus));
	}
	printf("\n");
    } else {
	doReboot = 1;
    }

    if (testing)
        exit(0);

    shutDown(noKill, doReboot);

    return 0;
}
