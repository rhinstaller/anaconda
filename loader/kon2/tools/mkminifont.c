#include <stdio.h>
#include <errno.h>
#include <interface.h>
#include <fnld.h>

struct _fontent {
    unsigned short code;
    unsigned char bitmap[32];
} fent[65535];

void
main()
{
    unsigned short code, max=0;
    unsigned int fnt, i, num=0;
    unsigned char line[10], *font, bytes, high;
    struct fontInfo *fi;
    struct fontRegs *freg=&fDRegs[1];

    if ((font = GetShmem(1|CHR_DFLD)) == NULL) {
	perror("GetShmem");
	exit(-1);
    }
    fi = (struct fontInfo *)font;
    high = fi->high;
    bytes = sizeof(fent[0].code) + high * 2;
    font += sizeof(struct fontInfo);
    while (fgets(line, sizeof(line), stdin)) {
	code = ((line[0] << 8) & 0x7F00) | (line[1] & 0x7F);
	if (code > max) max = code;
	fnt = freg->addr(line[0] & 0x7F, line[1] & 0x7F);
	fent[num].code = code;
	memcpy(fent[num].bitmap, font + fnt, 32);
	num ++;
    }
    fwrite(&high, sizeof(high), 1, stdout);
    fwrite(&max, sizeof(max), 1, stdout);
    for (i = 0; i < num; i ++) if (fent[i].code)
	fwrite(&fent[i], bytes, 1, stdout);
}
