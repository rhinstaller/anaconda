/*
        KON Font Loader for J-3100 (TOSHIBA), Version 0.3(1993/ 9/ 3)
        Copyright (C) 1993, Kazumasa KAWAI (kazu@jl1keo.tama.prug.or.jp)
	Copyright (C) 1992, 1993 MAEDA Atusi (mad@math.keio.ac.jp)
*/
/*
 * KON2 - Kanji ON Console 2 -
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
#include        <stdlib.h>
#include	<sys/types.h>
#include	<sys/ioctl.h>
#include	<sys/file.h>
#include	<string.h>
#include	<sys/types.h>
#include	<sys/socket.h>
#include	<sys/mman.h>
/* #include	<linux/mm.h> */
#include <asm/page.h>
#include        <mem.h>

#include	<fnld.h>
#include	<interface.h>

#define ANK_BASE 0xFC000
#define ANK_SIZE 0x4000
#define	SCHAR_SIZE	(16*1)	/* Size of one hankaku char (bytes) */
#define	HANKAKU_OFFSET	32	/* No font for first 32 chars */
#define	SFONT_SIZE	(256*SCHAR_SIZE)	/* Font for 32(10)...128(10) */
#define KANJI_BASE 0xE0000
#define KANJI_SIZE 0x10000
#define MINKANJI 0x2121
#define MAXKANJI 0x7424

static char *fontrom;

extern struct fontInfo fi;

#define get_kfontoft(k1,k2)	(((k1) > 0x29) ? \
	((((k2) - 0x40) + ((k1) - 0x25) * 96) << 5) : \
	((((k2) - 0x20) + ((k1) - 0x20) * 96) << 5))

#define get_afontoft(c)	(c << 4)

static u_char *FontLoads(boldMode, Source)
int boldMode, Source;
{
  int devMem, i;
  u_short	word;
  u_char *fontbuf, bankNum;
  u_int offset;

  if (Source) {                     /* from BIOS ROM */
    if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
      fprintf(stderr, "Can not open /dev/mem.\n");
      exit(EOF);
    }
    if ((fontrom = malloc(ANK_SIZE + (PAGE_SIZE-1))) == NULL) {
      fprintf(stderr, "Memory allocation error.\n");
      exit (EOF);
    }
    if ((unsigned long)fontrom % PAGE_SIZE)
      fontrom += PAGE_SIZE - ((unsigned long)fontrom % PAGE_SIZE);
    fontrom = (unsigned char *)mmap(
				    (caddr_t)fontrom,
				    ANK_SIZE,
				    PROT_READ,
				    MAP_SHARED|MAP_FIXED,
				    devMem,
				    ANK_BASE
				    );
    if ((long)fontrom < 0) {
      fprintf(stderr, "Can not map memory.\n");
      exit(EOF);
    }

    if ((fontbuf = (u_char *)malloc(get_afontoft(256))) == NULL)
      return(NULL);
    fi.size = get_afontoft(128);
    if (Source == 1)
      offset = 0xA00;
    else
      offset = 0xC00;
    bmove(fontbuf, fontrom + offset, fi.size);
  } else {                       /* from KANJI ROM */
    if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
      fprintf(stderr, "Can not open /dev/mem.\n");
      exit(EOF);
    }
    if ((fontrom = valloc(KANJI_SIZE)) == NULL ||
	(fontbuf = calloc(1, SFONT_SIZE)) == NULL) {
      fprintf(stderr, "Memory allocation error.\n");
      exit (EOF);
    }
    fontrom = (u_char *)mmap(
			    (caddr_t)fontrom,
			    KANJI_SIZE,
			    PROT_READ|PROT_WRITE,
			    MAP_SHARED|MAP_FIXED,
			    devMem,
			    KANJI_BASE
			    );
    bankNum = 0x80;
    *fontrom = bankNum;
    for (i = HANKAKU_OFFSET*SCHAR_SIZE, offset = 0; i < (SFONT_SIZE/2); i ++) {
      word = *(u_short *) (fontrom + offset);
      fontbuf[i] = (word & 0xff);
      offset += 2;
    }
  }
  /* kana */
/*
  if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
    fprintf(stderr, "Can not open /dev/mem.\n");
    exit(EOF);
  }
*/
  if ((fontrom = valloc(KANJI_SIZE)) == NULL) {
    fprintf(stderr, "Memory allocation error.\n");
    exit (EOF);
  }
  fontrom = (u_char *)mmap(
			   (caddr_t)fontrom,
			   KANJI_SIZE,
			   PROT_READ|PROT_WRITE,
			   MAP_SHARED|MAP_FIXED,
			   devMem,
			   KANJI_BASE
			   );
  bankNum = 0x80;
  *fontrom = bankNum;
  for (i = 0xa00, offset = get_kfontoft(0x29, 0x20); i < 0xe00; i ++) {
    word = *(u_short *) (fontrom + offset);
    fontbuf[i] = (word & 0xff);
    offset += 2;
  }
  fi.size = SFONT_SIZE;
  if (boldMode) {
    for (i = 0; i < fi.size; i++) {
      *(fontbuf + i) |= *(fontbuf + i) >> 1;
    }
  }
  return(fontbuf);
}

static u_char	*FontLoadw(boldMode)
int boldMode;
{
  size_t start;
  int devMem, i;     /* , l; JL1KEO */
  u_char *fontbuf;
	
  if ((devMem = open("/dev/mem", O_RDWR) ) < 0) {
    fprintf(stderr, "Can not open /dev/mem.\n");
    exit(EOF);
  }
  if ((fontrom = malloc(KANJI_SIZE + (PAGE_SIZE-1))) == NULL) {
    fprintf(stderr, "Memory allocation error.\n");
    exit (EOF);
  }
  if ((unsigned long)fontrom % PAGE_SIZE)
    fontrom += PAGE_SIZE - ((unsigned long)fontrom % PAGE_SIZE);
  fontrom = (unsigned char *)mmap(
				  (caddr_t)fontrom,
				  KANJI_SIZE,
				  PROT_READ|PROT_WRITE,
				  MAP_SHARED|MAP_FIXED,
				  devMem,
				  KANJI_BASE
				  );
  if ((long)fontrom < 0) {
    fprintf(stderr, "Can not map memory.\n");
    exit(EOF);
  }

  fi.size = get_kfontoft((MAXKANJI+1)>>8, (MAXKANJI+1) & 0xFF);
  start = get_kfontoft((MINKANJI)>>8, (MINKANJI) & 0xFF);
  if ((fontbuf = (u_char *)malloc(fi.size)) == NULL) return(NULL);

  *fontrom = 0x80; bmove(fontbuf          , fontrom, 0x10000);
  *fontrom = 0x81; bmove(fontbuf + 0x10000, fontrom, 0x10000);
  *fontrom = 0x82; bmove(fontbuf + 0x20000, fontrom, 0x10000);
  *fontrom = 0x83; bmove(fontbuf + 0x30000, fontrom, 0x0b0a0);

  if (boldMode) {
    for (i = 0; i < fi.size; ) {
      if(*(fontbuf + i) & 0x01) {
	*(fontbuf + i + 1) |= (*(fontbuf + i + 1) >> 1) | 0x80;
      } else {
	*(fontbuf + i + 1) |= *(fontbuf + i + 1) >> 1;
      }
      *(fontbuf + i) |= *(fontbuf + i) >> 1;
      i += 2;
    }
  }

  return(fontbuf + start);
}

u_char *FontLoadJ3100(int argc, char **argv)
{
  int boldMode = 0, Source = 0;
  u_char *font = NULL;

  if (argc < 2) exit(EOF);
  if (argc > 2)                             /* Bold mode */
    if (*argv[2] == 'b' || *argv[2] == 'B')
      boldMode = 1;
  if (argc > 3)                             /* ASCII source */
    if (*argv[3] == 'b' || *argv[3] == 'B') /* from BIOS ROM */
      if (*(argv[3]+4) == '2')
	Source = 2;
      else
	Source = 1;
  if (*argv[1] == 'a' || *argv[1] == 'A') { /* ASCII mode */
    fi.width = 8;
    fi.high = 16;
    fi.type = CHR_SFONT;	/* single byte char */
    if (CheckLoadedFont(CHR_SFONT))
        font = FontLoads(boldMode, Source);
    else exit(0);
  } else {                                  /* KANJI mode */
    fi.width = 16;
    fi.high = 16;
    fi.type = CHR_WFONT;	/* double byte char */
    if (CheckLoadedFont(CHR_WFONT))
        font = FontLoadw(boldMode);
    else exit(0);
  }
}

#if 0
void main(argc, argv)
int argc;
char *argv[];
{
  int boldMode = 0, Source = 0;
  u_char *font = NULL;

  if (argc < 2) exit(EOF);
  if (argc > 2)                             /* Bold mode */
    if (*argv[2] == 'b' || *argv[2] == 'B')
      boldMode = 1;
  if (argc > 3)                             /* ASCII source */
    if (*argv[3] == 'b' || *argv[3] == 'B') /* from BIOS ROM */
      if (*(argv[3]+4) == '2')
	Source = 2;
      else
	Source = 1;
  if (*argv[1] == 'a' || *argv[1] == 'A') { /* ASCII mode */
    fi.width = 8;
    fi.high = 16;
    fi.type = CHR_SFONT;	/* single byte char */
    if (CheckLoadedFont(CHR_SFONT))
        font = FontLoads(boldMode, Source);
    else exit(0);
  } else {                                  /* KANJI mode */
    fi.width = 16;
    fi.high = 16;
    fi.type = CHR_WFONT;	/* double byte char */
    if (CheckLoadedFont(CHR_WFONT))
        font = FontLoadw(boldMode);
    else exit(0);
  }
  if (font == NULL) {
    fprintf(stderr, "%s> Can not load font file.\n", argv[0]);
    exit(EOF);
  }

  exit(SetFont(argv[0], font, &fi));
}
#endif
