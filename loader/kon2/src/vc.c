/*
 * KON2 - Kanji ON Console -
 * Copyright (C) 1992, 1993 MAEDA Atusi (mad@math.keio.ac.jp)
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
 * THIS SOFTWARE IS PROVIDED BY MAEDA ATUSI AND TAKASHI MANABE ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
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
#include	<string.h>
#include	<unistd.h>
#if defined(linux)
#include	<sys/vt.h>
#endif
#include	<fcntl.h>
#include	<signal.h>
#include	<termios.h>
#if defined(__FreeBSD__)
#include	<machine/console.h>
#endif
#include	<sys/ioctl.h>
#ifdef linux
#include	<sys/kd.h>
#endif

#include	<mem.h>
#include	<getcap.h>

#include	<defs.h>
#include	<errors.h>
#include	<fnld.h>
#ifndef	MINI_KON
#include	<mouse.h>
#endif
#include	<vc.h>
#include	<vt.h>
#include	<term.h>

struct dispInfo		dInfo;
struct cursorInfo	cInfo;
struct videoInfo	vInfo;
#ifndef	MINI_KON
static struct cursorInfo	mouseCursor;
#endif

static bool	textClear;

static int	textHead, scrollLine;
static u_int	textSize;
static u_char	*textBuff, *attrBuff, *flagBuff;

static int	saveTime, saverCount;
static bool	saved;
static bool	useHardScroll;
static volatile bool	busy;		 /* TRUE iff updating screen */
static volatile bool	release;	 /* delayed VC switch flag */

static void	ShowCursor(struct cursorInfo *, bool);

static void	LeaveVC(int);
static void	EnterVC(int);

/*

  flagBuff:
  |      7|      6|      5|4||3|2|1|0|
  |CLEAN_S|LATCH_2|LATCH_1| ||<----->|
  |0=latch|  byte2|  byte1| ||   LANG|

  */

#define	KON_TMP_FILE	"/tmp/.kontmp"

static
inline	void	blatch(void *head, int n)
{

    __asm__("\t clc\n"
	    "1:\n"
	    "\t andb %%bl, (%%eax)\n"
	    "\t incl %%eax\n"
	    "\t loop 1b\n"
	    :
	    : "eax" ((long)head), "bl" (0x7F), "c" (n)
	    : "bl", "cx" );
}

static
inline	void	llatch(void *head, int n)
{

    __asm__("\t clc\n"
	    "1:\n"
	    "\t andl %%ebx, (%%eax)\n"
	    "\t addl $4, %%eax\n"
	    "\t loop 1b\n"
	    :
	    : "eax" ((long)head), "ebx" (0x7F7F7F7F), "c" (n>>2)
	    : "ebx", "cx" );
}

static inline u_int	TextAddress(u_int x, u_int y)
{
    return (textHead + x + y * dInfo.glineByte) % textSize;
}

static inline bool	IsKanji(u_int x, u_int y)
{
    return(*(flagBuff + TextAddress(x, y)) & CODEIS_1);
}

static inline bool	IsKanji2(u_int x, u_int y)
{
    return(*(flagBuff + TextAddress(x, y)) & CODEIS_2);
}

void    euctosjis(ch, cl)
u_char  *ch, *cl;
{
    u_char  nh, nl;
    
    nh = ((*ch - 0x21) >> 1) + 0x81;
    if (nh > 0x9F) nh += 0x40;
    if (*ch & 1) {
	nl = *cl + 0x1F;
	if (*cl > 0x5F)
	    nl ++;
    } else nl = *cl + 0x7E;
    *cl = nl;
    *ch = nh;
}

void	TextDeleteChar(int n)
{
    u_int	addr, dx;
    
    addr = TextAddress(con.x, con.y);
    dx = dInfo.glineByte - con.x - n;
    
    bmove(textBuff + addr, textBuff + addr + n, dx);
    bmove(attrBuff + addr, attrBuff + addr + n, dx);
    bmove(flagBuff + addr, flagBuff + addr + n, dx);
    blatch(flagBuff + addr, dx);
    
    addr = TextAddress(dInfo.glineByte - n, con.y);
    bzero2(textBuff + addr, n);
    bzero2(attrBuff + addr, n);
    bzero2(flagBuff + addr, n);
}

void	TextInsertChar(int n)
{
    u_int	addr, dx;
    
    addr = TextAddress(dInfo.txmax, con.y);
    dx = dInfo.glineByte - con.x - n;
    brmove(textBuff + addr, textBuff + addr - n, dx);
    brmove(attrBuff + addr, attrBuff + addr - n, dx);
    brmove(flagBuff + addr, flagBuff + addr - n, dx);
    
    addr = TextAddress(con.x, con.y);

    blatch(flagBuff + addr + n, dx);
    bzero2(textBuff + addr, n);
    bzero2(attrBuff + addr, n);
    bzero2(flagBuff + addr, n);
}

void	TextRefresh(void)
{
    u_int	fnt, i;
    u_char	ch, ch2, fc, bc;
    
    busy = TRUE;
    if (!con.active) {
	busy = FALSE;
	return;
    }
    ShowCursor(&cInfo, FALSE);
#ifndef	MINI_KON
    ShowCursor(&mouseCursor, FALSE);
#endif
    if (textClear) vInfo.clear_all();
    if (useHardScroll) {
	if (scrollLine > 0) vInfo.hard_scroll_up(scrollLine);
	else if (scrollLine < 0) vInfo.hard_scroll_down(- scrollLine);
	scrollLine = 0;
    }
    textClear = FALSE;
    for (i = 0; i < textSize; i ++) {
	if (*(flagBuff + i)&CLEAN_S) continue; /* already clean */
	vInfo.set_address(i);
	fc = *(attrBuff + i);
	bc = *(attrBuff + i) >> 4;
	ch = *(textBuff + i);
	*(flagBuff + i) |= CLEAN_S;
	if (*(flagBuff + i) & CODEIS_1) {
	    dbFReg = &fDRegs[*(flagBuff + i)&LANG_CODE];
	    i ++;
	    *(flagBuff + i) |= CLEAN_S;
	    ch2 = *(textBuff + i);
	    fnt = dbFReg->addr(ch2, ch);
#if 0
		{
		    FILE *fp=fopen("errlog", "a");
		    fprintf(fp,"<%x %s %d %X %X %X>\n",
			    *(flagBuff + i - 1)&LANG_CODE,
			    dbFReg->registry, dbFReg->size, ch2, ch, fnt);
		    fclose(fp);
		}
#endif
	    if (con.ins) TextInsertChar(2);
	    if (fnt < dbFReg->size)
		vInfo.wput(dbFReg->bitmap + fnt, fc, bc);
	} else {
	    sbFReg = &fSRegs[*(flagBuff + i)&LANG_CODE];
#if 0
	    {
		FILE *fp=fopen("errlog", "a");
		fprintf(fp,"<%x %s %d>\n",
			*(flagBuff + i)&LANG_CODE,
			sbFReg->registry, sbFReg->size);
		fclose(fp);
	    }
#endif
	    if (con.ins) TextInsertChar(1);
	    vInfo.sput(ch ? sbFReg->bitmap + (ch << 4):0, fc, bc);
	}
    }
    cInfo.kanji = IsKanji(con.x, con.y);
    vInfo.set_cursor_address(&cInfo, con.x, con.y);
    ShowCursor(&cInfo, TRUE);
    busy = FALSE;
    if (release)
	LeaveVC(SIGUSR1);
}

static struct winsize text_win;

static void SetTextMode(void)
{
    ShowCursor(&cInfo, FALSE);
    vInfo.clear_all();
    vInfo.text_mode();
    ioctl(0, KDSETMODE, KD_TEXT);
    ioctl(0, TIOCCONS, NULL);
}

void TextMode(void)
{
    struct vt_mode vtm;

    signal(SIGUSR1, SIG_DFL);
    signal(SIGUSR2, SIG_DFL);
    vtm.mode = VT_AUTO;
    vtm.waitv = 0;
    vtm.relsig = 0;
    vtm.acqsig = 0;
    ioctl(0, VT_SETMODE, &vtm);
#if defined(__FreeBSD__)
    ioctl(0, VT_RELDISP, 1);
#endif
    con.text_mode = TRUE;
    SetTextMode();
    ioctl(masterPty, TIOCSWINSZ, &text_win);
}

void GraphMode(void)
{
    struct winsize win;
    struct vt_mode vtm;

    con.text_mode = FALSE;
    ioctl(0, KDSETMODE, KD_GRAPHICS);
#if defined(__FreeBSD__)
    ioctl(0, VT_RELDISP, VT_ACKACQ);
#endif
    signal(SIGUSR1, LeaveVC);
    signal(SIGUSR2, EnterVC);
    vtm.mode = VT_PROCESS;
    vtm.waitv = 0;
    vtm.relsig = SIGUSR1;
    vtm.acqsig = SIGUSR2;
    ioctl(0, VT_SETMODE, &vtm);
    vInfo.graph_mode();
    if (useHardScroll)
	vInfo.set_start_address();
    
    win.ws_row = dInfo.tymax + 1;	 /* Note: con.ymax may be changed by application */
    win.ws_col = dInfo.txmax + 1;
    win.ws_xpixel = win.ws_ypixel = 0;
    ioctl(masterPty, TIOCSWINSZ, &win);
    ioctl(masterPty, TIOCCONS, NULL);
    
    llatch(flagBuff, textSize);
    textClear = TRUE;
    TextRefresh();
}

static
    void	LeaveVC(int signum)
{

    signal(SIGUSR1, LeaveVC);  /* should use sigaction()? */
    if (busy) {
        release = TRUE;
	return;
    }
    release = FALSE;
    con.active = FALSE;
    SetTextMode();
#ifdef	HAS_MOUSE
    if (mInfo.has_mouse) {
	MouseResetRfd(mouseFd);
	MouseCleanup();
    }
#endif
    ioctl(0, VT_RELDISP, 1);
}

static
    void	EnterVC(int signum)
{
    signal(SIGUSR2, EnterVC);
    if (!con.active) {
	con.active = TRUE;
	GraphMode();
    signal(SIGUSR2, EnterVC);
#ifdef	HAS_MOUSE
	if (mInfo.has_mouse) {
	    MouseStart();
	    MouseSetRfd(mouseFd);
	}
#endif
    }
}

static
    void	TextScrollUp(int line)
{
    int	oldhead, len;
    
    oldhead = textHead;
    textHead += line * dInfo.glineByte;
    if (textHead > textSize) {
	textHead -= textSize;
	len = textSize - oldhead;
	if (textHead) {
	    lzero(textBuff, textHead);
	    lzero(attrBuff, textHead);
	    lzero(flagBuff, textHead);
	}
    } else len = textHead - oldhead;
    lzero(textBuff + oldhead, len);
    lzero(attrBuff + oldhead, len);
    lzero(flagBuff + oldhead, len);
}

static
    void	TextScrollDown(int line)
{
    int	oldhead, len;
    
    oldhead = textHead;
    textHead -= line * dInfo.glineByte;
    if (textHead < 0) {
	textHead += textSize;
	if (oldhead) {
	    lzero(textBuff, oldhead);
	    lzero(attrBuff, oldhead);
	    lzero(flagBuff, oldhead);
	}
	len = textSize - textHead;
    } else len = oldhead - textHead;
    lzero(textBuff + textHead, len);
    lzero(attrBuff + textHead, len);
    lzero(flagBuff + textHead, len);
}

void TextWput(u_char ch1, u_char ch2)
{
    u_int addr;
    u_char *p;
    
    addr = TextAddress(con.x, con.y);
    *(attrBuff + addr) = con.fcol | (con.bcol << 4);
    *(p = textBuff + addr) = ch2;
    *(p + 1) = ch1;
    *(p = flagBuff + addr) = con.db;
    *(p + 1) = LATCH_2;
}

void TextSput(u_char ch)
{
    u_int addr;

    addr = TextAddress(con.x, con.y);
    *(flagBuff + addr) = LATCH_S|con.sb;
    *(attrBuff + addr) = con.fcol | (con.bcol << 4);
    *(textBuff + addr) = ch;
}

void TextClearAll(void)
{
#if 1
    u_int y, addr;

    for (y = 0; y <= con.ymax; y ++) {
	addr = TextAddress(0, y);
	lzero(textBuff + addr, dInfo.glineByte);
	lzero(attrBuff + addr, dInfo.glineByte);
    }
#else
    lzero(textBuff, textSize);
    lzero(attrBuff, textSize);
#endif
    lzero(flagBuff, textSize);
#ifndef	MINI_KON
    mInfo.sw = 0;
#endif
    textClear = TRUE;
}

void	TextClearEol(u_char mode)
{
    u_int	addr;
    u_char	len, x=0;
    
    switch(mode) {
    case 1:
	len = con.x;
	break;
    case 2:
	len = dInfo.glineByte;
	break;
    default:
	x = con.x;
	len = dInfo.glineByte - con.x;
	break;
    }
    addr = TextAddress(x, con.y);
    bzero2(textBuff + addr, len);
    bzero2(attrBuff + addr, len);
    bzero2(flagBuff + addr, len);/* needless to latch */
}

void	TextClearEos(u_char mode)
{
    u_int	addr, len, y;
    
    if (mode == 2) {
	TextClearAll();
	return;
    }
    switch(mode) {
    case 1:
	for (y = 0; y < con.y; y ++) {
	    addr = TextAddress(0, y);
	    lzero(textBuff + addr, dInfo.glineByte);
	    lzero(attrBuff + addr, dInfo.glineByte);
	    lzero(flagBuff + addr, dInfo.glineByte);/* needless to latch */
	}
	addr = TextAddress(0, con.y);
	bzero2(textBuff + addr, con.x);
	bzero2(attrBuff + addr, con.x);
	bzero2(flagBuff + addr, con.x);/* needless to latch */
	break;
    default:
	for (y = con.y + 1; y <= con.ymax; y ++) {
	    addr = TextAddress(0, y);
	    lzero(textBuff + addr, dInfo.glineByte);
	    lzero(attrBuff + addr, dInfo.glineByte);
	    lzero(flagBuff + addr, dInfo.glineByte);/* needless to latch */
	}
	addr = TextAddress(con.x, con.y);
	len = dInfo.glineByte - con.x;
	bzero2(textBuff + addr, len);
	bzero2(attrBuff + addr, len);
	bzero2(flagBuff + addr, len);/* needless to latch */
	break;
    }
}

static
    void	TextClearBand(u_int top, u_int btm)
{
    u_int	y, addr;
    
    for (y = top; y <= btm; y ++) {
	addr = TextAddress(0, y);
	lzero(textBuff + addr, dInfo.glineByte);
	lzero(attrBuff + addr, dInfo.glineByte);
	lzero(flagBuff + addr, dInfo.glineByte);/* needless to latch */
    }
}

void	TextMoveDown(int top, int btm, int line)
{
    u_int	n, src, dst;
    
    if (btm - top - line + 1 <= 0) {
	TextClearBand(top, btm);
	return;
    }
    for (n = btm; n >= top + line; n --) {
	dst = TextAddress(0, n);
	src = TextAddress(0, n - line);
	lmove(textBuff + dst, textBuff + src, dInfo.glineByte);
	lmove(attrBuff + dst, attrBuff + src, dInfo.glineByte);
	lmove(flagBuff + dst, flagBuff + src, dInfo.glineByte);
	llatch(flagBuff + dst, dInfo.glineByte);
    }
    TextClearBand(top, top + line - 1);
}

void	TextMoveUp(int top, int btm, int line)
{
    u_int	n, src, dst;
    
    if (btm - top - line + 1 <= 0) {
	TextClearBand(top, btm);
	return;
    }
    for (n = top; n <= btm - line; n ++) {
	dst = TextAddress(0, n);
	src = TextAddress(0, n + line);
	lmove(textBuff + dst, textBuff + src, dInfo.glineByte);
	lmove(attrBuff + dst, attrBuff + src, dInfo.glineByte);
	lmove(flagBuff + dst, flagBuff + src, dInfo.glineByte);
	llatch(flagBuff + dst, dInfo.glineByte);
    }
    TextClearBand(btm - line + 1, btm);
}

void	ScrollUp(int line)
{
    if (useHardScroll && !con.soft) {
	TextScrollUp(line);
	scrollLine += line;
    } else
	TextMoveUp(con.ymin, con.ymax, line);
}

void	ScrollDown(int line)
{
    if (useHardScroll && !con.soft) {
	TextScrollDown(line);
	scrollLine -= line;
    } else
	TextMoveDown(con.ymin, con.ymax, line);
}

static inline void	KanjiAdjust(int *x, int *y)
{
    if (IsKanji2(*x, *y)) {
	--*x;
    }
}

void	TextReverse(int fx, int fy, int tx, int ty)
{
    u_int	from, to, y, swp, xx, x;
    u_char	fc, bc, fc2, bc2;
    
    KanjiAdjust(&fx, &fy);
    KanjiAdjust(&tx, &ty);
    if (fy > ty) {
	swp = fy;
	fy = ty;
	ty = swp;
	swp = fx;
	fx = tx;
	tx = swp;
    } else if (fy == ty && fx > tx) {
	swp = fx;
	fx = tx;
	tx = swp;
    }
    for (xx = dInfo.txmax, y = fy; y <= ty; y ++) {
	if (y == ty) xx = tx;
	from = TextAddress(fx, y);
	to = TextAddress(xx, y);
	if (flagBuff[from] & CODEIS_2)
	    /* 2nd byte of kanji */
	    from--;
	for (x = from; x <= to; x ++) {
	    if (!textBuff[x]) continue;
	    fc = attrBuff[x];
	    bc = fc >> 4;
	    bc2 = (bc & 8) | (fc & 7);
	    fc2 = (fc & 8) | (bc & 7);
	    attrBuff[x] = fc2 | (bc2 << 4);
	    flagBuff[x] &= ~CLEAN_S;
	}
	fx = 0;
    }
}

#ifndef	MINI_KON

void	TextCopy(int fx, int fy, int tx, int ty)
{
    int	fd;
    u_int	from, to, y, swp, xx, x;
    u_char	ch, ch2;

    unlink(KON_TMP_FILE);
    if ((fd = open(KON_TMP_FILE, O_WRONLY|O_CREAT, 0600)) < 0) return;

    KanjiAdjust(&fx, &fy);
    KanjiAdjust(&tx, &ty);
    if (fy > ty) {
	swp = fy;
	fy = ty;
	ty = swp;
	swp = fx;
	fx = tx;
	tx = swp;
    } else if (fy == ty && fx > tx) {
	swp = fx;
	fx = tx;
	tx = swp;
    }
    for (xx = dInfo.txmax, y = fy; y <= ty; y ++) {
	if (y == ty) xx = tx;
	from = TextAddress(fx, y);
	if (flagBuff[from] & CODEIS_2)
	    /* 2nd byte of kanji */
	    from--;
	to = TextAddress(xx, y);
	for (x = to; x >= from; x --) if (textBuff[x] > ' ') break;
	to = x;
	for (x = from; x <= to; x ++) {
	    ch = textBuff[x];
	    if (!ch) ch = ' ';
	    if (flagBuff[x] & CODEIS_1) {
		x ++;
		ch2 = textBuff[x];
		switch(lInfo.sc) {
		case CODE_EUC:
		    ch2 |= 0x80;
		    ch |= 0x80;
		    break;
		case CODE_SJIS:
		    jistosjis(ch2, ch);
		    break;
		}
		write(fd, &ch2, 1);
		write(fd, &ch, 1);
	    } else write(fd, &ch, 1);
	}
	if (y < ty) {
	    ch = '\n';
	    write(fd, &ch, 1);
	}
	fx = 0;
    }
    close(fd);
}

void	TextPaste(void)
{
    u_char	ch;
    int	fd;
    
    if ((fd = open(KON_TMP_FILE, O_RDONLY)) < 0) return;
    while(read(fd, &ch, 1) == 1) write(masterPty, &ch, 1);
    close(fd);
}

#endif

/* Cursor related routines. */

static void	ToggleCursor(struct cursorInfo *c)
{
    c->count = 0;
    if (con.text_mode)
	return;
    c->shown = ! c->shown;
    vInfo.cursor(c);
}

static void	ShowCursor(struct cursorInfo *c, bool show)
{
    if (!con.active || !c->sw)
	return;
    if (c->shown != show)
	ToggleCursor(c);
}

static void	SaveScreen(bool save)
{
    if (saved != save) {
	saved = save;
	vInfo.screen_saver(save);
    }
    saverCount = 0;
}

#ifndef	MINI_KON
static void PollMouseCursor(void)
{
    ShowCursor(&mouseCursor, FALSE);
    if (mInfo.sw > 0) {
	--mInfo.sw;
	if (cInfo.shown) {
	    int	x = mInfo.x, y = mInfo.y;
	    
	    KanjiAdjust(&x, &y);
	    mouseCursor.kanji = IsKanji(x, y);
	    vInfo.set_cursor_address(&mouseCursor, x, y);
	    ShowCursor(&mouseCursor, TRUE);
	}
    }
}
#endif

/* Called when some action was over, or every 1/10 sec when idle. */

void	PollCursor(bool wakeup)
{
    if (!con.active)
	return;
    if (wakeup) {
	SaveScreen(FALSE);
	ShowCursor(&cInfo, TRUE);
#ifndef	MINI_KON
	PollMouseCursor();
#endif
	return;
    }
    /* Idle. */
    if (saved)
	return;
    if ((saveTime > 0) && (++saverCount == saveTime)) {
	ShowCursor(&cInfo, FALSE);
#ifndef	MINI_KON
	ShowCursor(&mouseCursor, FALSE);
#endif
	SaveScreen(TRUE);
	return;
    }
    if ((cInfo.interval > 0) && (++cInfo.count == cInfo.interval)) {
	ToggleCursor(&cInfo);
    }
#ifndef	MINI_KON
    if (mInfo.has_mouse) {
	PollMouseCursor();
    }
#endif
}

/* Configuration routines. */

extern int	SvgaSetVideoType(struct videoInfo*, const char*);
extern int	VgaFmSetVideoType(struct videoInfo*, const char*);
extern int	S3SetVideoType(struct videoInfo*, const char*);
extern int	J31SXSetVideoType(struct videoInfo*, const char*);

static struct videoconf {
    const char *name;
    int	(*set)(struct videoInfo*, const char*);
} videos[] = {
#ifdef	HAS_VGA
    {"VGA", SvgaSetVideoType},
#ifndef	MINI_KON
    {"VGAFM", VgaFmSetVideoType},
    {"EGA", SvgaSetVideoType},
    {"SVGA", SvgaSetVideoType},
#endif
#endif
#ifdef	HAS_S3
    {"S3", S3SetVideoType},
#endif
#ifdef	HAS_J31SX
    {"J3100SX", J31SXSetVideoType},
#endif
    {NULL, NULL}
};

static int	ConfigHardScroll(const char *confstr)
{
    bool value = BoolConf(confstr);
    useHardScroll = value;
    if (value) {
	message("hardware scroll mode.\r\n");
    }
    return SUCCESS;
}

static	char	*videoName;

static int	ConfigDisplay(const char *config)
{
    struct videoconf *v;
    char name[MAX_COLS];
    
    sscanf(config, "%s", name);
    for (v = videos; v->name != NULL; v++) {
	if (strcasecmp(name, v->name) == 0) {
	    config = strchr(config, '\n');
	    if (config == NULL) {
		error("invalid entry for %s\r\n", videoName);
		return FAILURE;
	    }
	    if (v->set(&vInfo, config) == FAILURE)
		return FAILURE;
	    message("video type `%s' selected\r\n", name);
	    if (vInfo.has_hard_scroll) {
		DefineCap("HardScroll", ConfigHardScroll, "On");
	    } else
		useHardScroll = FALSE;
	    return SUCCESS;
	}
    }
    error("unknown video type `%s'\r\n", name);
    return FAILURE;
}

/* Beep routines. */

#define	COUNTER_ADDR	0x61

static int	beepCount;

static int	ConfigBeep(const char *confstr)
{
    beepCount = atoi(confstr) * 10000;
#if defined(linux)
    if (beepCount > 0)
	ioperm(COUNTER_ADDR, 1, TRUE);
#endif
    return SUCCESS;
}

void	Beep(void)
{
    if (!con.active || beepCount <= 0) return;
#if defined(linux)
    PortOutb(PortInb(COUNTER_ADDR)|3, COUNTER_ADDR);
    usleep(beepCount);
    PortOutb(PortInb(COUNTER_ADDR)&0xFC, COUNTER_ADDR);
#endif
}

static int	ConfigInterval(const char *confstr)
{
    cInfo.interval = atoi(confstr);
#ifndef	MINI_KON
    mouseCursor.interval = cInfo.interval;
#endif
    return SUCCESS;
}

static int	ConfigSaver(const char *confstr)
{
    saveTime = atoi(confstr) * 600; /* convert unit from minitue to 1/10 sec */
    return SUCCESS;
}

/* Initialize routine. */

void	ConsoleInit(const char *video)
{
    videoName = strdup(video);
    DefineCap(videoName, ConfigDisplay, NULL);
    DefineCap("BeepCounter", ConfigBeep, "5");
    DefineCap("CursorInterval", ConfigInterval, "4");
    DefineCap("SaveTime", ConfigSaver, "4");
}

void	ConsoleStart(void)
{
    /* What to do if calloc failed? */
    textBuff = (u_char *)calloc(dInfo.glineByte, dInfo.tymax + 1);
    attrBuff = (u_char *)calloc(dInfo.glineByte, dInfo.tymax + 1);
    flagBuff = (u_char *)calloc(dInfo.glineByte, dInfo.tymax + 1);
    textSize = dInfo.glineByte * (dInfo.tymax + 1);
    ioctl(0, KDSETMODE, KD_GRAPHICS);
    ioctl(0, TIOCGWINSZ, &text_win);
    vInfo.init();
    cInfo.shown = FALSE;
#ifndef	MINI_KON
    mouseCursor.shown = FALSE;
    mouseCursor.sw = TRUE;
#endif
    saved = FALSE;
    GraphMode();
}

void	ConsoleCleanup(void)
{
    scrollLine = textHead = 0;
    vInfo.detatch();
    SafeFree((void **)&textBuff);
    SafeFree((void **)&attrBuff);
    SafeFree((void **)&flagBuff);
#ifdef linux
    ioperm(COUNTER_ADDR, 1, FALSE);
#endif
    
    SafeFree((void **)&videoName);
}
