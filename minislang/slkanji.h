/*	-*- mode: C; mode: fold -*- */
/* slkanji.h --- Interface To use Japanese 2byte KANJI code 
 * Copyright (c) 1995, 2000 Kazuhisa Yoshino(k-yosino@actweb.ne.jp)
 * This file is part of the Japanized S-Lang library.
 * 
 * You may distribute under the terms of either the GNU General Public
 * License or the Perl Artistic License.
 */


/* Added by H.Nishizuka */
#ifndef TRUE
#define TRUE (-1)
#endif
#ifndef FALSE
#define FALSE (0)
#endif

#define issjiskanji(c)	((0x81 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0x9f)	\
			|| (0xe0 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0xfc))
#define iseuckanji(c)	(0xa1 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0xfe)
#define isjiskanji(c)	(0x21 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0x7e)
#define ishkana(c)	(0xa0 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0xdf)
#ifdef iskanji
# undef iskanji
#endif
#define iskanji(c)	IsKanji(c,kSLcode)

#define	SS2	0x8E			/* for EUC  kana (Single Shift JIS-X0201kana)*/
#define	ESC	0x1b

#define	NON	0
#define	NOKANJI	0
#define ASCII	0
#define	EUC	1
#define	JIS	2
#define	SJIS	3
#define	BINARY	4

#ifndef IBMPC_SYSTEM
# define SLANG_DEFAULT_KANJI_CODE EUC
#else
# define SLANG_DEFAULT_KANJI_CODE SJIS
#endif
# define KANJI_DEFAULT_CODE SLANG_DEFAULT_KANJI_CODE

#ifndef NULL
#define NULL 0
#endif

extern char *Kcode[];
extern int	kSLfiAuto, SKanaToDKana;
extern int	kSLcode;
extern int	kSLfile_code, kSLinput_code, kSLdisplay_code, kSLsystem_code;
extern int	DetectLevel;
extern int IsKanji(int, int);
extern int kanji_pos(unsigned char *, unsigned char *);
extern int short_kanji_pos(unsigned short *, unsigned short *);
#define kanji_pos2 short_kanji_pos
extern int iskanji2nd(char *, int);
extern char *kcode_to_str(int);
extern int str_to_kcode(char *);
#ifdef REAL_UNIX_SYSTEM
extern int Stricmp(char *, char *);
#else
#define Stricmp	stricmp
#endif
extern void sjistojis(char *, char *);
extern void jistosjis(char *, char *);
extern void euctosjis(char *, char *);
extern void sjistoeuc(char *, char *);
extern void euctojis(char *, char *);
extern void jistoeuc(char *, char *);
extern void notconv(char *, char *);
#define NCODE 4
extern void (*kSLcodeconv[NCODE][NCODE])();
#if 0
extern void	kSLset_kanji_filecode(int *);
extern void	kSLset_kanji_inputcode(int *);
extern void	kSLset_kanji_displaycode(int *);
extern void	kSLset_kanji_systemcode(int *);
extern void	set_kanji_kSLcode(int *);
extern int	kSLget_kanji_filecode(void);
extern int	kSLget_kanji_inputcode(void);
extern int	kSLget_kanji_displaycode(void);
extern char	*get_kanji_systemcode(void);
extern char	*get_kanji_kSLcode(void);
#if 0
extern char	get_1st_kanji_filecode(void);
extern char	get_1st_kanji_inputcode(void);
extern char	get_1st_kanji_displaycode(void);
extern char	get_1st_kanji_systemcode(void);
extern char	get_1st_kanji_jedcode(void);
#endif
extern void	kSLrot_kanji_filecode(void);
extern void	kSLrot_kanji_inputcode(void);
extern void	kSLrot_kanji_displaycode(void);
extern void	kSLrot_kanji_systemcode(void);
#endif
extern char	*file_kanji_autocode(char *);
extern void	han_to_zen(int *);
extern void	han2zen(unsigned char *, unsigned char *, int *, int *, int);

extern int	kSLis_kanji_code(void);
extern int	kcode_detect(char *);
extern int	IsKcode(unsigned char *, int, int *);
extern int	kSLinit_kanji(void);
/* compatible for old version */
#define init_SLKanji kSLinit_kanji
extern int	kSLCheckLineNum(unsigned char *, int, int, int, int);
extern unsigned char * kSLCodeConv(unsigned char *, int *, int, int, int);
extern unsigned int kSLsys_getkey(void);

