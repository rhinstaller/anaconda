/*
 * init.c
 * 
 * This is the install type init 
 *
 * Erik Troan (ewt@redhat.com)
 *
 * Copyright 1996 Red Hat Software 
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
#else
#include <ctype.h>
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
#include <sys/time.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/reboot.h>
#include <termios.h>


#define syslog klogctl
#endif

#define KICK_FLOPPY     1
#define KICK_BOOTP	2

#define MS_REMOUNT      32

#define ENV_PATH 		0
#define ENV_LD_LIBRARY_PATH 	1
#define ENV_HOME		2
#define ENV_TERM		3
#define ENV_DEBUG		4

char * env[] = {
    "PATH=/usr/bin:/bin:/sbin:/usr/sbin:/mnt/sysimage/usr/bin:"
        "/mnt/sysimage/usr/bin:/mnt/sysimage/usr/sbin:/mnt/sysimage/sbin",
    "LD_LIBRARY_PATH=/lib:/usr/lib:/usr/X11R6/lib:/mnt/usr/lib:"
        "/mnt/sysimage/lib:/mnt/sysimage/usr/lib",
    "HOME=/",
    "TERM=linux",
    "DEBUG=",
    "TERMINFO=/etc/linux-terminfo",
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

int testing;

void printstr(char * string) {
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
    while (1) ;
}

int doMke2fs(char * device, char * size) {
    char * args[] = { "/usr/bin/mke2fs", NULL, NULL, NULL };
    int pid, status;

    args[1] = device;
    args[2] = size;

    if (!(pid = fork())) {
	/* child */
	execve("/usr/bin/mke2fs", args, env);
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

#if defined(__alpha__)
char * findKernel(void) {
    char * dev, * file;
    struct stat sb;

    dev = getenv("bootdevice");
    file = getenv("bootfile");

    if (!dev || !file) {
	printf("I can't find your kernel. When you are booting"
		" from a CDROM, you must pass\n");
	printf("the bootfile argument to the kernel if your"
		" boot loader doesn't do so automatically.\n");
	printf("\n");
	printf("You should now reboot your system and try "	
		"again\n");

	while (1) ;
    }

    if (!strcmp(dev, "fd0")) {
	if (!strcmp(file, "vmlinux.gz")) {
	    printf("The kernel on a boot floppy must be named vmlinux.gz. "
	           "You\n");
	    printf("are using a kernel named %s instead. You'll have "
		   "to\n", file);
	    printf("fix this and try again.\n");

	    while (1) ;
	}

	return NULL;
    } else {
	if (stat(file, &sb)) {
	    printf("I can't find your kernel. When you are booting"
		    " from a CDROM, you must pass\n");
	    printf("the bootfile argument to the kernel if your"
		    " boot loader doesn't do so automatically.\n");
	    printf("\n");
	    printf("You should now reboot your system and try "	
		    "again\n");

	    while (1) ;
	}

	return file;
    }
}
#endif 

int setupTerminal(int fd) {
    struct winsize winsize;

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

    env[ENV_TERM] = "TERM=vt100";

    return 0;
}

void unmountFilesystems(void) {
    int fd, size;
    char buf[65535];			/* this should be big enough */
    char * chptr, * start;
    struct {
	char * name;
	int len;
    } filesystems[500], tmp;
    int numFilesystems = 0;
    int i, j;

    fd = open("/proc/mounts", O_RDONLY, 0);
    if (fd < 1) {
	/* FIXME: was perror */
	printstr("failed to open /proc/mounts");
	sleep(2);
	return;
    }

    size = read(fd, buf, sizeof(buf) - 1);
    buf[size] = '\0';

    close(fd);

    chptr = buf;
    while (*chptr) {
	while (*chptr != ' ') chptr++;
	chptr++;
	start = chptr;
	while (*chptr != ' ') chptr++;
	*chptr++ = '\0';
	filesystems[numFilesystems].name = start;
	filesystems[numFilesystems].len = strlen(start);
	numFilesystems++;
	while (*chptr != '\n') chptr++;
	chptr++;
    }

    /* look ma, a *bubble* sort */
    for (i = 0; i < (numFilesystems - 1); i++) {
	for (j = i; j < numFilesystems; j++) {
	    if (filesystems[i].len < filesystems[j].len) {
		tmp = filesystems[i];
		filesystems[i] = filesystems[j];
		filesystems[j] = tmp;
	    }
	}
    }

    /* -1 because the last one will always be '/' */
    for (i = 0; i < numFilesystems - 1; i++) {
	printf("\t%s", filesystems[i].name);
	/* don't need to unmount /tmp.  it is busy anyway. */
	if (!testing && strncmp(filesystems[i].name, "/tmp", 4)) {
	    if (umount(filesystems[i].name) < 0) {
		/* FIXME printf(" failed: %s", strerror(errno));*/
		printstr(" umount failed");
	    }
	}
	printf("\n");
    }
}

int main(void) {
    pid_t installpid, childpid;
    int waitStatus;
    int fd;
    int nfsRoot = 0;
    int roRoot = 0;
    int cdRoot = 0;
    int doReboot = 0;
    int doShutdown =0;
    int isSerial = 0;
#ifdef __alpha__
    char * kernel;
#endif
    char * argv[15];
    char ** argvp = argv;

    /* getpid() != 1 should work, by linuxrc tends to get a larger pid */
    testing = (getpid() > 50);

    if (!testing) {
	/* turn off screen blanking */
	printstr("\033[9;0]");
	printstr("\033[8]");
    }

    printstr("Greetings.\n");

    printf("Red Hat install init version %s starting\n", VERSION);

    printf("mounting /proc filesystem... "); 
    if (!testing) {
	if (mount("/proc", "/proc", "proc", 0, NULL))
	    fatal_error(1);
    }
    printf("done\n");

#ifndef __alpha__
    printf("mounting /dev/pts (unix98 pty) filesystem... "); 
    if (!testing) {
	if (mount("/dev/pts", "/dev/pts", "devpts", 0, NULL))
	    fatal_error(1);
    }
    printf("done\n");
#endif

    if (!isSerial) {
	char twelve = 12;
	if (ioctl (0, TIOCLINUX, &twelve) < 0)
	    isSerial = 1;
    }
    
    if (isSerial) {
	printf("Red Hat install init version %s using a serial console\n", 
		VERSION);

	printf("remember, cereal is an important part of a nutritionally "
	       "balanced breakfast.\n\n");

	fd = open("/dev/console", O_RDWR, 0);
	if (fd < 0) {
	    printf("failed to open /dev/console");
	    fatal_error(1);
	}

	setupTerminal(fd);

	close(fd);
    } else {
	fd = open("/dev/tty1", O_RDWR, 0);
	if (fd < 0) {
	    printf("failed to open /dev/tty1");
	    fatal_error(1);
	}
    }

    dup2(fd, 0);
    dup2(fd, 1);
    dup2(fd, 2);
    close(fd);

    setsid();
    if (ioctl(0, TIOCSCTTY, NULL)) {
	printf("could not set new controlling tty");
    }

    if (!testing) {
	sethostname("localhost.localdomain", 21);
	/* the default domainname (as of 2.0.35) is "(none)", which confuses 
	   glibc */
	setdomainname("", 0);
    }

    printf("checking for NFS root filesystem...");
    if (hasNetConfiged()) {
	printf("yes\n");
	roRoot = nfsRoot = 1;
    } else {
	printf("no\n");
    }

    if (!nfsRoot) {
	printf("trying to remount root filesystem read write... ");
	if (mount("/", "/", NULL, MS_REMOUNT | MS_MGC_VAL, NULL)) {
	    printf("failed (but that's okay)\n");
	
	    roRoot = 1;
	} else {
	    printf("done\n");

	    /* 2.0.18 (at least) lets us remount a CD r/w!! */
	    printf("checking for writeable /tmp... ");
	    fd = open("/tmp/tmp", O_WRONLY | O_CREAT, 0644);
	    if (fd < 0) {
		printf("no (probably a CD rooted install)\n");
		roRoot = 1;
	    } else {
		close(fd);
		unlink("/tmp/tmp");
		printf("yes\n");
	    }
	}
    }

    if (!testing && roRoot) {
	printf("creating 300k of ramdisk space... ");
	if (doMke2fs("/dev/ram", "300"))
	    fatal_error(0);

	printf("done\n");
	
	printf("mounting /tmp from ramdisk... ");
	if (mount("/dev/ram", "/tmp", "ext2", 0, NULL))
	    fatal_error(1);

	printf("done\n");

	if (!nfsRoot) cdRoot = 1;
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

	printf("running %s\n", argv[0]);
	execve(argv[0], argv, env);
	
	exit(0);
    }

    while (!doShutdown) {
	childpid = wait4(-1, &waitStatus, 0, NULL);

	if (childpid == installpid) 
	    doShutdown = 1;
    }

    if (!WIFEXITED(waitStatus) || WEXITSTATUS(waitStatus)) {
	printf("install exited abnormally ");
	if (WIFSIGNALED(waitStatus)) {
	    printf("-- recieved signal %d", WTERMSIG(waitStatus));
	}
	printf("\n");
    } else {
	doReboot = 1;
    }

    if (testing)
        exit(0);

    sync(); sync();

    if (!testing) {
	printf("sending termination signals...");
	kill(-1, 15);
	sleep(2);
	printf("done\n");

	printf("sending kill signals...");
	kill(-1, 9);
	sleep(2);
	printf("done\n");
    }

    printf("unmounting filesystems...\n"); 
    unmountFilesystems();

    if (doReboot) {
	printf("rebooting system\n");
	sleep(2);

	#if USE_MINILIBC
	    reboot(0xfee1dead, 672274793, 0x1234567);
	#else
	    reboot(RB_AUTOBOOT);
	#endif
    } else {
	printf("you may safely reboot your system\n");
	while (1);
    }

    exit(0);

    return 0;
}
