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

/*
  This code is based on KanjiHand.
  
  Thanks to
  nemossan@uitec.ac.jp == nemossan@mix
  takamiti@mix
  maebashi@mcs.meitetsu.co.jp
  yamamoto@sws.cpd.mei.co.jp
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

#include	<fnld.h>
#include	<interface.h>

#define	SFONT_SIZE	256
#define FH_MEMO_SIZE		508

extern struct fontInfo fi;
extern forceLoad;

struct font_header {
    short fnt_size;		/* bytes per one character bit patern */
    short fnt_high;		/* font height */
    short fnt_width;	/* font width */
    unsigned short top_code;
    unsigned short end_code;
    char _unused[502];	/* empty */
    char memo[FH_MEMO_SIZE];
    long sum;
};

#define FONT_HEAD_SIZE		sizeof(struct font_header)
#define MINKANJI	0x2121
#define MAXKANJI	0x7424

#define get_kfontoft(k1,k2)	(((k1) > 0x29) ? \
				 ((((k2) - 0x40) + ((k1) - 0x25) * 96) << 5) : \
				 ((((k2) - 0x20) + ((k1) - 0x20) * 96) << 5))

#define get_afontoft(c)	(c << 4)

static u_char	*FontLoads(fp, fsize)
FILE	*fp;
size_t	fsize;
{
    int	addr, i;
    u_char	*fontbuf;
    
    if ((fontbuf = (u_char *)malloc(get_afontoft(SFONT_SIZE))) == NULL)
	return(NULL);
    fi.size = get_afontoft(SFONT_SIZE);
    for (i = 0; i < SFONT_SIZE; i ++) {
	addr = get_afontoft(i);
	if (fread(fontbuf + addr, fsize, 1, fp) != 1) return(NULL);
    }
    return(fontbuf);
}

static u_char	*FontLoadw(fp, fsize)
FILE	*fp;
size_t	fsize;
{
    size_t	start;
    int	addr, k1, k2, i;
    u_char	*fontbuf;
    
    fi.size = get_kfontoft((MAXKANJI+1)>>8, (MAXKANJI+1) & 0xFF);
    start = get_kfontoft((MINKANJI)>>8, (MINKANJI) & 0xFF);
    if ((fontbuf = (u_char *)malloc(fi.size)) == NULL) return(NULL);
    for (k1 = 0x21; k1 <= 0x74; k1 ++) {
	for (k2 = 0x21; k2 < 0x7f; k2 ++) {
	    if (k1 > 0x29 && k1 < 0x30) {
		for (i = 0; i < fsize; i ++) fgetc(fp);
		/*				fseek(fp, fsize, SEEK_CUR);*/
		continue;
	    }
	    addr = get_kfontoft(k1, k2);
	    if (fread(fontbuf + addr, fsize, 1, fp) != 1)
		return(NULL);
	    if(k1 == 0x74 && k2 == 0x24) break;
	}
    }
    return(fontbuf + start);
}

u_char	*FontLoadMinix(fp)
FILE *fp;
{
    char	*fdata = NULL;
    struct	font_header hd;
    
    if(fread(&hd, sizeof(struct font_header), 1, fp) != 1) return(NULL);
    if (memcmp("k14;", hd.memo, 4)) {
	if (hd.fnt_width > 0 && hd.fnt_width <= 8
	    && hd.fnt_high > 8 && hd.fnt_high <= 16
	    && hd.fnt_size == 16 ) {
	    fi.high = hd.fnt_high;
	    fi.width = hd.fnt_width;
	    fi.type = CodingByRegistry("JISX0201.1976-0");
	    if (CheckLoadedFont(fi.type))
		fdata = FontLoads(fp, hd.fnt_size);
	    else exit(0);
	}
    } else {
	if(hd.fnt_width > 8 && hd.fnt_width <= 16
	   && hd.fnt_high > 8
	   && hd.fnt_high <= 16
	   && hd.fnt_size > 16 && hd.fnt_size <= 32) {
	    fi.high = hd.fnt_high;
	    fi.width = hd.fnt_width;
	    fi.type = CodingByRegistry("JISX0208.1983-0");
	    if (CheckLoadedFont(fi.type))
		fdata = FontLoadw(fp, hd.fnt_size);
	    else exit(0);
	}
    }
    return(fdata);
}

#if 0
void	main(argc, argv)
int	argc;
char	*argv[];
{
    FILE	*fp;
    u_char	*font;
    int		loaded=0;
    int	i;
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

    if ((font = FontLoadMinix(fp)) == NULL) {
	fprintf(stderr, "%s> Can not load font file.\n", argv[0]);
	exit(EOF);
    }
    if (fp != stdin) fclose(fp);
    
    exit(SetFont(argv[0], font, &fi));
}
#endif
