#include <sys/signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>

#include "gzlib.h"

struct gzFile_s {
    int fd;
};

gzFile gunzip_open(const char * file) {
    int fd;
    int p[2];
    void * oldsig;
    pid_t child;
    gzFile str;

    fd = open(file, O_RDONLY);
    if (fd < 0) return NULL;

    pipe(p);

    oldsig = signal(SIGCLD, SIG_IGN);

    child = fork();
    if (!child) {
	if (fork()) exit(0);

	dup2(fd, 0);
	dup2(p[1], 1);
	close(p[0]);
	close(p[1]);
	gunzip_main();
	exit(0);
    }

    waitpid(child, NULL, 0);
    signal(SIGCLD, oldsig);

    close(p[1]);

    str = malloc(sizeof(*str));
    str->fd = p[0];

    return str;
}

int gunzip_read(gzFile str, void * buf, int bytes) {
    int pos = 0;
    int i;

    while ((pos != bytes) &&
      (i = read(str->fd, ((char *) buf) + pos, bytes - pos)) > 0)
	pos += i;

    if (i < 0) return -1;

    return pos;
}

int gunzip_close(gzFile str) {
    close(str->fd);
    
    return 0;
}

