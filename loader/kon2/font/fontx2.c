/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992, 1993
 * kensyu@rabbit.is.s.u-tokyo.ac.jp
 * nozomi@yucca.cc.tsukuba.ac.jp
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

#define	FXLD_C
#include	<stdio.h>
#include	<stdlib.h>
#include	<sys/types.h>
#include	<sys/ioctl.h>
#include	<sys/file.h>
#include	<string.h>
#include	<sys/socket.h>

#include	<interface.h>
#include	<fnld.h>

extern struct fontInfo fi;
extern forceLoad;

struct fontx {
    char title[6];
    char name[8];
    unsigned char xsize;
    unsigned char ysize;
    unsigned char type;
    
    unsigned char ntable;
    struct tn { unsigned short top, tail; } table[1 /* = ntable */];
};

#define	FontxhTop       17
#define MSDOS           1
#define nSFontx         256

static struct fontx* LoadFontxHeader(FILE *fp){
    struct fontx head;
    struct fontx* ans;
#if !MSDOS
    fread(&head.title, 6, 1, fp);
    fread(&head.name, 8, 1, fp);
    fread(&head.xsize, 1, 1, fp);
    fread(&head.ysize, 1, 1, fp);
    fread(&head.type, 1, 1, fp);
    fread(&head.ntable, 1, 1, fp);
#else
    fread(&head, sizeof(struct fontx) - sizeof(struct tn), 1, fp);
#endif
    if(head.type & 1){
	ans = malloc(sizeof(struct fontx) + sizeof(struct tn)*(head.ntable-1));
	*ans = head;
#if !MSDOS
	for(i=1;i<head.ntable;i++)fread(ans->table + i,sizeof(struct tn),1,fp);
#else
	fread(ans->table, sizeof(struct tn), head.ntable, fp);
#endif
	fseek(fp, FontxhTop + 1 + ans->ntable * 4, SEEK_SET);
    }else{
	ans = malloc(sizeof(struct fontx));
	*ans = head;
	fseek(fp, FontxhTop, SEEK_SET);
    };
    return ans;
};

u_char	*FontLoadSFontx(fp, header)
FILE	*fp;
struct fontx *header;
{
    u_char	*fontbuff;
    
    fi.width = header->xsize;
    fi.high  = header->ysize;
    fi.size = ((header->xsize - 1)/8 + 1) * header->ysize * nSFontx;
    fontbuff = (u_char *)calloc(fi.size, nSFontx);
    fread(fontbuff, fi.size, nSFontx, fp);
    return(fontbuff);
}
static  unsigned int sjis2num(unsigned int code){
    unsigned int cl, ch;
    /* to jis */
    ch = (code >> 8) & 0xFF;
    cl = code & 0xFF;
    
    ch -= (ch > 0x9F) ? 0xC1: 0x81;
    if (cl >= 0x9F) {
	ch = (ch << 1) + 0x22;
	cl -= 0x7E;
    } else {
	ch = (ch << 1) + 0x21;
	cl -= ((cl <= 0x7E) ? 0x1F: 0x20);
    }
    /* to num */
    if (ch > 0x2A){
	return (cl - 0x41 + (ch - 0x26) * 96);
    }else{
	return (cl - 0x21 + (ch - 0x21) * 96);
    }
}

u_char	*FontLoadDFontx(fp, header)
FILE	*fp;
struct fontx *header;
{
    u_char	*fontbuff;
    unsigned	i, code, nchar;
    int char_byte;
    
    for(i = 0, nchar = 0; i < header->ntable; i++){
	nchar += header->table[i].tail - header->table[i].top + 1;
    }
    fi.width = header->xsize;
    fi.high  = header->ysize;
    char_byte = ((header->xsize - 1)/8 + 1) * header->ysize;
    fi.size = char_byte * (sjis2num(header->table[header->ntable-1].tail) + 1);
    
    fontbuff = (u_char *)malloc(fi.size);
    
    for(i = 0; i < header->ntable; i++){
	for(code = header->table[i].top; code <= header->table[i].tail; code ++){
	    if ((code & 0xFF) == 0x7F){ /* for buggy font (0x7E == 0x7F) */
		fseek(fp, char_byte, SEEK_CUR);
		continue;
	    }
	    fread(fontbuff + sjis2num(code) * char_byte, char_byte, 1, fp);
	}
    }
    return(fontbuff);
}

u_char *FontLoadFontx(FILE *fp)
{
    u_char *font;
    struct fontx *header;

    header = LoadFontxHeader(fp);
    if (header->type & 1) {
	fi.type = CodingByRegistry("JISX0208.1983-0");
	if (forceLoad || CheckLoadedFont(fi.type))
	    font = FontLoadDFontx(fp, header);
	else exit(0);
    } else {
	fi.type = CodingByRegistry("JISX0201.1976-0");
	if (CheckLoadedFont(fi.type))
	    font = FontLoadSFontx(fp, header);
	else exit(0);
    }
    free(header);
    return(font);
}

#if 0
void	main(argc, argv)
int	argc;
char	*argv[];
{
    FILE	*fp;
    u_char	*font;
    int	i, loaded=0;
    char	*p;

    for (i = 1; i < argc; i ++) {
	p = argv[i];
	if (*p == '-') {
	    ++p;
	    switch(*p) {
	    case 'n':
		forceLoad = 0;
		break;
	    }
	} else {
	    if(!(fp = fopen(argv[i], "r"))) {
		fprintf(stderr, "%s> Can not open font file.\n", argv[0]);
		exit(EOF);
	    }
	    loaded = 1;
	}
    }
    if (!loaded) fp = stdin;
    if ((font = FontLoadFontx(fp))== NULL) {
	fprintf(stderr, "%s> Can not load font file.\n", argv[0]);
	exit(EOF);
    }
    fclose(fp);
    
    exit(SetFont(argv[0], font, &fi));
}
#endif
