#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/kd.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <zlib.h>

#include <linux/keyboard.h>
#include <linux/kd.h>

#include "cpio.h"

int isysLoadFont(char * fontFile) {
    char font[8192];
    unsigned short map[E_TABSZ];
    struct unimapdesc d;
    struct unimapinit u;
    struct unipair desc[2048];
    int fd;
    gzFile stream;
    int rc;

    stream = gzopen("/etc/fonts.cgz", "r");
    if (!stream)
	return -EACCES;

    rc = installCpioFile(stream, fontFile, "/tmp/font", 1);
    gzclose(stream);
    if (rc || access("/tmp/font", R_OK))
        return -EACCES;

    fd = open("/tmp/font", O_RDONLY);
    read(fd, font, sizeof(font));
    read(fd, map, sizeof(map));
    read(fd, &d.entry_ct, sizeof(d.entry_ct));
    d.entries = desc;
    read(fd, desc, d.entry_ct * sizeof(desc[0]));
    close(fd);
    rc = ioctl(1, PIO_FONT, font);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNIMAPCLR, &u);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNIMAP, &d);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNISCRNMAP, map);
    if (rc) return rc;
    fprintf(stderr, "\033(K");
    return 0;
}

/* define ask johnsonm@redhat.com where this came from */
#define KMAP_MAGIC 0x8B39C07F
#define KMAP_NAMELEN 40         /* including '\0' */

struct kmapHeader {
    int magic;
    int numEntries;
};
        
struct kmapInfo {
    int size;
    char name[KMAP_NAMELEN];
};

/* the file pointer must be at the beginning of the section already! */
static int loadKeymap(gzFile stream) {
    int console;
    int kmap, key;
    struct kbentry entry;
    int keymaps[MAX_NR_KEYMAPS];
    int count = 0;
    int magic;
    short keymap[NR_KEYS];

    if (gzread(stream, &magic, sizeof(magic)) != sizeof(magic))
	return -EIO;

    if (magic != KMAP_MAGIC) return -EINVAL;

    if (gzread(stream, keymaps, sizeof(keymaps)) != sizeof(keymaps))
	return -EINVAL;

    console = open("/dev/console", O_RDWR);
    if (console < 0)
	return -EACCES;

    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	if (!keymaps[kmap]) continue;

	if (gzread(stream, keymap, sizeof(keymap)) != sizeof(keymap)) {
	    close(console);
	    return -EIO;
	}

	count++;
	for (key = 0; key < NR_KEYS; key++) {
	    entry.kb_index = key;
	    entry.kb_table = kmap;
	    entry.kb_value = keymap[key];
	    if (KTYP(entry.kb_value) != KT_SPEC) {
		if (ioctl(console, KDSKBENT, &entry)) {
		    int ret = errno;
		    close(console);
		    return ret;
		}
	    }
	}
    }
    close(console);
    return 0;
}

int isysLoadKeymap(char * keymap) {
    int num = -1;
    int rc;
    gzFile f;
    struct kmapHeader hdr;
    struct kmapInfo * infoTable;
    char buf[16384]; 			/* I hope this is big enough */
    int i;

    f = gzopen("/etc/keymaps.gz", "r");
    if (!f) return -EACCES;

    if (gzread(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	gzclose(f);
	return -EINVAL;
    }

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gzread(f, infoTable, i) != i) {
	gzclose(f);
	return -EIO;
    }

    for (i = 0; i < hdr.numEntries; i++)
	if (!strcmp(infoTable[i].name, keymap)) {
	    num = i;
	    break;
	}

    if (num == -1) {
	gzclose(f);
	return -ENOENT;
    }

    for (i = 0; i < num; i++) {
	if (gzread(f, buf, infoTable[i].size) != infoTable[i].size) {
	    gzclose(f);
	    return -EIO;
	}
    }

    rc = loadKeymap(f);

    gzclose(f);

    return rc;
}
