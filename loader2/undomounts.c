/*
 * undomounts.c
 *
 * Handles some basic unmounting stuff for init
 * Broken out so that it can be used on s390 in a shutdown binary 
 *
 * Erik Troan <ewt@redhat.com>
 * Jeremy Katz <katzj@redhat.com> 
 *
 * Copyright 1996 - 2003 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <unistd.h>
#include <ctype.h>
#include <arpa/inet.h>

#include "devt.h"
#include "../isys/nfsmount.h"
#include "../isys/dns.h"

struct unmountInfo {
    char * name;
    char * fstype;
    char * device;
    int mounted;
    int loopDevice;
    enum { FS, LOOP } what;
} ;

extern int testing;

void undoLoop(struct unmountInfo * fs, int numFs, int this);

static void printstr(char * string) {
    write(1, string, strlen(string));
}

static int xdr_dir(XDR *xdrsp, char *dirp)
{
      return (xdr_string(xdrsp, &dirp, MNTPATHLEN));
}

static int
nfs_umount_rpc_call(const char *spec, const char *opts)
{
      register CLIENT *clp;
      struct sockaddr_in saddr;
      struct timeval pertry, try;
      enum clnt_stat clnt_stat;
      int port = 0;
      int so = RPC_ANYSOCK;
      char *hostname;
      char *dirname;
      char *p;
      char *tmp;

      if (spec == NULL || (p = strchr(spec,':')) == NULL)
		return 0;
      tmp = strdup(spec);
      hostname = strtok(tmp, ":");
      dirname = strtok(NULL, ":");

      if (opts && (p = strstr(opts, "addr="))) {

	   free(hostname);
           tmp = strdup(p);
           strtok(tmp, "= ,");
           hostname = strtok(NULL, "= ,");
      }

      if (opts && (p = strstr(opts, "mountport=")) && isdigit(*(p+10)))
	   port = atoi(p+10);

      sleep(5);
      if (hostname[0] >= '0' && hostname[0] <= '9'){
	   saddr.sin_addr.s_addr = inet_addr(hostname);
      } else {
	   if (mygethostbyname(hostname, &saddr.sin_addr) < 0) 
		return 1;
      }

      saddr.sin_family = AF_INET;
      saddr.sin_port = htons(port);
      pertry.tv_sec = 3;
      pertry.tv_usec = 0;
      if (opts && (p = strstr(opts, "tcp"))) {
	   /* possibly: make sure option is not "notcp"
	      possibly: try udp if tcp fails */
	   if ((clp = clnttcp_create(&saddr, MOUNTPROG, MOUNTVERS,
				     &so, 0, 0)) == NULL) {
		clnt_pcreateerror("Cannot MOUNTPROG RPC (tcp)");
		return 1;
	   }
      } else {
           if ((clp = clntudp_create(&saddr, MOUNTPROG, MOUNTVERS,
				     pertry, &so)) == NULL) {
		clnt_pcreateerror("Cannot MOUNTPROG RPC");
		return 1;
	   }
      }
      clp->cl_auth = authunix_create_default();
      try.tv_sec = 20;
      try.tv_usec = 0;
      clnt_stat = clnt_call(clp, MOUNTPROC_UMNT,
			    (xdrproc_t) xdr_dir, dirname,
			    (xdrproc_t) xdr_void, (caddr_t) 0,
			    try);

      if (clnt_stat != RPC_SUCCESS) {
	   clnt_perror(clp, "Bad UMNT RPC");
	   return 1;
      }
      auth_destroy(clp->cl_auth);
      clnt_destroy(clp);

      return 0;
}

void undoMount(struct unmountInfo * fs, int numFs, int this) {
    int len = strlen(fs[this].name);
    int i;

    if (!fs[this].mounted) return;
    fs[this].mounted = 0;

    /* unmount everything underneath this */
    for (i = 0; i < numFs; i++) {
	if (fs[i].name && (strlen(fs[i].name) >= len) &&
	    (fs[i].name[len] == '/') && 
	    !strncmp(fs[this].name, fs[i].name, len)) {
	    if (fs[i].what == LOOP)
		undoLoop(fs, numFs, i);
	    else
		undoMount(fs, numFs, i);
	} 
    }

    printf("\t%s", fs[this].name);
    /* don't need to unmount /tmp.  it is busy anyway. */
    if (!testing) {
        if(strcmp(fs[this].fstype, "nfs") == 0){
            if(nfs_umount_rpc_call(fs[this].device, "") != 0){
                printf(" umount failed (%d)", errno);
            }else{
                printf(" done");
            }
        } else{
            if (umount2(fs[this].name, 0) < 0) 
                printf(" umount failed (%d)", errno);
            else
                printf(" done");
        }
    }
    printf("\n");
}

void undoLoop(struct unmountInfo * fs, int numFs, int this) {
    int i;
    int fd;

    if (!fs[this].mounted) return;
    fs[this].mounted = 0;

    /* find the device mount */
    for (i = 0; i < numFs; i++) {
	if (fs[i].what == FS && (fs[i].loopDevice == fs[this].loopDevice))
	    break;
    }

    if (i < numFs) {
	/* the device is mounted, unmount it (and recursively, anything
	 * underneath) */
	undoMount(fs, numFs, i);
    }

    unlink("/tmp/loop");
    mknod("/tmp/loop", 0600 | S_IFBLK, (7 << 8) | fs[this].loopDevice);
    printf("\tdisabling /dev/loop%d", fs[this].loopDevice);
    if ((fd = open("/tmp/loop", O_RDONLY, 0)) < 0) {
	printf(" failed to open device: %d", errno);
    } else {
	if (!testing && ioctl(fd, LOOP_CLR_FD, 0))
	    printf(" LOOP_CLR_FD failed: %d", errno);
	close(fd);
    }

    printf("\n");
}

void unmountFilesystems(void) {
    int fd, size;
    char buf[65535];			/* this should be big enough */
    char * chptr, * start, * device, * fst;
    struct unmountInfo filesystems[500];
    int numFilesystems = 0;
    int i;
    struct loop_info li;
    struct stat sb;

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
	device = chptr;
	while (*chptr != ' ') chptr++;
	*chptr++ = '\0';
	start = chptr;
	while (*chptr != ' ') chptr++;
	*chptr++ = '\0';
        fst = chptr;
        while (*chptr != ' ') chptr++;
        *chptr++ = '\0';

	if (strcmp(start, "/") && strcmp(start, "/tmp")) {
	    filesystems[numFilesystems].name = strdup(start);
	    filesystems[numFilesystems].what = FS;
	    filesystems[numFilesystems].mounted = 1;
            filesystems[numFilesystems].fstype = strdup(fst);
            filesystems[numFilesystems].device = strdup(device);

	    stat(start, &sb);
	    if ((sb.st_dev >> 8) == 7) {
		filesystems[numFilesystems].loopDevice = sb.st_dev & 0xf;
	    } else {
		filesystems[numFilesystems].loopDevice = -1;
	    }

	    numFilesystems++;
	}

	while (*chptr != '\n') chptr++;
	chptr++;
    }

    for (i = 0; i < 7; i++) {
	unlink("/tmp/loop");
	mknod("/tmp/loop", 0600 | S_IFBLK, (7 << 8) | i);
	if ((fd = open("/tmp/loop", O_RDONLY, 0)) >= 0) {
	    if (!ioctl(fd, LOOP_GET_STATUS, &li) && li.lo_name[0]) {
		filesystems[numFilesystems].name = strdup(li.lo_name);
		filesystems[numFilesystems].what = LOOP;
		filesystems[numFilesystems].mounted = 1;
		filesystems[numFilesystems].loopDevice = i;
		numFilesystems++;
	    }

	    close(fd);
	}
    }

    for (i = 0; i < numFilesystems; i++) {
	if (filesystems[i].what == LOOP) {
	    undoLoop(filesystems, numFilesystems, i);
	}
    }

    for (i = 0; i < numFilesystems; i++) {
	if ((filesystems[i].mounted) && (filesystems[i].name)) {
	    undoMount(filesystems, numFilesystems, i);
	}
    }

    for (i = 0; i < numFilesystems; i++) 
        free(filesystems[i].name);
}

void disableSwap(void) {
    int fd;
    char buf[4096];
    int i;
    char * start;
    char * chptr;

    if ((fd = open("/proc/swaps", O_RDONLY, 0)) < 0) return;

    i = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (i < 0) return;
    buf[i] = '\0';

    start = buf;
    while (*start) {
	while (*start != '\n' && *start) start++;
	if (!*start) return;

	start++;
	if (*start != '/') return;
	chptr = start;
	while (*chptr && *chptr != ' ') chptr++;
	if (!(*chptr)) return;
	*chptr = '\0';
	printf("\t%s", start);
	if (swapoff(start)) 
	    printf(" failed (%d)", errno);
	printf("\n");

	start = chptr + 1;
    }
}
