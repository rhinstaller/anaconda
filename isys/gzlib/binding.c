#include <sys/signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/wait.h>

#include "gzlib.h"

int gunzip_main(int decompress);

struct gzFile_s {
    int fd;
};

gzFile gunzip_dopen(int fd) {
    int p[2];
    void * oldsig;
    pid_t child;
    gzFile str;
    int ret;

    ret = pipe(p);

    oldsig = signal(SIGCLD, SIG_DFL);

    child = fork();
    if (!child) {
	if (fork()) exit(0);

	dup2(fd, 0);
	dup2(p[1], 1);
	close(p[0]);
	close(p[1]);
	if (fd > 2) close(fd);
	gunzip_main(1);
	exit(0);
    }

    waitpid(child, NULL, 0);
    signal(SIGCLD, oldsig);

    close(p[1]);

    str = malloc(sizeof(*str));
    str->fd = p[0];

    return str;
}

gzFile gunzip_open(const char * file) {
    int fd;
    gzFile rc;

    fd = open(file, O_RDONLY);
    if (fd == -1) return NULL;

    rc = gunzip_dopen(fd);
    close(fd);

    return rc;
}

gzFile gzip_dopen(int fd) {
    int p[2];
    void * oldsig;
    pid_t child;
    gzFile str;
    int ret;

    ret = pipe(p);

    oldsig = signal(SIGCLD, SIG_IGN);

    child = fork();
    if (!child) {
	if (fork()) exit(0);

	dup2(p[0], 0);
	dup2(fd, 1);
	close(p[0]);
	close(p[1]);
	if (fd > 2) close(fd);
	gunzip_main(0);
	exit(0);
    }

    waitpid(child, NULL, 0);
    signal(SIGCLD, oldsig);

    close(p[0]);

    str = malloc(sizeof(*str));
    str->fd = p[1];

    return str;
}


gzFile gzip_open(const char * file, int flags, int perms) {
    int fd;
    gzFile rc;

    fd = open(file, flags, perms);
    if (fd == -1) return NULL;

    rc = gzip_dopen(fd);
    close(fd);

    return rc;
}

int gunzip_read(gzFile str, void * buf, int bytes) {
    int pos = 0;
    int i = 0;

    while ((pos != bytes) &&
      (i = read(str->fd, ((char *) buf) + pos, bytes - pos)) > 0) {
	pos += i;
    }

    if (i < 0) return -1;

    return pos;
}

int gzip_write(gzFile str, void * buf, int bytes) {
    return write(str->fd, buf, bytes);
}

int gunzip_close(gzFile str) {
    close(str->fd);
    
    return 0;
}

int gzip_close(gzFile str) {
    close(str->fd);
    
    return 0;
}

