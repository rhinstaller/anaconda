#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#define BLOCK_SIZE 2048
 
/* returns 1 if file is an ISO, 0 otherwise */
int fileIsIso(const char * file) {
    int blkNum;
    char magic[5];
    int fd;

    fd = open(file, O_RDONLY);
    if (fd < 0)
	return 0;

    for (blkNum = 16; blkNum < 100; blkNum++) {
	if (lseek(fd, blkNum * BLOCK_SIZE + 1, SEEK_SET) < 0) {
	    close(fd);
	    return 0;
	}

	if (read(fd, magic, sizeof(magic)) != sizeof(magic)) {
	    close(fd);
	    return 0;
	}

	if (!strncmp(magic, "CD001", 5)) {
	    close(fd);
	    return 1;
	}
    }

    close(fd); 
    return 0;
}
