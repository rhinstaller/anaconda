#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "../loader/lang.h"

int main(int argc, char ** argv) {
    struct kmapHeader h;
    struct kmapInfo info;
    int i;
    struct stat sb;
    char * chptr;

    h.magic = KMAP_MAGIC;
    h.numEntries = argc - 1;
    write(1, &h, sizeof(h));

    for (i = 1; i < argc; i++) {
	if (stat(argv[i], &sb)) {
	    fprintf(stderr, "stat error for %s: %s\n", argv[i], 
			strerror(errno));
	    exit(1);
	}

	memset(info.name, 0, KMAP_NAMELEN);
	strncpy(info.name, argv[i], KMAP_NAMELEN - 1);

	chptr = info.name + strlen(info.name) - 1;
	while (*chptr != '.') *chptr-- = '\0';
	*chptr = '\0';

	info.size = sb.st_size;
	write(1, &info, sizeof(info));
    }

    return 0;
}
