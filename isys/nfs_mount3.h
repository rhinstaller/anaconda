/*
 * We want to be able to compile mount on old kernels in such a way
 * that the binary will work well on more recent kernels.
 * Thus, if necessary we teach nfsmount.c the structure of new fields
 * that will come later.
 */
#include "nfs_mountversion.h"

#if KERNEL_NFS_MOUNT_VERSION >= 4

#define _LINUX_IN_H 1

#define NFS_MAXFHSIZE		64

#ifndef __ia64__
struct nfs_fh {
	unsigned short		size;
	unsigned char		data[NFS_MAXFHSIZE];
};
#endif

#include <linux/nfs2.h>
#include <linux/nfs_mount.h>

#ifndef NFS_VERSION
#define NFS_VERSION 2
#endif

#else /* KERNEL_NFS_MOUNT_VERSION < 3 */

#ifndef NFS_VERSION
#define NFS_VERSION 2
#endif

/*
 * We know more than the kernel. Override the kernel defines.
 * Check at runtime whether the running kernel can handle the new stuff.
 */

struct nfs_fh {
        char                    data[NFS_FHSIZE];
};

struct nfs_mount_data {
	int		version;		/* 1 */
	int		fd;			/* 1 */
	struct nfs_fh	root;			/* 1 */
	int		flags;			/* 1 */
	int		rsize;			/* 1 */
	int		wsize;			/* 1 */
	int		timeo;			/* 1 */
	int		retrans;		/* 1 */
	int		acregmin;		/* 1 */
	int		acregmax;		/* 1 */
	int		acdirmin;		/* 1 */
	int		acdirmax;		/* 1 */
	struct sockaddr_in addr;		/* 1 */
	char		hostname[256];		/* 1 */
	int		namlen;			/* 2 */
	unsigned int	bsize;			/* 3 */
};

/* bits in the flags field */

#define NFS_MOUNT_SOFT		0x0001	/* 1 */
#define NFS_MOUNT_INTR		0x0002	/* 1 */
#define NFS_MOUNT_SECURE	0x0004	/* 1 */
#define NFS_MOUNT_POSIX		0x0008	/* 1 */
#define NFS_MOUNT_NOCTO		0x0010	/* 1 */
#define NFS_MOUNT_NOAC		0x0020	/* 1 */
#define NFS_MOUNT_TCP		0x0040	/* 2 */
#define NFS_MOUNT_VER3		0x0080	/* 3 */
#define NFS_MOUNT_KERBEROS	0x0100	/* 3 */
#define NFS_MOUNT_NONLM		0x0200	/* 3 */

#endif
