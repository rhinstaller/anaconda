/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992-1996 Takashi MANABE (manabe@papilio.tutics.tut.ac.jp)
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY TAKASHI MANABE ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE TERRENCE R. LAMBERT BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 * 
 */

#include	<stdio.h>
#include	<stdlib.h>
#include	<sys/types.h>
#include	<sys/ioctl.h>
#include	<sys/file.h>
#include	<string.h>
#include	<sys/types.h>
#include	<sys/socket.h>
#include	<errno.h>

#include	<interface.h>
#include	<fnld.h>

extern struct fontInfo fi;
extern forceLoad;

u_char	*FontLoadBdf(fp)
FILE *fp;
{
    char *fdata = NULL, line[256], *p, *w, reg[256];
    u_char ch, ch2;
    int	num, width, high, i, code, data, k, n;
    struct fontRegs *fReg;
    struct fontLoaderRegs *fldReg;

    fReg = &fSRegs[0];
    fldReg = &fldSRegs[0];
    fi.type = CodingByRegistry("ISO8859-1");
    num = width = high = 0;
    while(fgets(line, 256, fp)) {
	if (!width && !high &&
	    !strncmp("FONTBOUNDINGBOX", line,
		     strlen("FONTBOUNDINGBOX"))) {
	    p = line + sizeof("FONTBOUNDINGBOX");
	    sscanf(p, "%d %d", &width, &high);
	} else if (!strncmp("CHARSET_REGISTRY", line, 16)) {
	    p = line + sizeof("CHARSET_REGISTRY");
	    while(*p != '"') p ++;
	    w = ++p;
	    while(*p != '"') p ++;
	    *p = '\0';
	    strcpy(reg, w);
	} else if (!strncmp("CHARSET_ENCODING", line, 16)) {
	    p = line + sizeof("CHARSET_ENCODING");
	    while(*p != '"') p ++;
	    w = ++p;
	    while(*p != '"') p ++;
	    *p = '\0';
	    strcat(reg, "-");
	    strcat(reg, w);
	    fi.type = CodingByRegistry(reg);
	} else if (!num && !strncmp("CHARS ", line, 6)) {
	    p = line + sizeof("CHARS");
	    sscanf(p, "%d", &num);
	    break;
	}
    }
    fi.width = width;
    fi.high = high;
    if (fi.type & CHR_DBC) {
	fldReg = &fldDRegs[fi.type&~CHR_DFLD];
	fReg = &fDRegs[fi.type&~CHR_DFLD];
	if (fldReg->max)
	    fi.size = fldReg->addr(fldReg->max >> 8, fldReg->max & 0xFF)
		+ 16;
	else
	    fi.size = (width / 8 + ((width % 8 > 0) ? 1: 0)) * num * 16;
	width = 0;
    } else {
	fldReg = &fldSRegs[fi.type&~CHR_SFLD];
	fReg = &fSRegs[fi.type&~CHR_SFLD];
	if (fldReg->max)
	    fi.size = fldReg->max * 16;
	else
	    fi.size = num * 16;
    }
    if ((fdata = (u_char *)malloc(fi.size)) == NULL) return(NULL);
    k = 0;
    while(fgets(line, 256, fp)) {
	if (!strncmp("ENCODING", line, strlen("ENCODING"))) {
	    p = line + sizeof("ENCODING");
	    code = atoi(p);
	} else if (!strncmp("BITMAP", line, strlen("BITMAP"))) {
	    p = fdata + code * 16;
	    k ++;
#ifdef BDFCAT
	    printf("----- %X -----\n", code);
#endif
	    if (!(fi.type & CHR_DBC)) {
		for (i = 0; i < fi.high; i ++, p ++) {
		    fscanf(fp, "%2X", &data);
#ifdef BDFCAT
		    for (n = 0; n < 7; n ++)
			printf("%c", ((data << n) & 0x80) ? '#':' ');
		    printf("\n");
#else
		    *p = data;
#endif
		}
	    } else {
		ch = (code >> 8) & 0xFF;
		ch2 = code & 0xFF;
		num = fldReg->addr(ch, ch2);
		if (num > width) width = num;
		p = fdata + num;
		for (i = 0; i < fi.high; i ++, p ++) {
		    fscanf(fp, "%4X", &data);
#ifdef BDFCAT
		    for (n = 0; n < 15; n ++)
			printf("%c", ((data << n) & 0x80) ? '#':' ');
		    printf("\n");
#else
		    *p = (data >> 8) & 0xFF;
		    p ++;
		    *p = data & 0xFF;
#endif
		}
	    }
	}
    }
    return(fdata);
}

#ifdef BDFCAT
struct fontInfo fi;
forceLoad;

void main(int argc, char *argv[])
{
    FILE *fp;

    fp = fopen(argv[1], "r");
    FontLoadBdf(fp);
}
#endif
