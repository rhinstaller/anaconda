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

/* vt -- VT emulator */

#ifndef VT_H
#define VT_H

#include	<defs.h>
#include	<fnld.h>

struct _con_info {
    short
	x,
	y,
	xmax,	/* 79 */
	ymin,	/* 0:スクロール開始行 */
	ymax,	/* 29 */
	tab;	/* 8 */
    u_char
	fcol,	/* フォアグランド */
	bcol,	/* バックグランド */
	attr,	/* 文字属性 */
	sb,	/* 1 byte code フォント番号 */
	db,	/* 2 byte code フォント番号 */
	knj1;	/* 漢字キャラクタ第 1 byte */
    void (*esc)(u_char);
    enum {
	CS_LEFT,
	CS_RIGHT,
	CS_GRAPH,
	CS_DBCS} trans, g[2];
    enum {
	SL_NONE,
	SL_ENTER,
	SL_LEAVE} sl;
    bool
	soft,
	ins,
	active,
	wrap,
	text_mode;
};

extern struct	_con_info con;

#define	CODE_2022	0	/* 2022 のみに従う*/
#define	CODE_EUC	1	/* EUC にも従う */
#define	CODE_SJIS	2	/* SJIS にも従う */

#define	G0_SET	0
#define	G1_SET	0x80

extern void	VtInit(void);
extern void	VtStart(void);
extern void	VtEmu(const char*, int nchars);
extern void	VtCleanup(void);

#define	sjistojis(ch, cl)\
{\
    ch -= (ch > 0x9F) ? 0xB1: 0x71;\
    ch = ch * 2 + 1;\
    if (cl > 0x9E) {\
	cl = cl - 0x7E;\
	ch ++;\
    } else {\
	if (cl > 0x7E) cl --;\
	cl -= 0x1F;\
    }\
}

#define	jistosjis(ch, cl)\
{\
    if (ch & 1) cl = cl + (cl > 0x5F ? 0x20:0x1F);\
    else cl += 0x7E;\
    ch = ((ch - 0x21) >> 1) + 0x81;\
    if (ch > 0x9F) ch += 0x40;\
}

/*
  derived from Mule:codeconv.c to support "ESC $(0" sequence
  thanks to K.Handa <handa@etl.go.jp>
  */

#define muletobig5(type, m1, m2)\
{\
    unsigned code = (m1 - 0x21) * 94 + (m2 - 0x21);\
\
    if (type == DF_BIG5_1) code += 0x16F0;\
    m1 = code / 157 + 0xA1;\
    m2 = code % 157;\
    m2 += m2 < 0x3F ? 64 : 98;\
}

enum {
    DF_GB2312,
    DF_JISX0208,
    DF_KSC5601,
    DF_JISX0212,
    DF_BIG5_0,
    DF_BIG5_1
    };

#endif
