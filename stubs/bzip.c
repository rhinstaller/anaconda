/* empty bzip stubs */

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
