#include <fcntl.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/kd.h>
#include <unistd.h>

void die(char * mess) {
    perror(mess);
    exit(1);
}

int main(void) {
    char font[8192];
    unsigned short map[E_TABSZ];
    struct unipair descs[2048];
    struct unimapdesc d;
    int fd;

    if ((fd = open("/dev/tty1", O_RDONLY)) < 0)
	die("open");

    if (ioctl(fd, GIO_FONT, font))
	die("GIO_FONT"); 

    if (ioctl(fd, GIO_UNISCRNMAP, map))
	die("GIO_UNISCRNMAP");

    d.entry_ct = 2048;
    d.entries = descs;
    if (ioctl(fd, GIO_UNIMAP, &d))
    	die("GIO_UNIMAP");

    write(1, font, sizeof(font));
    write(1, map, sizeof(map));
    write(1, &d.entry_ct, sizeof(d.entry_ct));
    write(1, descs, d.entry_ct * sizeof(descs[0]));
    return 0;
}
