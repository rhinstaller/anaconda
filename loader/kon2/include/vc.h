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

/* vc -- high-level console driver */

#ifndef VC_H
#define VC_H

#define	ATTR_ULINE	0x80	/* under line */
#define	ATTR_REVERSE	0x40	/* reverse */
#define	ATTR_HIGH	0x20	/* high */

#define	LATCH_S		0x0 /* single byte char */
#define	LATCH_1		0x20 /* double byte char 1st byte */
#define	LATCH_2		0x40 /* double byte char 2nd byte */

#define	CLEAN_S		0x80
#define	CODEIS_1	LATCH_1
#define	CODEIS_2	LATCH_2
#define	LANG_CODE	0x0F
/*
#define	LANG_DCODE	LANG_CODE|CODEIS_1
#define	LANG_SCODE	LANG_CODE
*/

extern void	ConsoleInit(const char *video_type);
extern void	ConsoleStart(void);
extern void	ConsoleCleanup(void);
extern void	TextClearAll(void);
extern void	TextClearEol(u_char);
extern void	TextClearEos(u_char);
extern void	TextDeleteChar(int);
extern void	TextInsertChar(int);
extern void	TextMoveDown(int top, int btm, int line);
extern void	TextMoveUp(int top, int btm, int line);
extern void	TextMode(void);
extern void	GraphMode(void);
extern void	ScrollUp(int);
extern void	ScrollDown(int);
extern void	TextWput(u_char ch1, u_char ch2);
extern void	TextSput(u_char ch);
extern void	TextReverse(int fx, int fy, int tx, int ty);
extern void	TextRefresh(void);
extern void	TextInvalidate(void);
extern void	TextCopy(int fx, int fy, int tx, int ty);
extern void	TextPaste(void);
extern void	PollCursor(bool wakeup); /* Called to wakeup, or every 0.1 sec when idle */
extern void	Beep(void);

struct cursorInfo {
    short kanji;	 /* 漢字の上にあれば TRUE */
    u_int addr;		 /* VRAM アドレス */
    bool sw;		 /* FALSE なら表示禁止 */
    int	interval;	 /* 点滅間隔 */
    int	count;		 /* 点滅用カウント */
    bool shown;		 /* 表示中フラグ */
};

/* video driver interface */
struct videoInfo {
    bool
	has_hard_scroll;	 /* ハードスクロールが使えるかどうか */
    void
	(*init)(void),		 /* 初期化 */
	(*text_mode)(void),	 /* テキストモードに切替え */
	(*graph_mode)(void),	 /* グラフィックモードに切替え */
	(*wput)(u_char *code, u_char fc, u_char bc), /* 漢字出力 */
	(*sput)(u_char *code, u_char fc, u_char bc), /* ANK出力 */
	(*set_cursor_address)(struct cursorInfo *c, u_int x, u_int y),
	/* カーソル c のアドレスを (x,y) に設定 */
	(*set_address)(u_int i),
	/* 文字書き込みアドレスを i 文字目に設定 */
	(*cursor)(struct cursorInfo *),	/* カーソルをトグル */
	(*clear_all)(void),	 /* 画面クリア */
	(*screen_saver)(bool),	 /* スクリーンブランク/アンブランク */
	(*detatch)(void),	 /* ドライバ解放 */
	/* ハードスクロールが使えなければ以下はNULL */
	(*set_start_address)(void),	/* 表示開始アドレス設定 */
	(*hard_scroll_up)(int lines), 	/* ハードスクロールアップ */
	(*hard_scroll_down)(int lines);	/* ハードスクロールダウン */
};

struct dispInfo {
    int
	gsize;
    short
	gxdim,
	gydim,
	txmax,
	tymax,
	glineChar,	/* text １行分の graph 行数 */
	glineByte,	/* graph １行分のバイト数 */
	tlineByte;	/* text １行分のバイト数 */
};

extern struct dispInfo		dInfo;
extern struct cursorInfo	cInfo;
extern struct videoInfo		vInfo;

#endif
