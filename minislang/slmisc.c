/* Copyright (c) 1992, 1998 John E. Davis
 * This file is part of the S-Lang library.
 *
 * You may distribute under the terms of either the GNU General Public
 * License or the Perl Artistic License.
 */
#include "config.h"
#include "sl-feat.h"

#include <stdio.h>
#include <string.h>

#include "slang.h"
#include "_slang.h"

#define DEBUG_MALLOC 0

#if DEBUG_MALLOC
# define SLREALLOC_FUN	SLdebug_realloc
# define SLMALLOC_FUN	SLdebug_malloc
# define SLFREE_FUN	SLdebug_free
#else
# define SLREALLOC_FUN	SLREALLOC
# define SLMALLOC_FUN	SLMALLOC
# define SLFREE_FUN	SLFREE
#endif

char *SLmake_string(char *str)
{
   return SLmake_nstring(str, strlen (str));
}

char *SLmake_nstring (char *str, unsigned int n)
{
   char *ptr;

   if (NULL == (ptr = SLmalloc(n + 1)))
     {
	return NULL;
     }
   SLMEMCPY (ptr, str, n);
   ptr[n] = 0;
   return(ptr);
}

void SLmake_lut (unsigned char *lut, unsigned char *range, unsigned char reverse)
{
   register unsigned char *l = lut, *lmax = lut + 256;
   int i, r1, r2;

   while (l < lmax) *l++ = reverse;

   while (*range)
     {
	r1 = *range;
	if (*(range + 1) == '-')
	  {
	     range += 2;
	     r2 = *range;
	  }
	else r2 = r1;

	for (i = r1; i <= r2; i++) lut[i] = !reverse;
	if (*range) range++;
     }
}

char *SLmalloc (unsigned int len)
{
   char *p;

   p = (char *) SLMALLOC_FUN (len);
   if (p == NULL)
     SLang_Error = SL_MALLOC_ERROR;

   return p;
}

void SLfree (char *p)
{
   if (p != NULL) SLFREE_FUN (p);
}

char *SLrealloc (char *p, unsigned int len)
{
   if (len == 0)
     {
	SLfree (p);
	return NULL;
     }

   if (p == NULL) p = SLmalloc (len);
   else
     {
	p = SLREALLOC_FUN (p, len);
	if (p == NULL)
	  SLang_Error = SL_MALLOC_ERROR;
     }
   return p;
}

char *SLcalloc (unsigned int nelems, unsigned int len)
{
   char *p;

   len = nelems * len;
   p = SLmalloc (len);
   if (p != NULL) SLMEMSET (p, 0, len);
   return p;
}

/* p and ch may point to the same buffer */
char *_SLexpand_escaped_char(char *p, char *ch)
{
   int i = 0;
   int max = 0, num, base = 0;
   char ch1;

   ch1 = *p++;

   switch (ch1)
     {
      default: num = ch1; break;
      case 'n': num = '\n'; break;
      case 't': num = '\t'; break;
      case 'v': num = '\v'; break;
      case 'b': num = '\b'; break;
      case 'r': num = '\r'; break;
      case 'f': num = '\f'; break;
      case 'E': case 'e': num = 27; break;
      case 'a': num = 7;
	break;

	/* octal */
      case '0': case '1': case '2': case '3':
      case '4': case '5': case '6': case '7':
	max = '7';
	base = 8; i = 2; num = ch1 - '0';
	break;

      case 'd':			       /* decimal -- S-Lang extension */
	base = 10;
	i = 3;
	max = '9';
	num = 0;
	break;

      case 'x':			       /* hex */
	base = 16;
	max = '9';
	i = 2;
	num = 0;
	break;
     }

   while (i--)
     {
	ch1 = *p;

	if ((ch1 <= max) && (ch1 >= '0'))
	  {
	     num = base * num + (ch1 - '0');
	  }
	else if (base == 16)
	  {
	     ch1 |= 0x20;
	     if ((ch1 < 'a') || ((ch1 > 'f'))) break;
	     num = base * num + 10 + (ch1 - 'a');
	  }
	else break;
	p++;
     }

   *ch = (char) num;
   return p;
}

/* s and t could represent the same space */
void SLexpand_escaped_string (register char *s, register char *t,
			      register char *tmax)
{
   char ch;

   while (t < tmax)
     {
	ch = *t++;
	if (ch == '\\')
	  {
	     t = _SLexpand_escaped_char (t, &ch);
	  }
	*s++ = ch;
     }
   *s = 0;
}

int SLextract_list_element (char *list, unsigned int nth, char delim,
			    char *elem, unsigned int buflen)
{
   char *el, *elmax;
   char ch;

   while (nth > 0)
     {
	while ((0 != (ch = *list)) && (ch != delim))
	  list++;
	
	if (ch == 0) return -1;

	list++;
	nth--;
     }

   el = elem;
   elmax = el + (buflen - 1);

   while ((0 != (ch = *list)) && (ch != delim) && (el < elmax))
     *el++ = *list++;
   *el = 0;

   return 0;
}

#ifndef HAVE_VSNPRINTF
int _SLvsnprintf (char *buf, unsigned int buflen, char *fmt, va_list ap)
{
   int status;
   
   status = vsprintf (buf, fmt, ap);
   if (status >= (int) buflen)
     {
	/* If we are lucky, we will get this far.  The real solution is to
	 * provide a working version of vsnprintf
	 */
	SLang_exit_error ("\
Your system lacks the vsnprintf system call and vsprintf overflowed a buffer.\n\
The integrity of this program has been violated.\n");
	return EOF;		       /* NOT reached */
     }
   return status;
}
#endif

#ifndef HAVE_SNPRINTF
int _SLsnprintf (char *buf, unsigned int buflen, char *fmt, ...)
{
   int status;

   va_list ap;
   
   va_start (ap, fmt);
   status = _SLvsnprintf (buf, buflen, fmt, ap);
   va_end (ap);
   
   return status;
}
#endif
