/* Copyright (c) 1992, 1998 John E. Davis
 * This file is part of the S-Lang library.
 *
 * You may distribute under the terms of either the GNU General Public
 * License or the Perl Artistic License.
 */

#include "config.h"
#include "sl-feat.h"

#include <stdio.h>
#include "slang.h"
#include "_slang.h"

unsigned int SLang_Input_Buffer_Len = 0;
unsigned char SLang_Input_Buffer [SL_MAX_INPUT_BUFFER_LEN];

int SLang_Abort_Char = 7;
int SLang_Ignore_User_Abort = 0;

/* This has the effect of mapping all characters in the range 128-169 to
 * ESC [ something
 */

unsigned int SLang_getkey (void)
{
   unsigned int imax;
   unsigned int ch;

   if (SLang_Input_Buffer_Len)
     {
	ch = (unsigned int) *SLang_Input_Buffer;
	SLang_Input_Buffer_Len--;
	imax = SLang_Input_Buffer_Len;

	SLMEMCPY ((char *) SLang_Input_Buffer,
		(char *) (SLang_Input_Buffer + 1), imax);
     }
   else if (SLANG_GETKEY_ERROR == (ch = _SLsys_getkey ())) return ch;

#if _SLANG_MAP_VTXXX_8BIT
# if !defined(IBMPC_SYSTEM)
   if (ch & 0x80)
     {
	unsigned char i;
	i = (unsigned char) (ch & 0x7F);
	if (i < ' ')
	  {
	     i += 64;
	     SLang_ungetkey (i);
	     ch = 27;
	  }
     }
# endif
#endif
   return(ch);
}

int SLang_ungetkey_string (unsigned char *s, unsigned int n)
{
   register unsigned char *bmax, *b, *b1;
   if (SLang_Input_Buffer_Len + n + 3 > SL_MAX_INPUT_BUFFER_LEN) 
     return -1;

   b = SLang_Input_Buffer;
   bmax = (b - 1) + SLang_Input_Buffer_Len;
   b1 = bmax + n;
   while (bmax >= b) *b1-- = *bmax--;
   bmax = b + n;
   while (b < bmax) *b++ = *s++;
   SLang_Input_Buffer_Len += n;
   return 0;
}

int SLang_buffer_keystring (unsigned char *s, unsigned int n)
{

   if (n + SLang_Input_Buffer_Len + 3 > SL_MAX_INPUT_BUFFER_LEN) return -1;

   SLMEMCPY ((char *) SLang_Input_Buffer + SLang_Input_Buffer_Len,
	   (char *) s, n);
   SLang_Input_Buffer_Len += n;
   return 0;
}

int SLang_ungetkey (unsigned char ch)
{
   return SLang_ungetkey_string(&ch, 1);
}

int SLang_input_pending (int tsecs)
{
   int n;
   unsigned char c;
   if (SLang_Input_Buffer_Len) return (int) SLang_Input_Buffer_Len;

   n = _SLsys_input_pending (tsecs);

   if (n <= 0) return 0;

   c = (unsigned char) SLang_getkey ();
   SLang_ungetkey_string (&c, 1);

   return n;
}

void SLang_flush_input (void)
{
   int quit = SLKeyBoard_Quit;

   SLang_Input_Buffer_Len = 0;
   SLKeyBoard_Quit = 0;
   while (_SLsys_input_pending (0) > 0)
     {
	(void) _SLsys_getkey ();
	/* Set this to 0 because _SLsys_getkey may stuff keyboard buffer if
	 * key sends key sequence (OS/2, DOS, maybe VMS).
	 */
	SLang_Input_Buffer_Len = 0;
     }
   SLKeyBoard_Quit = quit;
}


#ifdef IBMPC_SYSTEM
static int Map_To_ANSI;
int SLgetkey_map_to_ansi (int enable)
{
   Map_To_ANSI = enable;
   return 0;
}

unsigned int _SLpc_convert_scancode (unsigned int scan)
{
   char *keystr;

   if (Map_To_ANSI == 0)
     {
	SLang_ungetkey (scan);
	return 0;
     }

   
   /* These mappings correspond to what rxvt produces under Linux */
   switch (scan)
     {
      default:
	return 0;
	
      case 'G':			       /* home */
	keystr = "[1~";
	break;
      case 'H':			       /* up */
	keystr = "[A";
	break;
      case 'I':			       /* PgUp */
	keystr = "[5~";
	break;
      case 'K':			       /* Left */
	keystr = "[D";
	break;
      case 'M':			       /* Right */
	keystr = "[C";
	break;
      case 'O':			       /* End */
	keystr = "[4~";
	break;
      case 'P':			       /* Down */
	keystr = "[B";
	break;
      case 'Q':			       /* PgDn */
	keystr = "[6~";
	break;
      case 'R':			       /* Insert */
	keystr = "[2~";
	break;
      case 'S':			       /* Delete */
	keystr = "[3~";
	break;

      case ';':			       /* F1 */
      case 'T':			       /* (shift) */
      case '^':			       /* (ctrl) */
      case 'h':			       /* (alt) */
	keystr = "[11~";
	break;

      case '<':			       /* F2 */
      case 'U':			       /* (shift) */
      case '_':			       /* (ctrl) */
      case 'i':			       /* (alt) */
	keystr = "[12~";
	break;

      case '=':			       /* F3 */
      case 'V':			       /* (shift) */
      case '`':			       /* (ctrl) */
      case 'j':			       /* (alt) */
	keystr = "[13~";
	break;

      case '>':			       /* F4 */
      case 'W':			       /* (shift) */
      case 'a':			       /* (ctrl) */
      case 'k':			       /* (alt) */
	keystr = "[14~";
	break;

      case '?':			       /* F5 */
      case 'X':			       /* (shift) */
      case 'b':			       /* (ctrl) */
      case 'l':			       /* (alt) */
	keystr = "[15~";
	break;

      case '@':			       /* F6 */
      case 'Y':			       /* (shift) */
      case 'c':			       /* (ctrl) */
      case 'm':			       /* (alt) */
	keystr = "[17~";
	break;

      case 'A':			       /* F7 */
      case 'Z':			       /* (shift) */
      case 'd':			       /* (ctrl) */
      case 'n':			       /* (alt) */
	keystr = "[18~";
	break;

      case 'B':			       /* F8 */
      case '[':			       /* (shift) */
      case 'e':			       /* (ctrl) */
      case 'o':			       /* (alt) */
	keystr = "[19~";
	break;

      case 'C':			       /* F9 */
      case '\\':		       /* (shift) */
      case 'f':			       /* (ctrl) */
      case 'p':			       /* (alt) */
	keystr = "[20~";
	break;

      case 'D':			       /* F10 */
      case ']':			       /* (shift) */
      case 'g':			       /* (ctrl) */
      case 'q':			       /* (alt) */
	keystr = "[21~";
	break;
	
      case 133:			       /* F11 */
      case 135:			       /* (shift) */
      case 137:			       /* (ctrl) */
      case 139:			       /* (alt) */
	keystr = "[23~";
	break;
	
      case 134:			       /* F12 */
      case 136:			       /* (shift) */
      case 138:			       /* (ctrl) */
      case 140:			       /* (alt) */
	keystr = "[24~";
	break;
     }
   
   (void) SLang_ungetkey_string ((unsigned char *)keystr, strlen (keystr));
   return 27;
}

#endif
