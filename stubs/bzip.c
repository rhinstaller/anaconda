/* empty bzip stubs */

# define strong_alias(name, aliasname) _strong_alias(name, aliasname)
# define _strong_alias(name, aliasname) \
  extern __typeof (name) aliasname __attribute__ ((alias (#name)));

void * bzdopen(int fd, const char *mode) {
    return (void *) 0;
}

void * bzopen(const char * fn, const char *mode) {
    return (void *) 0;
}

const char * bzerror(void * b, int * err) {
    return (void *) 0;
}

int bzwrite(void * b, void * buf, int len) {
    return -1;
}

int bzread(void * b, void * buf, int len) {
    return -1;
}

void bzclose(void * b) {
}

int bzflush(void * b) {
    return 0;
}

strong_alias(bzclose, BZ2_bzclose)
strong_alias(bzdopen, BZ2_bzdopen)
strong_alias(bzerror, BZ2_bzerror)
strong_alias(bzflush, BZ2_bzflush)
strong_alias(bzopen,  BZ2_bzopen)
strong_alias(bzread,  BZ2_bzread)
strong_alias(bzwrite, BZ2_bzwrite)

