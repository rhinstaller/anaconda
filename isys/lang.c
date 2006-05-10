#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <linux/keyboard.h>
#ifdef NR_KEYS
#undef NR_KEYS
#define NR_KEYS 128
#endif

#include "linux/kd.h"

#include "cpio.h"
#include "isys.h"
#include "lang.h"
#include "stubs.h"

int isysLoadFont(void) {
    unsigned char font[65536];
    struct console_font_op cfo;
    unsigned short map[E_TABSZ];
    struct unimapdesc d;
    struct unimapinit u;
    struct unipair desc[2048];
    gzFile stream;
    int rc;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    stream = gunzip_open("/etc/screenfont.gz");
    if (!stream)
	return -EACCES;

    gunzip_read(stream, &cfo, sizeof(cfo));
    gunzip_read(stream, font, sizeof(font));
    gunzip_read(stream, map, sizeof(map));
    gunzip_read(stream, &d.entry_ct, sizeof(d.entry_ct));
    d.entries = desc;
    gunzip_read(stream, desc, d.entry_ct * sizeof(desc[0]));
    gunzip_close(stream);

    cfo.data = font;
    cfo.op = KD_FONT_OP_SET;

    rc = ioctl(1, KDFONTOP, &cfo);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNIMAPCLR, &u);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNIMAP, &d);
    if (rc) return rc;
    rc = ioctl(1, PIO_UNISCRNMAP, map);
    if (rc) return rc;
    /* activate the font map */
    fprintf(stderr, "\033(K");
    return 0;
}

int isysSetUnicodeKeymap(void) {
    int console;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    console = open("/dev/console", O_RDWR);
    if (console < 0)
	return -EACCES;

    /* place keyboard in unicode mode */
    ioctl(console, KDSKBMODE, K_UNICODE);
    close(console);
    return 0;
}

/* the file pointer must be at the beginning of the section already! */
int loadKeymap(gzFile stream) {
    int console;
    int kmap, key;
    struct kbentry entry;
    int keymaps[MAX_NR_KEYMAPS];
    int count = 0;
    unsigned int magic;
    short keymap[NR_KEYS];
    struct stat sb;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    if (isVioConsole())
        return 0;
    if (!access("/proc/xen", R_OK)) /* xen can't load keymaps */
        return 0;

    /* assume that if we're already on a pty loading a keymap is silly */
    fstat(0, &sb);
    if (major(sb.st_rdev) == 3 || major(sb.st_rdev) == 136)
	return 0;

    if (gunzip_read(stream, &magic, sizeof(magic)) != sizeof(magic))
	return -EIO;

    if (magic != KMAP_MAGIC) return -EINVAL;

    if (gunzip_read(stream, keymaps, sizeof(keymaps)) != sizeof(keymaps))
	return -EINVAL;

    console = open("/dev/console", O_RDWR);
    if (console < 0)
	return -EACCES;

    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	if (!keymaps[kmap]) continue;

	if (gunzip_read(stream, keymap, sizeof(keymap)) != sizeof(keymap)) {
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

    f = gunzip_open("/etc/keymaps.gz");
    if (!f) return -EACCES;

    if (gunzip_read(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	gunzip_close(f);
	return -EINVAL;
    }

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gunzip_read(f, infoTable, i) != i) {
	gunzip_close(f);
	return -EIO;
    }

    for (i = 0; i < hdr.numEntries; i++)
	if (!strcmp(infoTable[i].name, keymap)) {
	    num = i;
	    break;
	}

    if (num == -1) {
	gunzip_close(f);
	return -ENOENT;
    }

    for (i = 0; i < num; i++) {
	if (gunzip_read(f, buf, infoTable[i].size) != infoTable[i].size) {
	    gunzip_close(f);
	    return -EIO;
	}
    }

    rc = loadKeymap(f);

    gunzip_close(f);

    return rc;
}
