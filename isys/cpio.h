#ifndef H_CPIO
#define H_CPIO

#include <zlib.h>
#define HAVE_ZLIB_H 1
#include <rpm/rpmio.h>

#define CPIO_MAP_PATH           (1 << 0)
#define CPIO_MAP_MODE           (1 << 1)
#define CPIO_MAP_UID            (1 << 2)
#define CPIO_MAP_GID            (1 << 3)
#define CPIO_FOLLOW_SYMLINKS    (1 << 4)  /* only for building */

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
    long fileSize;                      /* total file size */
    long fileComplete;                  /* amount of file unpacked */
    long bytesProcessed;                /* bytes in archive read */
};

typedef struct CFD {
    union {
        FD_t    _cfdu_fd;
#define cpioFd  _cfdu._cfdu_fd
        FILE *  _cfdu_fp;
#define cpioFp  _cfdu._cfdu_fp
        FD_t    _cfdu_gzfd;
#define cpioGzFd        _cfdu._cfdu_gzfd
    } _cfdu;
    int         cpioPos;
    enum cpioIoType {
        cpioIoTypeDebug,
        cpioIoTypeFd,
        cpioIoTypeFp,
        cpioIoTypeGzFd,
    } cpioIoType;
} CFD_t;

typedef void (*cpioCallback)(struct cpioCallbackInfo * filespec, void * data);

/* librpm provides these */
int cpioInstallArchive(CFD_t *cfd, struct cpioFileMapping * mappings,
                       int numMappings, cpioCallback cb, void * cbData,
                       char ** failedFile);
const char *cpioStrerror(int rc);

int installCpioFile(FD_t fd, char * cpioName, char * outName, int inWin);

#endif
