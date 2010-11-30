/*
 * Generate initrd.addrsize file for zSeries platforms.
 * Takes an integer argument and writes out the binary representation of
 * that value to the initrd.addrsize file.
 * https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=197773
 */

#include <stdio.h>
#include <stdlib.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

int main(int argc,char **argv) {
    char *prog = basename(argv[0]);
    struct stat initrd_sbuf;
    unsigned int zero = 0;
    unsigned int addr, size;
    int fd, rc;
    char *tmp;
    mode_t mode = S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH;

    if (argc != 4) {
        printf("Usage: %s [address] [initrd file] [output file]\n", prog);
        printf("Example: %s 0x2000000 initrd.img initrd.addrsize\n", prog);
        return 0;
    }

    rc = stat(argv[2], &initrd_sbuf);
    if (rc) {
        perror("Error getting initrd stats ");
        return rc;
    }

    addr = htonl(strtoul(argv[1], &tmp, 0));
    size = htonl(initrd_sbuf.st_size);
    fd = open(argv[3], O_CREAT | O_RDWR, mode);

    if (write(fd, &zero, sizeof(int)) == -1) {
        perror("writing first zero");
        return errno;
    }

    if (write(fd, &addr, sizeof(int)) == -1) {
        perror("writing addr");
        return errno;
    }

    if (write(fd, &zero, sizeof(int)) == -1) {
        perror("writing second zero");
        return errno;
    }

    if (write(fd, &size, sizeof(int)) == -1) {
        perror("writing size");
        return errno;
    }

    close(fd);
    return 0;
}
