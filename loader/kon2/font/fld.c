/*
  KON - Kanji ON Linux Console -
  Copyright (C) 1992, 1993 Takashi MANABE (manabe@tut.ac.jp)
  
  KON is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.
  
  KON is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
  See the GNU General Public License for more details.
  
  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
  */

#include	<stdio.h>
#include	<stdlib.h>
#include	<unistd.h>
#include	<sys/types.h>
#include	<sys/file.h>
#include	<string.h>
#include	<ctype.h>
#include	<sys/ipc.h>
#include	<sys/shm.h>
#include	<sys/socket.h>
#include	<errno.h>

#include	<interface.h>
#include	<fnld.h>

int forceLoad=1;
struct fontInfo fi;

u_char *FontLoadMinix();
u_char *FontLoadFontx();
u_char *FontLoadBdf();
#if defined(linux)
u_char *FontLoadJ3100();
#endif

static struct {
    char *type;
    u_char* (*loader)(FILE *fp);
} fontLoaders[] = {
    {"minix", FontLoadMinix},
    {"fontx", FontLoadFontx},
    {"bdf", FontLoadBdf},
    {"j3100", NULL},
    {NULL, NULL}
};

void UnloadShmem(char fnum)
{
    key_t shmkey;
    int	shmid;
    struct shmid_ds shmseg;

#if defined(linux)
    shmkey = ftok(CONFIG_NAME, fnum);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fnum & 0x7F);
#endif
    if ((shmid = shmget(shmkey, sizeof(struct fontInfo), 0444)) < 0)
	return;
    shmctl(shmid, IPC_STAT, &shmseg);
    if (shmseg.shm_nattch < 1) {
	shmctl(shmid, IPC_RMID, 0);
    }
}

int CheckLoadedFont(char fnum)
{
    key_t shmkey;
    extern int forceLoad;

    if (forceLoad) return(EOF);
#if defined(linux)
    shmkey = ftok(SHMEM_NAME, fnum);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fnum & 0x7F);
#endif
    if (shmget(shmkey, 1, 0444) == EOF) return(EOF);
    return(0);
}

static
    void ShmFont(char *prog, u_char *font, struct fontInfo *fi)
{
    key_t shmkey;
    int	shmid;
    u_char *shmbuff;

#if defined(linux)
    shmkey = ftok(SHMEM_NAME, fi->type);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fi->type & 0x0000007F);
#endif
    shmid = shmget(shmkey, fi->size+sizeof(struct fontInfo),
		   IPC_CREAT|0666);
    shmbuff = shmat(shmid, 0, 0);
    memcpy(shmbuff, fi, sizeof(struct fontInfo));
    memcpy(shmbuff + sizeof(struct fontInfo), font, fi->size);
    shmdt(shmbuff);
    fprintf(stderr, "%s> load %s in shmem(%d): %d Bytes\n",
	    prog,
	    (fi->type & CHR_DBC) ?
	    fDRegs[fi->type&~CHR_DFLD].registry:
	    fSRegs[fi->type&~CHR_SFLD].registry,
	    shmid, fi->size);
}

int SetFont(char *prog, u_char *font, struct fontInfo *fi)
{
    int s;

    if ((s = SocketClientOpen()) > 0) {
	SocketSendCommand(s, CHR_UNLOAD);
	close(s);
    }
    ShmFont(prog, font, fi);
    if ((s = SocketClientOpen()) > 0) {
	SocketSendCommand(s, CHR_LOAD);
	close(s);
    }
    return(0);
}

void
ShowShmem(u_char fnum)
{
    key_t shmkey;
    int shmid;
    struct fontInfo *fi;

#if defined(linux)
    shmkey = ftok(CONFIG_NAME, fnum);
#elif defined(__FreeBSD__)
    shmkey = 5000 + (fnum & 0x7F);
#endif
    if ((shmid = shmget(shmkey, sizeof(struct fontInfo), 0444)) < 0)
	return;
    fi = (struct fontInfo*)shmat(shmid, 0, SHM_RDONLY);
    if (fi) {
	printf("%3X %6d %-15s %2dx%2d %7d\n",
	       fnum&~CHR_SFLD,
	       shmid,
	       (fnum & CHR_DBC) ?
	       fDRegs[fnum&~CHR_DFLD].registry:
	       fSRegs[fnum&~CHR_SFLD].registry,
	       fi->width,
	       fi->high,
	       fi->size);
    }
}

void ShowFont()
{
    int i;

    i = 0;
    printf(" No. ShmId Font Name       Size  MemSize\n"
	   "+---+-----+---------------+-----+-------+\n");
    while (fSRegs[i].registry) {
	ShowShmem(i|CHR_SFLD);
	i ++;
    }
    i = 0;
    while (fDRegs[i].registry) {
	ShowShmem(i|CHR_DFLD);
	i ++;
    }
}

void main(argc, argv)
int argc;
char *argv[];
{
    int i, n;
    FILE *fp = stdin;
    enum {ST_ARG, ST_UNLOAD, ST_TYPE} st=ST_ARG;
    char file[256], *type, *p;
    u_char *font;

    if ((p = index(argv[0], '.')) != NULL) type = p + 1;
    for (i = 1; i < argc; i ++) {
	p = argv[i];
	switch(st) {
	case ST_UNLOAD:
	    if (isxdigit(*p)) {
		sscanf(p, "%X", &n);
		fprintf(stderr, "%s> unload %X(%s)\n", argv[0], n,
			(n & CHR_DBC) ?
			fDRegs[n&~CHR_DFLD].registry:
			fSRegs[n&~CHR_SFLD].registry);
		UnloadShmem(n | CHR_SFLD);
		break;
	    }
	    st = ST_ARG;
	case ST_ARG:
	    if (*p == '-') {
		++p;
		switch(*p) {
		case 'n':
		    forceLoad = 0;
		    break;
		case 'u':
		    st = ST_UNLOAD;
		    break;
		case 't':
		    st = ST_TYPE;
		    break;
		case 'i':
		    ShowFont();
		    exit(0);
		    break;
		}
	    } else {
		if(!(fp = fopen(argv[i], "r"))) {
		    fprintf(stderr, "%s> Can not open font file.\n", argv[0]);
		    exit(EOF);
		}
	    }
	    break;
	case ST_TYPE:
	    type = p;
	    st = ST_ARG;
	    break;
	}
    }
    if (st == ST_UNLOAD) exit(0);
    i = 0;
    while (fontLoaders[i].type) {
	if (!strcasecmp(fontLoaders[i].type, type))
	    break;
	i ++;
    }
    if (!fontLoaders[i].type) {
	fprintf(stderr, "%s> type %s is not supported.\n",
		argv[0], type); 
	exit(EOF);
    }
#if defined(linux)
    if (!fontLoaders[i].loader)
	font = FontLoadJ3100(argc, argv);
    else
#endif
      font = fontLoaders[i].loader(fp);
    if (font == NULL) {
	fprintf(stderr, "%s> Can not load font.\n", argv[0]);
	exit(EOF);
    }
    if (fp != stdin) fclose(fp);
    exit(SetFont(argv[0], font, &fi));
}
