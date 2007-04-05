#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <linux/fs.h>

#include "isys.h"

#if defined(__s390__) || defined(__s390x__)
#define u8 __u8
#define u16 __u16
#define u32 __u32
#define u64 __u64
#include <asm/vtoc.h>
#include <asm/dasd.h>
typedef struct vtoc_volume_label volume_label_t;
#endif

#if defined(__s390__) || defined(__s390x__)
/* s390 stuff to detect DASDs */
static int read_vlabel(dasd_information_t *dasd_info, int fd, int blksize,
                       volume_label_t *vlabel) {
    int rc;
    unsigned long vlabel_start = dasd_info->label_block * blksize;

    memset(vlabel, 0, sizeof(volume_label_t));

    if (lseek(fd, vlabel_start, SEEK_SET) < 0) {
        return 2;
    }

    rc = read(fd, vlabel, sizeof(volume_label_t));
    if (rc != sizeof(volume_label_t)) {
        return 1;
    }

    return 0;
}
#endif

int isUsableDasd(char *device) {
#if !defined(__s390__) && !defined(__s390x__)
    return 0;
#else
    char devname[16];
    char label[5], v4_hex[9];
    char l4ebcdic_hex[] = "d3d5e7f1";  /* LNX1 */
    char cms1_hex[] = "c3d4e2f1";      /* CMS1 */
    int f, ret, blksize;
    dasd_information_t dasd_info;
    volume_label_t vlabel;

    memset(&dasd_info, 0, sizeof(dasd_info));
    devname = strcpy(devname, "/dev/");
    devname = strcat(devname, device);
    devMakeInode(device, devname);

    if ((f = open(devname, O_RDONLY)) == -1)
        return 0;

    if (ioctl(f, BLKSSZGET, &blksize) != 0) {
        close(f);
        return 0;
    }

    if (ioctl(f, BIODASDINFO, &dasd_info) != 0) {
        close(f);
        return 0;
    }

    ret = read_vlabel(&dasd_info, f, blksize, &vlabel);
    close(f);

    if (ret == 2)
        return 0;
    else if (ret == 1) /* probably unformatted DASD */
        return 1;

    memset(label, 0, 5);
    memset(v4_hex, 0, 9);
    label = strncpy(label, vlabel.volkey, 4);

    ret = sprintf(v4_hex, "%02x%02x%02x%02x", label[0], label[1],
                                              label[2], label[3]);
    if (ret < 0 || ret < strlen(cms1_hex))
        return 3;
        
    if (!strncmp(v4_hex, cms1_hex, 9))
        return 0;

    if (!strncmp(v4_hex, l4ebcdic_hex, 9))
        return 2;

    return 1;
#endif
}

int isLdlDasd(char * device) {
    return (isUsableDasd(device) == 2);
}

char *getDasdPorts() {
#if !defined(__s390__) && !defined(__s390x__)
    return 0;
#else
    char * line, *ports = NULL;
    char devname[7];
    char port[10];
    FILE *fd;
    int ret, sz;

    fd = fopen("/proc/dasd/devices", "r");
    if (!fd)
        return NULL;

    if ((line = (char *)malloc(100 * sizeof(char))) == NULL)
        return NULL;

    while (fgets(line, 100, fd) != NULL) {
        if ((strstr(line, "unknown") != NULL))
            continue;

        if (strstr(line, "(FBA )") != NULL)
            ret = sscanf(line, "%[A-Za-z.0-9](FBA ) at ( %*d: %*d) is %s : %*s", port, devname);
        else
            ret = sscanf(line, "%[A-Za-z.0-9](ECKD) at ( %*d: %*d) is %s : %*s", port, devname);

        if (ret == 2) {
            if (!ports) {
                sz = strlen(port) + 1;
                if ((ports = (char *) malloc(sz)) == NULL)
                    return NULL;

                ports = strcpy(ports, port);
            } else {
                sz = strlen(ports) + strlen(port) + 2;
                if ((ports = (char *) realloc(ports, sz)) == NULL)
                    return NULL;

                ports = strcat(ports, ",");
                ports = strcat(ports, port);
            }
        }
    }

    if (fd)
        fclose(fd);

    return ports;
#endif
}

/* vim:set shiftwidth=4 softtabstop=4: */
