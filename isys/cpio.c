#include <fcntl.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <zlib.h>

#include "cpio.h"

int installCpioFile(FD_t fd, char * cpioName, char * outName, int inWin) {
    struct cpioFileMapping map;
    int rc;
    const char * failedFile;
    FD_t cfd;

    if (outName) {
	map.archivePath = cpioName;
	map.fsPath = outName;
	map.mapFlags = CPIO_MAP_PATH;
    }

    (void) Fflush(fd);
    cfd = Fdopen(fdDup(Fileno(fd)), "r.gzdio");

    rc = cpioInstallArchive(cfd, outName ? &map : NULL, 1, NULL, NULL, 
			    &failedFile);
    Fclose(cfd);

    if (rc || access(outName, R_OK)) {
	return -1;
    }

    return 0;
}
