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
#include	<unistd.h>
#include	<string.h>
#include	<termios.h>
#if defined(linux)
#include	<malloc.h>
#elif defined(__FreeBSD__)
#include	<stdlib.h>
#endif
#include	<sys/types.h>
#include	<sys/ioctl.h>

#include	<getcap.h>
#include	<defs.h>
#include	<term.h>
#include	<interface.h>
#include	<fnld.h>
#include	<vt.h>
#include	<vc.h>

struct	_con_info con;

#define	CHAR_NUL	'\x00'
#define	CHAR_BEL	'\x07'
#define	CHAR_BS		'\x08'
#define	CHAR_HT		'\x09'
#define	CHAR_LF		'\x0A'
#define	CHAR_VT		'\x0B'
#define	CHAR_FF		'\x0C'
#define	CHAR_CR		'\x0D'
#define	CHAR_SO		'\x0E'
#define	CHAR_SI		'\x0F'
#define	CHAR_XON	'\x11'
#define	CHAR_XOFF	'\x12'
#define	CHAR_CAN	'\x18'
#define	CHAR_SUB	'\x1A'
#define	CHAR_ESC	'\x1B'
#define	CHAR_DEL	'\x7F'
#define	CHAR_CSI	'\x9B'
#define	CHAR_SS2	'\x8E'

#define	LEN_REPORT	9

struct attrStack {
    struct attrStack *prev;
    u_char x, y, attr, bcol, fcol;
};

static struct attrStack *saveAttr;

static int	scroll;			 /* スクロール行数 */
struct langInfo lInfo;

static void
SaveAttr(struct attrStack **asp)
{
    struct attrStack *tmp;

    tmp = (struct attrStack *)malloc(sizeof(struct attrStack));
    if (!asp) {
	if (saveAttr) tmp->prev = saveAttr;
	else tmp->prev = NULL;
	saveAttr = tmp;
    } else *asp = tmp;
    tmp->x = con.x;
    tmp->y = con.y;
    tmp->attr = con.attr;
    tmp->fcol = con.fcol;
    tmp->bcol = con.bcol;
}

static void
RestoreAttr(struct attrStack *asp)
{
    if (!asp) {
	if ((asp = saveAttr) == NULL) return;
	saveAttr = asp->prev;
    }
    con.x = asp->x;
    con.y = asp->y;
    if (con.y < con.ymin) con.y = con.ymin;
    if (con.y > con.ymax) con.y = con.ymax;
    con.attr = asp->attr;
    con.fcol = asp->fcol;
    con.bcol = asp->bcol;
    free(asp);
}

static void	EscSetAttr(int col)
{
    static u_char table[] = {0, 4, 2, 6, 1, 5, 3, 7};
    u_char	swp;

    switch(col) {
    case 0:	/* off all attributes */
	con.bcol = 0;
	con.fcol = 7;
	con.attr = 0;
	break;
    case 1:	/* highlight */
	con.attr |= ATTR_HIGH;
	if (con.fcol) con.fcol |= 8;
	break;
    case 21:
	con.attr &= ~ATTR_HIGH;
	con.fcol &= ~8;
	break;
    case 4:	/* 下線 */
	con.attr |= ATTR_ULINE;
	con.bcol |= 8;
	break;
    case 24:
	con.attr &= ~ATTR_ULINE;
	con.bcol &= ~8;
	break;
    case 7:	/* 反転 */
	if (!(con.attr & ATTR_REVERSE)) {
	    con.attr |= ATTR_REVERSE;
	    swp = con.fcol & 7;
	    if (con.attr & ATTR_ULINE) swp |= 8;
	    con.fcol = con.bcol & 7;
	    if (con.attr & ATTR_HIGH && con.fcol) con.fcol |= 8;
	    con.bcol = swp;
	}
	break;
    case 27:
	if (con.attr & ATTR_REVERSE) {
	    con.attr &= ~ATTR_REVERSE;
	    swp = con.fcol & 7;
	    if (con.attr & ATTR_ULINE) swp |= 8;
	    con.fcol = con.bcol & 7;
	    if (con.attr & ATTR_HIGH && con.fcol) con.fcol |= 8;
	    con.bcol = swp;
	}
	break;
    case 10:
	if (con.trans == CS_GRAPH) con.trans = CS_LEFT;
	break;
    case 11:
	con.trans = CS_GRAPH;
	break;
    default:
	if (col >= 30 && col <= 37) {
	    swp = table[col - 30];
	    if (con.attr & ATTR_REVERSE) {
		if (con.attr & ATTR_ULINE) swp |= 8;
		con.bcol = swp;
	    } else {
		if (con.attr & ATTR_HIGH) swp |= 8;
		con.fcol = swp;
	    }
	} else if (col >= 40 && col <= 47) {
	    swp = table[col - 40];
	    if (con.attr & ATTR_REVERSE) {
		if (con.attr & ATTR_HIGH) swp |= 8;
		con.fcol = swp;
	    } else {
		if (con.attr & ATTR_ULINE) swp |= 8;
		con.bcol = swp;
	    }
	}
	break;
    }
}

static void	VtSetMode(u_char mode, bool sw)
{
    switch(mode) {
    case 4:
	con.ins = sw;
	break;
    case 25:
	cInfo.sw = sw;
	break;
    }
}

static void
EscReport(u_char mode, u_short arg)
{
    static char report[LEN_REPORT];

    switch(mode) {
    case 'n':
	if (arg == 6) {
	    int x = (con.x < con.xmax) ? con.x : con.xmax;
	    int y = (con.y < con.ymax) ? con.y : con.ymax;
	    sprintf(report, "\x1B[%d;%dR", y + 1, x + 1);
	} else if (arg == 5)
	    strcpy(report, "\x1B[0n\0");
	break;
    case 'c':
	if (arg == 0) strcpy(report, "\x1B[?6c\0");
	break;
    }
    write(masterPty, report, strlen(report));
}

static void
SetRegion(int ymin, int ymax)
{
    con.ymin = ymin;
    con.ymax = ymax;
    con.x = 0;
    if (con.y < con.ymin || con.y > con.ymax) con.y = con.ymin;
    con.wrap = FALSE;
    if (con.ymin || con.ymax != dInfo.tymax)
	con.soft = TRUE;
    else
	con.soft = FALSE;
}

void
SetWinSize()
{
    struct winsize win;

    win.ws_row = con.ymax + 1;
    win.ws_col = dInfo.txmax + 1;
    win.ws_xpixel = win.ws_ypixel = 0;
    ioctl(masterPty, TIOCSWINSZ, &win);
}

static void
EscStatusLine(u_char mode)
{
    static void EscBracket(u_char);
    static struct attrStack *asp;

    switch(mode) {
    case 'T':	/* To */
	if (con.sl == SL_ENTER) break;
	if (!asp) SaveAttr(&asp);
    case 'S':	/* Show */
	if (con.sl == SL_NONE) {
	    con.ymax = dInfo.tymax - 1;
	    SetWinSize();
	}
	if (mode == 'T') {
	    con.sl = SL_ENTER;
	    SetRegion(dInfo.tymax, dInfo.tymax);
	}
	break;
    case 'F':	/* From */
	if (con.sl == SL_ENTER) {
	    con.sl = SL_LEAVE;
	    SetRegion(0, dInfo.tymax - 1);
	    if (asp) RestoreAttr(asp);
	    asp = NULL;
	}
	break;
    case 'H':	/* Hide */
    case 'E':	/* Erase */
	if (con.sl == SL_NONE) break;
	SetRegion(0, dInfo.tymax);
	SetWinSize();
	con.sl = SL_NONE;
	break;
    default:
	con.esc = EscBracket;
	EscBracket(mode);
	return;
    }
    con.wrap = FALSE;
    con.esc = NULL;
}

#define	MAX_NARG	8

static void
EscBracket(u_char ch)
{
    u_char	n;
    static u_short varg[MAX_NARG], narg, question;

    if (ch >= '0' && ch <= '9') {
	varg[narg] = (varg[narg] * 10) + (ch - '0');
    } else if (ch == ';') {
	/* 引数は MAX_NARG までしかサポートしない!! */
	if (narg < MAX_NARG) {
	    narg ++;
	    varg[narg] = 0;
	} else con.esc = NULL;
    } else {
	con.esc = NULL;
	switch(ch) {
	case 'K':
	    TextClearEol(varg[0]);
	    break;
	case 'J':
	    TextClearEos(varg[0]);
	    break;
	case 'A':
	    con.y -= varg[0] ? varg[0]: 1;
	    if (con.y < con.ymin) {
		scroll -= con.y - con.ymin;
		con.y = con.ymin;
	    }
	    break;
	case 'B':
	    con.y += varg[0] ? varg[0]: 1;
	    if (con.y > con.ymax) {
		scroll += con.y - con.ymin;
		con.y = con.ymax;
	    }
	    break;
	case 'C':
	    con.x += varg[0] ? varg[0]: 1;
	    con.wrap = FALSE;
	    break;
	case 'D':
	    con.x -= varg[0] ? varg[0]: 1;
	    con.wrap = FALSE;
	    break;
	case 'G':
	    con.x = varg[0] ? varg[0] - 1: 0;
	    con.wrap = FALSE;
	    break;
	case 'P':
	    TextDeleteChar(varg[0] ? varg[0]: 1);
	    break;
	case '@':
	    TextInsertChar(varg[0] ? varg[0]: 1);
	    break;
	case 'L':
	    TextMoveDown(con.y, con.ymax,
			 varg[0] ? varg[0] : 1);
	    break;
	case 'M':
	    TextMoveUp(con.y, con.ymax,
		       varg[0] ? varg[0] : 1);
	    break;
	case 'H':
	case 'f':
	    if (varg[1]) con.x = varg[1] - 1;
	    else con.x = 0;
	    con.wrap = FALSE;
	case 'd':
	    con.y = varg[0] ? varg[0] - 1: 0;
	    break;
	case 'm':
	    for (n = 0; n <= narg; n ++)
		EscSetAttr(varg[n]);
	    break;
	case 'r':
	    n = varg[1] ? (varg[1] - 1): dInfo.tymax;
	    if (con.sl != SL_NONE) {
		if (n == dInfo.tymax) n --;
	    }
	    SetRegion(varg[0] ? (varg[0] - 1): 0, n);
	    break;
	case 'l':
	    for (n = 0; n <= narg; n ++)
		VtSetMode(varg[n], FALSE);
	    break;
	case 'h':
	    for (n = 0; n <= narg; n ++)
		VtSetMode(varg[n], TRUE);
	    break;
	case '?':
	    con.esc = EscStatusLine;
#if 0
	    question = TRUE;
	    con.esc = EscBracket;
#endif
	    break;
	case 's':
	    SaveAttr(NULL);
	    break;
	case 'u':
	    RestoreAttr(NULL);
	    break;
	case 'n':
	case 'c':
	    if (question != TRUE)
		EscReport(ch, varg[0]);
	    break;
	case 'R':
	    break;
	}
	if (con.esc == NULL)
	    question = narg = varg[0] = varg[1] = 0;
    }
}

static
    void EscSetDCodeG0(u_char ch)
{
    int i;

    switch(ch) {
    case '(': /* EscSetDCodeG0 */
    case ')': /* EscSetDCodeG1 */
	return;
    case '@':
	ch = 'B';
    default:
	i = 0;
	while (fDRegs[i].sign0) {
#if 0
{FILE *fp=fopen("errlog", "a");
fprintf(fp,"[%d %c %s]\n", i, ch, fDRegs[i].registry);
fclose(fp);}
#endif
	    if (fDRegs[i].sign0 == ch) {
		con.db = (u_char)i|LATCH_1;
		break;
	    }
	    i ++;
	}
	con.trans = CS_DBCS;
	break;
    }
    con.esc = NULL;
}

static
    void EscSetSCodeG0(u_char ch)
{
    int i=0;

    switch(ch) {
    case '0':
	con.g[0] = CS_GRAPH;
	break;
    case 'U':
	con.g[0] = CS_GRAPH;
	break;
    default:
	while (fSRegs[i].sign0) {
	    if (fSRegs[i].sign0 == ch) {
		con.sb = (u_char)i;
		con.g[0] = CS_LEFT;
		break;
	    } else if (fSRegs[i].sign1 == ch) {
		con.sb = (u_char)i;
		con.g[0] = CS_RIGHT;
		break;
	    }
	    i ++;
	}
    }
    con.trans = con.g[0];
    con.esc = NULL;
}

static
    void EscSetSCodeG1(u_char ch)
{
    switch(ch) {
    case 'U':
	con.g[1] = CS_LEFT;
	break;
    case '0':
	con.g[1] = CS_GRAPH;
	break;
    case 'A':
    case 'J':
    case 'B':
	break;
    }
    con.trans = con.g[1];
    con.esc = NULL;
}

static
    void EscStart(u_char ch)
{
    con.esc = NULL;
    switch(ch) {
    case '[':
	con.esc = EscBracket;
	break;
    case '$':/* Set Double Byte Code */
	con.esc = EscSetDCodeG0;
	break;
    case '(':/* Set 94 to G0 */
    case ',':/* Set 96 to G0 */
	con.esc = EscSetSCodeG0;
	break;
    case ')':/* Set G1 */
	con.esc = EscSetSCodeG1;
	break;
    case 'E':
	con.x = 0;
	con.wrap = FALSE;
    case 'D':
	if (con.y == con.ymax) scroll ++;
	else con.y ++;
	break;
    case 'M':
	if (con.y == con.ymin) scroll --;
	else con.y --;
	break;	
    case 'c':
	con.fcol = 7;
	con.attr = 0;
	con.knj1 = con.bcol = 0;
	con.wrap = FALSE;
	con.trans = CS_LEFT;
	con.sb = lInfo.sb;
	con.db = lInfo.db|LATCH_1;
    case '*':
	con.x = con.y = 0;
	con.wrap = FALSE;
	TextClearAll();
	break;
    case '7':
	SaveAttr(NULL);
	break;
    case '8':
	RestoreAttr(NULL);
	con.wrap = FALSE;
	break;
    }
}

static inline
    bool iskanji(u_char c)
{
    switch(lInfo.sc) {
    case CODE_SJIS:
	return (c >=0x81 && c<=0x9F) || (c >=0xE0 && c <=0xFC);
    default:
	return (c & 0x80);
    }
}

void	VtEmu(const char *buff, int nchars)
{
    u_char	ch;

#if	0
    {
	FILE *fff;
	fff = fopen("esc.log", "a");
	fwrite(buff, nchars, 1, fff);
	fclose(fff);
    }
#endif

    while (nchars-- > 0) {
	ch = *buff;
	buff ++;
	if (! ch)
	    continue;
	if (con.esc) {
	    con.esc(ch);
	} else switch (ch) {
	case CHAR_BEL:
	    Beep();
	    break;
	case CHAR_DEL:
	    break;
	case CHAR_BS:
	    if (con.x) con.x --;
	    con.wrap = FALSE;
	    break;
	case CHAR_HT:
	    con.x += con.tab - (con.x % con.tab);
	    con.wrap = FALSE;
	    if (con.x > con.xmax) con.x -= con.xmax + 1;
	    else break;
	case CHAR_VT:
	case CHAR_FF:
#if 1
	    con.trans = CS_LEFT;
	    con.sb = lInfo.sb;
	    con.db = lInfo.db|LATCH_1;
#endif
	case CHAR_LF:
	    con.wrap = FALSE;
/*	    if (con.sl != SL_ENTER) {*/
		if (con.y == con.ymax) scroll ++;
		else con.y ++;
/*	    }*/
	    break;
	case CHAR_CR:
	    con.x = 0;
	    con.wrap = FALSE;
	    break;
	case CHAR_ESC:
	    con.esc = EscStart;
	    continue;
	case CHAR_SO:
	    con.trans = con.g[1] | G1_SET;
	    continue;
	case CHAR_SI:
	    con.trans = con.g[0];
	    continue;
/*	case ' ': con.trans = CS_LEFT;*/
	default:
	    if (con.x == con.xmax + 1) {
		con.wrap = TRUE;
		con.x --;
	    }
	    if (con.wrap) {
		con.x -= con.xmax;
/*		if (con.sl != SL_ENTER) {*/
		    if (con.y == con.ymax) scroll ++;
		    else con.y ++;
/*		}*/
		con.wrap = FALSE;
		buff --;
		nchars ++;
		break;
	    }
	    if (con.knj1) {
		/* 第 2 漢字モード */
		if (con.knj1 & 0x80) switch(lInfo.sc) {
		case CODE_EUC:
		    if (con.knj1 == (u_char)CHAR_SS2) {
			/* handling 'kata-kana' */
			if (con.ins) TextInsertChar(1);
			TextSput(ch);
			con.x ++;
			con.knj1 = 0;
			continue;
		    }
		    con.knj1 &= 0x7F;
		    ch &= 0x7F;
		    break;
		case CODE_SJIS:
		    sjistojis(con.knj1, ch);
		    break;
		} else {
		    if (con.db == (DF_BIG5_0|LATCH_1))
			muletobig5(con.db, con.knj1, ch);
		}
		if (con.ins) TextInsertChar(2);
		TextWput(con.knj1, ch);
		con.x += 2;
		con.knj1 = 0;
		continue;
	    } else if (con.trans == CS_DBCS
		       || (iskanji(ch) && con.trans == CS_LEFT)) {
		/* 第 1 漢字モード */
		if (con.x == con.xmax) con.wrap = TRUE;
		con.knj1 = ch;
		continue;
	    } else {
		/* ANK モード */
		if (con.ins) TextInsertChar(1);
		TextSput(con.trans == CS_RIGHT ? ch | 0x80: ch);
		con.x ++;
		continue;
	    }
	}
	if (scroll > 0) {
	    ScrollUp(scroll);
	} else if (scroll < 0) {
	    ScrollDown(- scroll);
	}
	scroll = 0;
    }
    if (con.x == con.xmax + 1) {
	con.wrap = TRUE;
	con.x --;
    }
}

static int	ConfigCoding(const char *confstr)
{
    char reg[3][MAX_COLS];
    int n, i;

    *reg[0] = *reg[1] = *reg[2] = '\0';
    sscanf(confstr, "%s %s %s", reg[0], reg[1], reg[2]);
    for (i = 0; i < 3 && *reg[i]; i ++) {
	n = (int)CodingByRegistry(reg[i]);
	if (n < 0) {
	    if (!strcasecmp(reg[i], "EUC"))
		lInfo.sc = CODE_EUC;
	    else if (!strcasecmp(reg[i], "SJIS"))
		lInfo.sc = CODE_SJIS;
/*
	    else if (!strcasecmp(reg[i], "BIG5"))
		lInfo.sc = CODE_BIG5;
*/
	    else
		lInfo.sc = 0;
	} else if (n & CHR_DBC)
	    lInfo.db = n & ~CHR_DFLD;
	else
	    lInfo.sb = n & ~CHR_SFLD;
#if 0
{FILE *fp=fopen("errlog", "a");
fprintf(fp,"[<%s> %d %d %d %d]\n", reg[i], n, lInfo.sb, lInfo.db, lInfo.sc);
fclose(fp);}
#endif
    }
    return SUCCESS;
}

void	VtInit(void)
{
    con.text_mode = TRUE;
    DefineCap("Coding", ConfigCoding,
	      "JISX0201.1976-0 JISX0208.1983-0 EUCJ"); 
}

void	VtStart(void)
{
    /* xmax, ymax は kon.cfg を読んだ後でないと分からない。*/
    con.x = con.y = 0;
    con.xmax = dInfo.txmax;
    con.ymax = dInfo.tymax;
    con.tab = 8;
    con.fcol = 7;
    con.attr = 0;
    con.esc = NULL;
    con.g[0] = con.g[1] = CS_LEFT;
    con.trans = con.soft = con.ins = con.wrap = FALSE;
    con.sb = lInfo.sb;
    con.db = lInfo.db|LATCH_1;
    con.active = cInfo.sw = TRUE;
}
