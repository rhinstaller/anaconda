/*	-*- mode: C; mode: fold -*- */
/* slkanji.c --- Interface To use Japanese 2byte KANJI code 
 * Copyright (c) 1995, 2000 Kazuhisa Yoshino(k-yosino@actweb.ne.jp)
 * This file is part of the Japanized S-Lang library.
 * 
 * You may distribute under the terms of either the GNU General Public
 * License or the Perl Artistic License.
 */

#include	<stdio.h>
#include	<ctype.h>
#include	"config.h"
#include	"slang.h"
#include	<fcntl.h>

#include	"slang.h"
#include	"_slang.h"
#include	"slkanji.h"

static char *Kcode[] = {
			"Ascii",
			"Euc",
			"Jis",
			"Sjis",
/*			"Binary", */
/* 			"SLang", */
			NULL };

#if 1
struct _kSLcode_data	/* Extended EUC */
{
   unsigned char *name;
   char *pre_str;	/* previous string(escape sequence). If this value unset, code data output... */
   unsigned char *func_name;
/*   unsigned char *(*convert_func)(); */	/* argument is 1? (or 2?). */
   int lenth;		/* character byte length */
   int width;		/* character width */
   int mode;		/* 0: after here. 1: next word(1*lenth) only. */
/*   int enable; */         /* enable/disable */
} *current_set=(struct _kSLcode_data *)NULL, kSLcode_data[0x20] =
{
   /* 0x80 */     {"",NULL,NULL,1,1,1},
   /* 0x81 */     {"jisx0201", "\x1b(B", NULL, 1, 1, 0},
   /* 0x82 */     {0,0,0,0,0,0},
   /* 0x83 */     {0,0,0,0,0,0},
   /* 0x84 */     {0,0,0,0,0,0},
   /* 0x85 */     {0,0,0,0,0,0},
   /* 0x86 */     {0,0,0,0,0,0},
   /* 0x87 */     {0,0,0,0,0,0},
   /* 0x88 */     {0,0,0,0,0,0},
   /* 0x89 */     {0,0,0,0,0,0},
   /* 0x8a */     {0,0,0,0,0,0},
   /* 0x8b */     {0,0,0,0,0,0},
   /* 0x8c */     {0,0,0,0,0,0},
   /* 0x8d */     {0,0,0,0,0,0},
   /* 0x8e */     {"euc-jp-ss2", NULL, NULL, 1, 1, 1},
   /* 0x8f */     {"euc-jp-ss3", NULL,NULL, 2,2,1},
   /* 0x90 */     {"jisx0208-1983", "\x1b$B", NULL, 2, 2, 0},
   /* 0x91 */     {"jisx0208-1978", "\x1b$@", NULL, 2, 2, 0},
   /* 0x92 */     {0,0,0,0,0,0},
   /* 0x93 */     {0,0,0,0,0,0},
   /* 0x94 */     {0,0,0,0,0,0},
   /* 0x95 */     {0,0,0,0,0,0},
   /* 0x96 */     {0,0,0,0,0,0},
   /* 0x97 */     {0,0,0,0,0,0},
   /* 0x98 */     {0,0,0,0,0,0},
   /* 0x99 */     {0,0,0,0,0,0},
   /* 0x9a */     {0,0,0,0,0,0},
   /* 0x9b */     {0,0,0,0,0,0},
   /* 0x9c */     {0,0,0,0,0,0},
   /* 0x9d */     {0,0,0,0,0,0},
   /* 0x9e */     {"extended",NULL,NULL,-1,-1,-1},
   /* 0x9f */     {"extended",NULL,NULL,-1,-1,-1}
};

int kSLset_code_data(unsigned char *name, char *pre, unsigned char *func, int len, int mod)
{
   int i, n;
   
   for (i=0 ; i<32 ; i++)
     {
	if (kSLcode_data[i].name == NULL && kSLcode_data[i].pre_str == NULL)
	  break;
     }
   if(i == 32) return -1;	/* kSLcode_data table is full */
   kSLcode_data[i].name = (unsigned char*)SLmalloc(strlen(name)+1);
   strcpy(kSLcode_data[i].name, name);
   kSLcode_data[i].pre_str = (char*)SLmalloc(strlen(pre)+1);
   strcpy(kSLcode_data[i].pre_str, pre);
   kSLcode_data[i].func_name = (char*)SLmalloc(strlen(func)+1);
   strcpy(kSLcode_data[i].func_name, func);
   kSLcode_data[i].lenth = len;
   kSLcode_data[i].mode = mod;
   
   return i;
}

int kSLfind_code_data(unsigned char *name, char *pre)
{
   int i, n;
   
   for (i=0 ; i<0x20 ; i++)
     {
	if((name && !strcmp(name, kSLcode_data[i].name))
	   || (pre && !strcmp(pre, kSLcode_data[i].pre_str)))
	  return i;
     }
   return -1;
}

#if 0
void kSLget_code_data_member(int i)
{
   
   SLang_push_string(kSLcode_data[i].name);
   SLang_push_string(kSLcode_data[i].pre_str);
   SLang_push_string(kSLcode_data[i].func_name);
   SLang_push_integer(kSLcode_data[i].lenth);
   SLang_push_integer(kSLcode_data[i].mode);

}
#endif

/*
int convert_function(void (unsigned char *buf, int bufsize, *get_func)(void))
{
   
   
}
*/

int kSLstrlen(unsigned char *str)
{
   register int len, n=0;
   register unsigned char *p = str;
   
   if (!p) return 0;
   while (*p)
     {
	if ((0x80 & *p) && (*p < 0xa0))			/* 0x80 <= *p < 0xa0 */
	  {
	     len = kSLcode_data[*p & 0x7f].lenth;	/* kSLcode_data[*p - 0x80] */
	     n += len;
	     p += len;
	  }
	else
	  n++;
	
	p++;
     }
   
   return n;
}

#endif

int	kSLcode = SLANG_DEFAULT_KANJI_CODE;
int	kSLfile_code = SLANG_DEFAULT_KANJI_CODE, kSLinput_code = SLANG_DEFAULT_KANJI_CODE,
	kSLdisplay_code = SLANG_DEFAULT_KANJI_CODE, kSLsystem_code = SLANG_DEFAULT_KANJI_CODE;

#ifdef IBMPC_SYSTEM
int	kSLfiAuto = FALSE,
	SKanaToDKana = FALSE;
#else
int	kSLfiAuto = TRUE,
	SKanaToDKana = TRUE;
#endif

int jp_nokanji = NOKANJI;
int ascii = ASCII;
int jp_euc = EUC;
int jp_jis = JIS;
int jp_sjis = SJIS;
int val_true = TRUE;
int val_false = FALSE;


int IsKanji(int c, int code) /*{{{*/
{
/*   if(!code) return FALSE; */
   c = (c & 0xff);
   if(code == SJIS)
     {
	if((0x80 < c && c < 0xa0) || (0xe0 <= c && c <= 0xfc))
	  return	TRUE;
     }
   else if(code == EUC)
     {
	if(0xa0 < c && c < 0xff)
	  return	TRUE;
	if(c == 0x8e) return TRUE;	/* fake */
     }
    else if(code == JIS)
     {
	if(0x20 < c && c < 0x7f)
	  return	TRUE;
     }
   return	FALSE;
}

/*}}}*/

int kSLiskanji(int *n) /*{{{*/
{
   return (IsKanji(*n, kSLcode));
}

/*}}}*/

/* 
 * distinguish KANJI code of pointed position in string
 * argment:
 * 	beg: begin of string
 * 	pos: position of string
 * return:
 * 	0: ASCII
 * 	1: KANJI 1st byte
 * 	2: KANJI 2nd byte
 */

int kanji_pos(unsigned char *beg, unsigned char *pos) /*{{{*/
{
   int ret = 0;
   unsigned char *p = beg;

   if((beg == pos) || !iskanji(*(pos-1)))
     {
	if (iskanji(*pos))
	  return 1;	/* KNAJI 1st byte */
	else
	  return ASCII;	/* ASCII: 0 */
     }

   while(p < pos)
     {
	if (iskanji(*p))	p++;
	p++;
     }
   
   if(p != pos)	return (p - pos +1);
   if(iskanji(*p))	return 1;
   
   return ASCII;
}

/*}}}*/


#define CHAR_MASK	0x000000FF

int short_kanji_pos(unsigned short *beg, unsigned short *pos) /*{{{*/
{
   int ret = 0;
   unsigned short *p = beg;

   if((beg == pos) || !iskanji(*(pos-1) & CHAR_MASK))
     {
	if (iskanji(*pos & CHAR_MASK))
	  return 1;	/* KNAJI 1st byte */
	else
	  return ASCII;	/* ASCII: 0 */
     }

   while(p < pos)
     {
	if (iskanji(*p & CHAR_MASK))	p++;
	p++;
     }
   
   if (p != pos)	return ((p - pos) +1);
   if (iskanji(*p & CHAR_MASK))	return 1;
   
   return ASCII;
}

/*}}}*/

int iskanji2nd(char *str, int col)
{
   int	j;

   if(!col || !iskanji(str[col-1]))	return FALSE;

   for( j=0 ; j < col ; j++ )
     {
	if (iskanji(str[j]))	j++;
     }
   if( j == col )	return FALSE;
   else		return TRUE;
}

char *kcode_to_str(int n)
{
   int i=0;
   while(Kcode[i])
     {
	if(i == n)	 return	Kcode[n];
	i++;
     }
   return	Kcode[ASCII];
}

#ifdef REAL_UNIX_SYSTEM
int Stricmp(char *src, char *dst)
{

   while(*src)
     {
	if(toupper(*src) != toupper(*dst))
	  return	(toupper(*src) - toupper(*dst));
	src++;
	dst++;
     }
   return	0;
}
#endif


int str_to_kcode(char *s)
{
   int	i;
   for(i=0 ; Kcode[i] ; i++)
     {
	if(!Stricmp(Kcode[i], s))	return	i;
     }

   return (int)NULL;
}

void sjistojis(char *src, char *dst)
{
#if 1
   sjistoeuc(src, dst);
   *dst++ &= 0x7f;
   *dst &= 0x7f;
#else
   unsigned int	high;
   unsigned int	low;

   high = *src & 0xff;
   low = *(src+1) & 0xff;
   if (high <= 0x9f)
     high -= 0x71;
   else
     high -= 0xb1;
   high = high * 2 + 1;
   if (low > 0x7f)
     low--;
   if (low >= 0x9e)
     {
	low -= 0x7d;
	high++;
     }
   else
     {
	low -= 0x1f;
     }
   *dst = (char)(high & 0x7f);
   *(dst+1) = (char)(low & 0x7f);
#endif
}

void jistosjis(char *src, char *dst)
{
   int	high;
   int	low;
	
   high = *src & 0x7f;
   low = *(src+1) & 0x7f;
   if (high & 1)
     low += 0x1f;
   else
     low += 0x7d;
   if (low >= 0x7f)
     low++;
   high = ((high - 0x21) >> 1) + 0x81;
   if (high > 0x9f)
     high += 0x40;

   *dst = (char)high;
   *(dst+1) = (char)low;
}

void euctosjis(char *src, char *dst)
{
#if 1
   euctojis(src, dst);
   jistosjis(dst, dst);
#else
   int	high;
   int	low;
	
   high = (*src & 0x7f);
   low = (*(src+1) & 0x7f);
   if (high & 1)
     low += 0x1f;
   else
     low += 0x7d;
   if (low >= 0x7f)
     low++;
   high = ((high - 0x21) >> 1) + 0x81;
   if (high > 0x9f)
     high += 0x40;

   *dst = (char)high;
   *(dst+1) = (char)low;
#endif
}

void sjistoeuc(char *src, char *dst)
{
   unsigned int	high;
   unsigned int	low;
	
   high = *src & 0xff;
   low = *(src+1) & 0xff;
   if (high <= 0x9f)
     high -= 0x71;
   else
     high -= 0xb1;
   high = high * 2 + 1;
   if (low > 0x7f)
     low--;
   if (low >= 0x9e)
     {
	low -= 0x7d;
	high++;
     }
   else
     {
	low -= 0x1f;
     }
   
   *dst = (char)(high | 0x80);
   *(dst+1) = (char)(low | 0x80);
}

void euctojis(char *src, char *dst)
{
   *dst = *src & 0x7f;
   *(dst+1) = *(src+1) & 0x7f;
}

void jistoeuc(char *src, char *dst)
{
   *dst = (*src | 0x80);
   *(dst+1) = (*(src+1) | 0x80);
}

void notconv(char *src, char *dst)
{
   *dst = *src;
   *(dst+1) = *(src+1);
}

void (*kSLcodeconv[NCODE][NCODE])() =
	{{notconv, notconv, notconv, notconv},
	 {notconv, notconv, euctojis, euctosjis},
	 {notconv, jistoeuc, notconv, jistosjis},
	 {notconv, sjistoeuc, sjistojis, notconv}};

void displaycode_to_SLang(char *src, char *dst)
{
   int in = kSLdisplay_code, out = kSLcode;
   
   if (in < 0 || NCODE <= in) in = ASCII;
   if (out < 0 || NCODE <= out) out = ASCII;
   kSLcodeconv[in][out](src, dst);
}

#define	ISMARU(c)	(0xca <= (c & 0xff) && (c & 0xff) <= 0xce)
#define ISNIGORI(c)	((0xb6 <= (c & 0xff) && (c & 0xff) <= 0xc4)\
			|| (0xca <= (c & 0xff) && (c & 0xff) <= 0xce)\
			|| (0xb3 == (c & 0xff)))
void han2zen(in, out, lin, lout, code) /*{{{*/
unsigned char	*in, *out;
int	*lin, *lout, code;
{
   int	maru = FALSE, nigori = FALSE;
   unsigned char	ch1, ch2 = '\0';
   int	mtable[][2] = {
	{129,66},{129,117},{129,118},{129,65},{129,69},{131,146},{131,64},{131,66},
	{131,68},{131,70},{131,72},{131,131},{131,133},{131,135},{131,98},{129,91},
	{131,65},{131,67},{131,69},{131,71},{131,73},{131,74},{131,76},{131,78},
	{131,80},{131,82},{131,84},{131,86},{131,88},{131,90},{131,92},{131,94},
	{131,96},{131,99},{131,101},{131,103},{131,105},{131,106},{131,107},{131,108},
	{131,109},{131,110},{131,113},{131,116},{131,119},{131,122},{131,125},{131,126},
	{131,128},{131,129},{131,130},{131,132},{131,134},{131,136},{131,137},{131,138},
	{131,139},{131,140},{131,141},{131,143},{131,147},{129,74},{129,75}
   };

   if(code == EUC)
     {
	ch1 = in[1];
	if (SKanaToDKana <= 0)
	  if (in[2] == SS2) ch2 = in[3];
     }
   else if(code == JIS)
     {
	ch1 = (in[0] | 0x80);
	ch2 = (in[1] | 0x80);
     }
   else
     {
	ch1 = in[0];
	ch2 = in[1];
     }

   if( ch1 == 0xa0 )
     {
	out[0] = ' ';
	out[1] = '\0';
	*lin = *lout = 1;
	if(code == EUC)	*lin = 2;
     }
   else
     {
	if (SKanaToDKana <= 0)
	  {
	     if(ch2 == 0xde && ISNIGORI(ch1))
	       nigori = TRUE;
	     else if(ch2 == 0xdf && ISMARU(ch1))
	       maru = TRUE;
	  }

	out[0] = mtable[ch1 - 0xa1][0];
	out[1] = mtable[ch1 - 0xa1][1];
	if(nigori)
	  {
	     if((0x4a <= out[1] && out[1] <= 0x67) || (0x6e <= out[1] && out[1] <= 0x7a))
	       out[1]++;
	     else if(out[0] == 0x83 && out[1] == 0x45)
	       out[1] = 0x94;
	  }
	else if(maru && 0x6e <= out[1] && out[1] <= 0x7a)
	  out[1] += 2;

	if(nigori || maru)	*lin = 2;
	else			*lin = 1;
	if(code == EUC)	*lin *= 2;
	*lout = 2;
     }
}

 /*}}}*/

/*
 *	Not check, if src[n-1] is KANJI first byte, or if src[n-1] is in JIS ESC sequence,
 *	it return more bigger number.	understand?
 *
 *	if you want change "src" string from Kanji *incode to Kanji *outcode,
 *	this function return to need byte for Code Convert.
 *
 * 	htoz:  hankaku to zenkaku flag (TRUE or FALSE)
 */
int kSLCheckLineNum(unsigned char *src, int n, int incode, int outcode, int htoz)
{
   int	i, siz=0;
   int	kflg = FALSE, hflg = FALSE;
   int	okflg = FALSE, ohflg = FALSE;
   
   for (i=0 ; i<n ; )
     {
	if (incode == JIS && src[i] == ESC )
	  {
	     if (src[i+1] == '$')
	       {
		  if ((src[i+2] == '@') || (src[i+2] == 'B'))
		    {
		       i += 3;
		       kflg = TRUE;
		       hflg = FALSE;
		    }
		  else
		    {
		       i += 2;
		       siz += 2;
		    }
	       }
	     else if (src[i+1] == '(')
	       {
		  if ((src[i+2] == 'J') || (src[i+2] == 'B') || (src[i+2] == 'H'))
		    {
		       i += 3;
		       kflg = hflg = FALSE;
		    }
		  else if (src[i+2] == 'I')
		    {
		       i += 3;
		       kflg = FALSE;
		       hflg = TRUE;
		    }
		  else
		    {
		       i += 2;
		       siz += 2;
		    }
	       }
	     else
	       {
		  i++;
		  siz++;
	       }
	  }
	else if ((incode == JIS && kflg && isjiskanji(src[i]))
		|| (incode == EUC && iseuckanji(src[i]))
		|| (incode == SJIS && issjiskanji(src[i])))
	  {
	     i += 2;
	     siz += 2;
	     if (outcode == JIS && !okflg)
	       {
		  siz += 3;
		  okflg = TRUE;
		  ohflg = FALSE;
	       }
	  }
	else if ((incode == JIS && hflg) || (incode == EUC && src[i] == SS2)
		|| (incode == SJIS && ishkana(src[i])))
	  {
	     if (htoz)
	       {
		  int	sc, dc;
		  unsigned char p[2];
		  
		  /* But &dst[o] is only SJIS code */
		  han2zen(&src[i], p, &sc, &dc, incode);
		  i += sc;
		  siz += dc;
		  if (outcode == JIS && !okflg)
		    {
		       siz += 3;
		       okflg = TRUE;
		       ohflg = FALSE;
		    }
	       }
	     else
	       {
		  i++; siz++;
		  if (incode == EUC)	i++;
		  if (outcode == EUC)	siz++;
		  if (outcode == JIS && !ohflg)
		    {
		       siz += 3;
		       okflg = FALSE;
		       ohflg = TRUE;
		    }
	       }
	  }
	else
	  {
	     i++;
	     siz++;
	     if (outcode == JIS && (okflg || ohflg))
	       {
		  siz += 3;
		  okflg = ohflg = FALSE;
	       }
	  }
     }

   if (outcode == JIS && (okflg || ohflg))
     {
	siz += 3;
	okflg = ohflg = FALSE;
     }
   
   return siz;
}


unsigned char * kSLCodeConv(unsigned char *src, int *siz, int incode, int outcode, int KanaChgFlag) /*{{{*/
{
   int	dstsiz;
   unsigned char	*dst, tmp[2];
   static int	kflg = FALSE, hflg = FALSE;
   static int	okflg = FALSE, ohflg = FALSE;
   int		i, o;
   void	(*kcodeto)(char *, char *);
   void	(*kanakcodeto)(char *, char *);
   char	*jiskanji = "\033$B",
	*jiskana = "\033(I",
	*jisascii = "\033(B";
   static char kanji_char[2] = {'\0', '\0'};	/* If last charctor of "src" string is KANJI 1st byte,
						 * it charctor(KANJI 1st byte) is set this variable.
						 * 
						 * And, if last charctor of "src" is KANJI 1st byte
						 * when it used to be this function,
						 * you must set to this variable.
						 */

   if (incode < 0 || NCODE <= incode) incode = ASCII;
   if (outcode < 0 || NCODE <= outcode) outcode = ASCII;

   if (!kSLcode || (incode == ASCII) || (outcode == ASCII) || !src) return src;
   else if (incode == outcode)
     {
	if (KanaChgFlag == FALSE) return src;
     }
   kcodeto = kSLcodeconv[incode][outcode];
   kanakcodeto = kSLcodeconv[SJIS][outcode];
   
   dstsiz = kSLCheckLineNum (src, *siz, incode, outcode, KanaChgFlag);
   if (kanji_char[0])
     {
	dstsiz++;
	if (outcode == JIS) dstsiz += 3;
     }
   if ((dst = (unsigned char*)SLmalloc(dstsiz + 1)) == NULL)
     {
	/* error message */
	return	src;
     }

   for (i=0,o=0 ; i<*siz ; )
     {
	if (incode == JIS && src[i] == ESC )
	  {
	     if (src[i+1] == '$')
	       {
		  if ((src[i+2] == '@') || (src[i+2] == 'B'))
		    {
		       i += 3;
		       kflg = TRUE;
		       hflg = FALSE;
		    }
		  else
		    {
		       dst[o++] = src[i++];
		    }
	       }
	     else if (src[i+1] == '(')
	       {
		  if ((src[i+2] == 'J') || (src[i+2] == 'B'))
		    {
		       i += 3;
		       kflg = hflg = FALSE;
		    }
		  else if (src[i+2] == 'I')
		    {
		       i += 3;
		       kflg = FALSE;
		       hflg = TRUE;
		    }
		  else {
		     dst[o++] = src[i++];
		  }
	       }
	     else
	       {
		  dst[o++] = src[i++];
	       }
	  }
	else if ((incode == JIS && kflg && isjiskanji(src[i]))
		 || (incode == EUC && iseuckanji(src[i]))
		 || (incode == SJIS && issjiskanji(src[i])) || kanji_char[0])
	  {
	     if (i == (*siz -1) && !kanji_char[0])
	       {
		  kanji_char[0] = src[i];
		  i++;
	       }
	     else
	       {
		  if (outcode == JIS && !okflg)
		    {
		       strcpy (&dst[o], jiskanji);
		       o += strlen (jiskanji);
		       okflg = TRUE;
		       ohflg = FALSE;
		    }
		  if (kanji_char[0])
		    {
		       kanji_char[1] = src[i];
		       kcodeto(kanji_char, &dst[o]);
		       kanji_char[0] = '\0';
		       i--;
		    }
		  else
		    kcodeto (&src[i], &dst[o]);
		  i += 2;
		  o += 2;
	       }
	  }
	else if ((incode == JIS && hflg) || (incode == EUC && src[i] == SS2)
		 || (incode == SJIS && ishkana(src[i])))
	  {
	     if (KanaChgFlag)
	       {
		  int	sc, dc;

		  if (outcode == JIS && !okflg)
		    {
		       strcpy (&dst[o], jiskanji);
		       o += strlen (jiskanji);
		       okflg = TRUE;
		       ohflg = FALSE;
		    }
		  /* But &dst[o] is only SJIS code */
		  han2zen (&src[i], &dst[o], &sc, &dc, incode);
		  kanakcodeto (&dst[o], &dst[o]);
		  i += sc;
		  o += dc;
	       }
	     else
	       {
		  if (outcode == JIS && !ohflg)
		    {
		       strcpy (&dst[o], jiskana);
		       o += strlen (jiskana);
		       okflg = FALSE;
		       ohflg = TRUE;
		    }
		  if (incode == EUC)	i++;
		  if (outcode == EUC)	dst[o++] = SS2;
		  dst[o] = src[i];
		  if (outcode == JIS)	dst[o] &= 0x7f;
		  else			dst[o] |= 0x80;
		  i++; o++;
	       }
	  }
	else
	  {
	     if (outcode == JIS && (okflg || ohflg))
	       {
		  strcpy (&dst[o], jisascii);
		  o += strlen (jisascii);
		  okflg = ohflg = FALSE;
	       }
	     dst[o++] = src[i++];
	  }
     }

   if (outcode == JIS && (okflg || ohflg))
     {
	strcpy (&dst[o], jisascii);
	o += strlen (jisascii);
	okflg = ohflg = FALSE;
     }

   dst[o] = '\0';
   *siz = o;

   return dst;
}

 /*}}}*/

#if 0
void kSLset_kanji_filecode(int *n)
{
   kSLfile_code = *n;
}

void kSLrot_kanji_filecode()
{
   kSLfile_code++;
   if(BINARY < kSLfile_code)	kSLfile_code = ASCII;
}

int	kSLget_kanji_filecode()
{
	return	kSLfile_code;
}
#if 0
char	get_1st_kanji_filecode()
{
	return	*Kcode[kSLfile_code];
}
#endif

void	kSLset_kanji_inputcode(int *n)
{
	kSLinput_code = *n;
}

void	kSLrot_kanji_inputcode()
{
	kSLinput_code++;
	if(SJIS < kSLinput_code)	kSLinput_code = ASCII;
}

int	kSLget_kanji_inputcode()
{
	return	kSLinput_code;
}

#if 0
char	get_1st_kanji_inputcode()
{
	return	*Kcode[kSLinput_code];
}
#endif

void	kSLset_kanji_displaycode(int *n)
{
	kSLdisplay_code = *n;
}

void	kSLrot_kanji_displaycode()
{
	kSLdisplay_code++;
	if(BINARY < kSLdisplay_code)	kSLdisplay_code = ASCII;
}

int	kSLget_kanji_displaycode()
{
	return	kSLdisplay_code;
}
#if 0
char	get_1st_kanji_displaycode()
{
	return	*Kcode[kSLdisplay_code];
}
#endif

void	kSLset_kanji_systemcode(int *n)
{
	jscode = *n;
}

#if 0
void	kSLrot_kanji_systemcode()
{
	jscode++;
	if(SJIS < jscode)	jscode = ASCII;
}

char	*get_kanji_systemcode()
{
	return	Kcode[jscode];
}
#if 0
char	get_1st_kanji_systemcode()
{
	return	*Kcode[jscode];
}
#endif
#endif
#endif

void	set_kanji_kSLcode(int *n)
{
   kSLcode = *n;
   if(kSLis_kanji_code() == FALSE)	kSLcode = ASCII;

}

#if 0
void	rot_kanji_kSLcode()
{
	kSLcode++;
	if(kSLis_kanji_code() == FALSE)	kSLcode = ASCII;
}
#endif

char	*get_kanji_kSLcode(void)
{
   return	Kcode[kSLcode];
}

#if 0
char	get_1st_kanji_jedcode()
{
	return	*Kcode[kSLcode];
}
#endif

int	kSLis_kanji_code(void)
{
   if(kSLcode == EUC || /* kSLcode == JIS || */ kSLcode == SJIS)
     return	TRUE;
   else
     return	FALSE;
}

char	*file_kanji_autocode(char *fname)
{
   return	Kcode[kSLfile_code];
}

/*	i: TRUE or FALSE */
void	han_to_zen(int *i)
{
   SKanaToDKana = *i;
}



int	DetectLevel = 2;
/*
 *	flag
 *	0:	return
 *	1:	100lines test
 *	2:	if first KANJI code find, it's end.
 *	3:	file's last made test suru.
 */
#define NLINES 1024
int kcode_detect(char *filename) /*{{{*/
{
   int	code = ASCII;
   FILE	*fp;
   unsigned char buf[NLINES], *s;
   int	EightBit=0;
   int	cnt = -1;
   int	cod_cnt[4] = {0,0,0,0};

   if(!kSLis_kanji_code())	return	ASCII;
   if(!DetectLevel)	return kSLfile_code;
   if(DetectLevel == 1)	cnt = 100;

   if((fp = fopen(filename, "rb")) == NULL)	return	kSLfile_code;
   while (((!code && cnt) || DetectLevel==3) && (s = (char*)fgets((char*)buf, NLINES, fp)) != NULL)
     {
	code = IsKcode(buf, strlen(buf), &EightBit);
	if (0 < cnt)	cnt--;
	if (code)
	  {
	     (cod_cnt[code])++;
	     cnt = 0;
	  }
     }
   fclose(fp);
   
   for (cnt = 1 ; cnt < 4 ; cnt++)	if (cod_cnt[cnt]) code = cnt;
   if (cod_cnt[EUC] && cod_cnt[SJIS])	code = BINARY;
   if (!code && EightBit) code = EUC;
   if (!code)	code = kSLfile_code;
   return code;
}

 /*}}}*/

#define issjis2ndkanji(c)	((0x40 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0x7e)	\
			|| (0x80 <= (unsigned char)(c&0xff) && (unsigned char)(c&0xff) <= 0xfc))

int IsKcode(buf, len, EightBit)
unsigned char	*buf;
int	len, *EightBit;
{
   int	code;
   int	i;
   code = ASCII;
   for (i=0 ; (i < len) && (code == ASCII) ; )
     {

	if (*EightBit==0 && buf[i] == ESC)
	  {
	     if ((buf[i+1] == '$' && (buf[i+2] == '@' || buf[i+2] == 'B'))
		 || (buf[i+1] == '(' && (buf[i+2] == 'J' || buf[i+2] == 'B' || buf[i+2] == 'I')))
	       {
		  code = JIS;
	       }
	     else
	       {
		  i++;
	       }
	  }
	else if( (buf[i] & 0x80) == 0 )
	  i++;
	else
	  {
	     *EightBit = 1;

	     if(buf[i] == SS2)
	       {
		  if(!ishkana(buf[i+1]))
		    {
		       code = SJIS;
		    }
		  else if(!issjis2ndkanji(buf[i+1]))
		    {
		       code = EUC;
		    }
		  else
		    {
		       i += 2;
		    }
	       }
/*	     else if(ishkana(buf[i]))
	       {
		  if(!iseuckanji(buf[i]) || !iseuckanji(buf[i+1]))
		    {
		       code = SJIS;
		    }
		  else
		    {
		       code = EUC;
		       i += 2;
		    }
	       } */
	     else if(issjiskanji(buf[i]))
	       {
		  if(!iseuckanji(buf[i]) || !iseuckanji(buf[i+1]))
		    {
		       code = SJIS;
		    }
		  else if(!issjis2ndkanji(buf[i+1]))
		    {
		       code = EUC;
		    }
		  else
		    {
		       i += 2;
		    }
	       }
	     else if(!iseuckanji(buf[i]) || !iseuckanji(buf[i+1]))
	       {
		  code = 5;
	       }
	     else
	       {
		  code = EUC;
	       }
	  }
     }
   return code;
}


#define	BUFSIZE	4
#define PENDING 10

unsigned int kSLsys_getkey(void) /*{{{*/
{
   static unsigned char	buf[BUFSIZE], dst[BUFSIZ], nxtchar = '\0';
   static int ikflg = FALSE, ihflg = FALSE;
   static int	okflg = FALSE, ohflg = FALSE;
   int ishankana = FALSE, iszenkaku = FALSE;
   unsigned int	ret;
   void	(*kcodeto)(char *, char *);
   void	(*kanakcodeto)(char *, char *);
   char	*jiskanji = "\033$@",
	*jiskana = "\033(I",
	*jisascii = "\033(B";
   int incode = kSLinput_code, outcode = kSLcode;
   
   if (incode < 0 || NCODE <= incode) incode = ASCII;
   if (outcode < 0 || NCODE <= outcode) outcode = ASCII;

   if (!SKanaToDKana && kSLinput_code == kSLcode) return _SLsys_getkey();
   
   kcodeto = kSLcodeconv[kSLinput_code][kSLcode];
   kanakcodeto = kSLcodeconv[SJIS][kSLcode];
   if (kcodeto == notconv) return _SLsys_getkey();

   if(nxtchar)
     {
	ret = buf[0] = nxtchar;
	nxtchar = '\0';
     }
   else
     ret = buf[0] = _SLsys_getkey();
   buf[1] = '\0';


   while(kSLinput_code == JIS && buf[0] == ESC)
     {
	if(_SLsys_input_pending(PENDING))
	  {
	     buf[1] = _SLsys_getkey();
	     if(_SLsys_input_pending(PENDING))
	       {
		  buf[2] = _SLsys_getkey();
	       }
	     else
	       {
		  SLang_ungetkey_string(&buf[1], 1);
		  return	ret;
	       }
	  }
	else	return	ret;
	
	if(buf[1] == '$' && (buf[2] == '@' || buf[2] == 'B'))
	  {
	     ikflg = TRUE;
	     ihflg = FALSE;
	  }
	else if(buf[1] == '(' && buf[2] == 'I')
	  {
	     ikflg = FALSE;
	     ihflg = TRUE;
	  }
	else if(buf[1] == '(' && (buf[2] == 'B' || buf[2] == 'J'))
	  {
	     ikflg = ihflg = FALSE;
	  }
	else
	  {
	     SLang_ungetkey_string(&buf[1], 2);
	     return	ret;
	  }
	ret = buf[0] = _SLsys_getkey();
     }


   if((kSLinput_code == JIS && ikflg) || (kSLinput_code == EUC && iseuckanji(ret))
      || (kSLinput_code == SJIS && issjiskanji(ret)))
     {
	buf[1] = _SLsys_getkey();
	kcodeto(buf, dst);
	ret = dst[0];
	iszenkaku = TRUE;
     }
   else if((kSLinput_code == JIS && ihflg) || (kSLinput_code == EUC && ret == SS2)
	   || (kSLinput_code == SJIS && ishkana(ret)))
     {
	if(kSLinput_code == EUC)
	  ret = buf[0] = _SLsys_getkey();
	else if(kSLinput_code == JIS)
	  ret = buf[0] = (ret | 0x80);
/* 		else if(kSLinput_code == SJIS) */

	if(kSLinput_code != EUC && SKanaToDKana && ISNIGORI(ret) && _SLsys_input_pending(PENDING))
	  {
	     nxtchar = buf[1] = _SLsys_getkey();
	     if(kSLinput_code == JIS && nxtchar != ESC &&
		(nxtchar == 0x5e || (nxtchar == 0x5f && ISMARU(ret))))
	       nxtchar = buf[1] = (nxtchar | 0x80);
	     if(buf[1] == 222 || (buf[1] == 223 && ISMARU(ret)))
	       {
		  nxtchar = '\0';
	       }
	  }
	ishankana = TRUE;
     }

   if(ishankana)
     {
	if(SKanaToDKana)
	  {
	     int dummy;
	     buf[0] = (unsigned char)ret;
	     han2zen(buf, dst, &dummy, &dummy, SJIS);
	     kanakcodeto(dst, dst);
	     ret = dst[0];
	     ishankana = FALSE;
	     iszenkaku = TRUE;
	  }
	else
	  {
	     if(kSLcode == JIS && !ohflg)
	       {
		  SLang_ungetkey_string(buf, 1);
		  SLang_ungetkey_string(jiskana+1, 2);
		  ohflg = TRUE;
		  okflg = FALSE;
		  ret = ESC;
	       }
	     else if(kSLcode == EUC)
	       {
		  SLang_ungetkey_string(buf, 1);
		  ret = SS2;
	       }
	  }
     }

   if(iszenkaku)
     {
	SLang_ungetkey_string(&dst[1], 1);

	if(kSLcode == JIS && !okflg)
	  {
	     SLang_ungetkey_string(dst, 1);
	     SLang_ungetkey_string(jiskanji+1, 2);
	     okflg = TRUE;
	     ohflg = FALSE;
	     ret = ESC;
	  }
     }
   else if(/* !iszenkaku && */ !ishankana)
     {
	if(kSLcode == JIS && (okflg || ohflg))
	  {
	     if(kSLcode == JIS && !okflg)
	       {
		  SLang_ungetkey_string(buf, 1);
		  SLang_ungetkey_string(jisascii+1, 2);
		  okflg = ohflg = FALSE;
		  ret = ESC;
	       }
	  }
     }

   return	ret;
}

 /*}}}*/

static SLang_Intrin_Fun_Type SLKanji_ITable[] =  /*{{{*/
{
   MAKE_INTRINSIC_I("iskanji", kSLiskanji, SLANG_INT_TYPE),

#if 0
   MAKE_INTRINSIC_SS("sjis_to_slang", notconv, SLANG_VOID_TYPE),
   MAKE_INTRINSIC_SS("jis_to_slang", jistosjis, SLANG_VOID_TYPE),
   MAKE_INTRINSIC_SS("euc_to_slang", euctosjis, SLANG_VOID_TYPE),
   MAKE_INTRINSIC_SS("to_sjis", notconv, SLANG_VOID_TYPE),
   MAKE_INTRINSIC_SS("to_euc", sjistoeuc, SLANG_VOID_TYPE),
   MAKE_INTRINSIC_SS("to_jis", sjistojis, SLANG_VOID_TYPE),
#endif
   SLANG_END_TABLE
};

 /*}}}*/

static SLang_Intrin_Var_Type SLKanji_Vars[] =  /*{{{*/
{
   MAKE_VARIABLE("NOKANJI", &jp_nokanji, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("ASCII", &ascii, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("EUC", &jp_euc, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("JIS", &jp_jis, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("SJIS", &jp_sjis, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("TRUE", &val_true, SLANG_INT_TYPE, 1),
   MAKE_VARIABLE("FALSE", &val_false, SLANG_INT_TYPE, 1),

   MAKE_VARIABLE("kfile_code", &kSLfile_code, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("kinput_code", &kSLinput_code, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("kdisplay_code", &kSLdisplay_code, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("KfioAuto", &kSLfiAuto, SLANG_INT_TYPE, 0),  /* for compatibility */
   							      /* use "kanji_filecode_detect" variable */
   MAKE_VARIABLE("kanji_filecode_detect", &kSLfiAuto, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("han_to_zen", &SKanaToDKana, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("SLang_code", &kSLcode, SLANG_INT_TYPE, 0),
   MAKE_VARIABLE("KANJI_DETECT", &DetectLevel, SLANG_INT_TYPE, 0),
   SLANG_END_TABLE
};

 /*}}}*/

int kSLinit_kanji(void)  /*{{{*/
{
   int ret;

#if 0
   if (-1 == SLadd_intrin_fun_table(SLKanji_ITable, NULL)
       || (-1 == SLadd_intrin_var_table (SLKanji_Vars, NULL)))
     return -1;
#endif
   
   return 0;
}

 /*}}}*/

