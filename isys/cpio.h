#ifndef H_CPIO
#define H_CPIO

#include <sys/types.h>

#include "stubs.h"

/* Note the CPIO_CHECK_ERRNO bit is set only if errno is valid. These have to
   be positive numbers or this setting the high bit stuff is a bad idea. */
#define CPIOERR_CHECK_ERRNO	0x80000000

#define CPIOERR_BAD_MAGIC	(2			)
#define CPIOERR_BAD_HEADER	(3			)
#define CPIOERR_OPEN_FAILED	(4    | CPIOERR_CHECK_ERRNO)
#define CPIOERR_CHMOD_FAILED	(5    | CPIOERR_CHECK_ERRNO)
#define CPIOERR_CHOWN_FAILED	(6    | CPIOERR_CHECK_ERRNO)
#define CPIOERR_WRITE_FAILED	(7    | CPIOERR_CHECK_ERRNO)
#define CPIOERR_UTIME_FAILED	(8    | CPIOERR_CHECK_ERRNO)
#define CPIOERR_UNLINK_FAILED	(9    | CPIOERR_CHECK_ERRNO)

#define CPIOERR_SYMLINK_FAILED	(11   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_STAT_FAILED	(12   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_MKDIR_FAILED	(13   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_MKNOD_FAILED	(14   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_MKFIFO_FAILED	(15   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_LINK_FAILED	(16   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_READLINK_FAILED	(17   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_READ_FAILED	(18   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_COPY_FAILED	(19   | CPIOERR_CHECK_ERRNO)
#define CPIOERR_INTERNAL	(20			)
#define CPIOERR_HDR_SIZE	(21			)
#define CPIOERR_UNKNOWN_FILETYPE (22			)


/* Don't think this behaves just like standard cpio. It's pretty close, but
   it has some behaviors which are more to RPM's liking. I tried to document
   them inline in cpio.c, but I may have missed some. */

#define CPIO_MAP_PATH		(1 << 0)
#define CPIO_MAP_MODE		(1 << 1)
#define CPIO_MAP_UID		(1 << 2)
#define CPIO_MAP_GID		(1 << 3)
#define CPIO_FOLLOW_SYMLINKS	(1 << 4)  /* only for building */

struct cpioFileMapping {
    char * archivePath;
    char * fsPath;
    mode_t finalMode;
    uid_t finalUid;
    gid_t finalGid;
    int mapFlags;
};

/* on cpio building, only "file" is filled in */
struct cpioCallbackInfo {
    char * file;
    long fileSize;			/* total file size */
    long fileComplete;			/* amount of file unpacked */
    long bytesProcessed;		/* bytes in archive read */
};

typedef void (*cpioCallback)(struct cpioCallbackInfo * filespec, void * data);

/* If no mappings are passed, this installs everything! If one is passed
   it should be sorted according to cpioFileMapCmp() and only files included
   in the map are installed. Files are installed relative to the current
   directory unless a mapping is given which specifies an absolute 
   directory. The mode mapping is only used for the permission bits, not
   for the file type. The owner/group mappings are ignored for the nonroot
   user. If *failedFile is non-NULL on return, it should be free()d. */
int myCpioInstallArchive(gzFile stream, struct cpioFileMapping * mappings, 
		       int numMappings, cpioCallback cb, void * cbData,
		       const char ** failedFile);
int myCpioFilterArchive(gzFile inStream, gzFile outStream, char ** pattern);

/* This is designed to be qsort/bsearch compatible */
int myCpioFileMapCmp(const void * a, const void * b);

const char *myCpioStrerror(int rc);

int installCpioFile(gzFile fd, char * cpioName, char * outName, int inWin);

#endif
