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

#include	<config.h>

#include	<stdio.h>
#include	<stdlib.h>
#include	<sys/types.h>
#include	<sys/file.h>
#include	<string.h>
#include	<unistd.h>
#include	<sys/ipc.h>
#include	<sys/shm.h>

#include	<interface.h>
#include	<vt.h>
#include	<fnld.h>

struct fontRegs *dbFReg, *sbFReg;

#ifdef	MINI_KON

/*#define	USE_GZFONT	1*/

#ifdef	USE_GZFONT
#define	PATH_MINIFONT	"/usr/lib/minikon.fnt.gz"
#define	CMD_MINIFONT	"/bin/gzip -dc "PATH_MINIFONT
#else
#define	PATH_MINIFONT	"/etc/minikon.fnt"
#endif

void
LoadMiniFont()
{
    int	addr, bytes;
    u_char type, high;
    u_short max;
    FILE *fp;
    struct fontRegs *freg;
    struct {
	u_short code;
	u_char bitmap[32];
    } fent;
    char dummy[]={
	0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
	0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01,
	0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
	0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01,
    };

    type = CodingByRegistry("JISX0208.1983-0");
    freg = &fDRegs[type & ~CHR_DFLD];
#ifdef	USE_GZFONT
    if ((fp = popen(CMD_MINIFONT, "r")) == NULL) {
#else
    if ((fp = fopen(PATH_MINIFONT, "r")) == NULL) {
#endif
	perror(PATH_MINIFONT);
	return;
    }
    fread(&high, sizeof(high), 1, fp);
    fread(&max, sizeof(max), 1, fp);
    max ++;
    freg->size = freg->addr(max>>8, max & 0xFF);
    freg->high = high;
    freg->stat = FR_ATTACH;
    freg->bitmap = malloc(freg->size);
    for (addr = 0; addr < freg->size; addr += 32) {
	memcpy(freg->bitmap + addr, dummy, 32);
    }
    bytes = high * 2;

    while (fread(&fent, sizeof(fent.code) + bytes, 1, fp) > 0) {
	addr = freg->addr(fent.code >> 8, fent.code & 0xFF);
	memcpy(freg->bitmap + addr, fent.bitmap, bytes);
    }

#ifdef	USE_GZFONT
    pclose(fp);
#else
    fclose(fp);
#endif
}

void
VgaLoadRomFont(char *fontbuff)
{
    static int loaded=0;
    int i;

    if (loaded) return;
    i = 1;
    sbFReg = &fSRegs[0];
    sbFReg->size = 256 * 16;
    sbFReg->high = 16;
    sbFReg->stat = FR_ATTACH;
    sbFReg->bitmap = calloc(sbFReg->size, 1);
    while (fSRegs[i].registry) {
	fSRegs[i].high = sbFReg->high;
	fSRegs[i].stat = FR_PROXY;
	fSRegs[i].size = sbFReg->size;
	fSRegs[i].bitmap = sbFReg->bitmap;
	i ++;
    }

    for (i = 0; i < sbFReg->size; i += sbFReg->high) {
	memcpy(&(sbFReg->bitmap[i]), &(fontbuff[i*2]), sbFReg->high);
    }
    loaded = 1;
}

#else

#ifdef	USE_ROMFONT

void
VgaLoadRomFont(char *fontbuff)
{
    static int loaded=0;
    key_t shmkey;
    int	shmid, i;
    u_char *shmbuff, *buff;
    struct fontInfo fi;

    if (loaded) return;
    shmkey = ftok(CONFIG_NAME, CHR_SFLD);
    fi.size = 256 * 16;
    fi.high = 16;
    fi.width = 8;
    fi.type = CHR_SFLD;
    shmid = shmget(shmkey, fi.size+sizeof(struct fontInfo),
		   IPC_CREAT|0666);
    shmbuff = shmat(shmid, 0, 0);
    memcpy(shmbuff, &fi, sizeof(struct fontInfo));
    buff = shmbuff + sizeof(struct fontInfo);

    for (i = 0; i < fi.size; i += fi.high) {
	memcpy(&(buff[i]), &(fontbuff[i*2]), fi.high);
    }
    shmdt(shmbuff);
    loaded = 1;
}

#endif

void FontDetach(bool down)
{
    int i;

    i = 0;
    while (fSRegs[i].registry) {
	if (fSRegs[i].stat & FR_ATTACH)
	    shmdt(fSRegs[i].bitmap - sizeof(struct fontInfo));
	if (down) DownShmem(i|CHR_SFLD);
	fSRegs[i].width = fSRegs[i].high =
	    fSRegs[i].size = fSRegs[i].stat = 0;
	i ++;
    }
    i = 0;
    while (fDRegs[i].registry) {
	if (fDRegs[i].stat & FR_ATTACH)
	    shmdt(fDRegs[i].bitmap - sizeof(struct fontInfo));
	if (down) DownShmem(i|CHR_DFLD);
	fDRegs[i].width = fDRegs[i].high =
	    fDRegs[i].size = fDRegs[i].stat = 0;
	i ++;
    }
}

void FontAttach()
{
    int i;
    u_char *font;
    struct fontInfo *fi;

    i = 0;
    while (fSRegs[i].registry) {
	if ((font = GetShmem(i|CHR_SFLD)) != NULL) {
	    fi = (struct fontInfo*)font;
	    fSRegs[i].high = fi->high;
	    fSRegs[i].stat = FR_ATTACH;
	    fSRegs[i].size = fi->size;
	    fSRegs[i].bitmap = font + sizeof(struct fontInfo);
	    sbFReg = &fSRegs[i];
	} else fSRegs[i].stat = 0;
	i ++;
    }
    if (fSRegs[lInfo.sb].stat) sbFReg = &fSRegs[lInfo.sb];
#if 1
    i = 0;
    while (fSRegs[i].registry) {
	if (!fSRegs[i].stat) {
	    fSRegs[i].high = sbFReg->high;
	    fSRegs[i].size = sbFReg->size;
	    fSRegs[i].bitmap = sbFReg->bitmap;
	    fSRegs[i].stat = FR_PROXY;
	}
	i ++;
    }
#endif
    i = 0;
    while (fDRegs[i].registry) {
	if ((font = GetShmem(i|CHR_DFLD)) != NULL) {
	    fi = (struct fontInfo*)font;
	    fDRegs[i].high = fi->high;
	    fDRegs[i].stat = FR_ATTACH;
	    fDRegs[i].size = fi->size;
	    fDRegs[i].bitmap = font + sizeof(struct fontInfo);
	}
	i ++;
    }
    dbFReg = &fDRegs[lInfo.db];
}
#endif
