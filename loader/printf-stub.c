/*
 *  linux/lib/vsprintf.c
 *
 *  Copyright (C) 1991, 1992  Linus Torvalds
 *  Copyright (C) 2000 Jakub Jelinek <jakub@redhat.com>
 */

/* vsprintf.c -- Lars Wirzenius & Linus Torvalds. */
/*
 * Wirzenius wrote this portably, Torvalds fucked it up :-)
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

/* Define ALIAS as a strong alias for ORIGINAL.  */
# define strong_alias(name, aliasname) _strong_alias(name, aliasname)
# define _strong_alias(name, aliasname) \
  extern __typeof (name) aliasname __attribute__ ((alias (#name)));

#define do_div(n,base) ({ \
	int __res; \
	__res = ((unsigned long long) n) % (unsigned) base; \
	n = ((unsigned long long) n) / (unsigned) base; \
	__res; })

static int skip_atoi(const char **s)
{
	int i=0;

	while (isdigit(**s))
		i = i*10 + *((*s)++) - '0';
	return i;
}

#define ZEROPAD	1		/* pad with zero */
#define SIGN	2		/* unsigned/signed long */
#define PLUS	4		/* show plus */
#define SPACE	8		/* space if plus */
#define LEFT	16		/* left justified */
#define SPECIAL	32		/* 0x */
#define LARGE	64		/* use 'ABCDEF' instead of 'abcdef' */

static char * number(char * str, long long num, int base, int size, int precision, int type)
{
	char c,sign,tmp[66];
	const char *digits="0123456789abcdefghijklmnopqrstuvwxyz";
	int i;

	if (type & LARGE)
		digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
	if ((type & LEFT) || precision >= 0)
		type &= ~ZEROPAD;
	if (base < 2 || base > 36)
		return 0;
	c = (type & ZEROPAD) ? '0' : ' ';
	sign = 0;
	if (type & SIGN) {
		if (num < 0) {
			sign = '-';
			num = -num;
			size--;
		} else if (type & PLUS) {
			sign = '+';
			size--;
		} else if (type & SPACE) {
			sign = ' ';
			size--;
		}
	}
	if (type & SPECIAL) {
		if (base == 16)
			size -= 2;
		else if (base == 8)
			size--;
	}
	i = 0;
	if (num == 0)
		tmp[i++]='0';
	else while (num != 0)
		tmp[i++] = digits[do_div(num,base)];
	if (i > precision)
		precision = i;
	size -= precision;
	if (!(type&(ZEROPAD+LEFT)))
		while(size-->0)
			*str++ = ' ';
	if (sign)
		*str++ = sign;
	if (type & SPECIAL) {
		if (base==8)
			*str++ = '0';
		else if (base==16) {
			*str++ = '0';
			*str++ = digits[33];
		}
	}
	if (!(type & LEFT))
		while (size-- > 0)
			*str++ = c;
	while (i < precision--)
		*str++ = '0';
	while (i-- > 0)
		*str++ = tmp[i];
	while (size-- > 0)
		*str++ = ' ';
	return str;
}

static char bigbuf[1024], *buf = NULL, *str, *lim;

static void check(int width)
{
	if (str + width + 16 < lim)
		return;
	if (width < 512) width = 512;
	if (buf == bigbuf) {
		buf = (char *)malloc(1024 + width);
		memcpy (buf, bigbuf, str - bigbuf);
		str = buf + (str - bigbuf);
		lim = buf + 1024 + width;
	} else {
		int w = lim - buf + width;
		buf = (char *)realloc (buf, w);
		lim = buf + w;
	}
}

static void xprintf(const char *fmt, va_list args)
{
	int len;
	unsigned long long num;
	int i, base;
	const char *s;

	int flags;		/* flags to number() */

	int field_width;	/* width of output field */
	int precision;		/* min. # of digits for integers; max
				   number of chars for from string */
	int qualifier;		/* 'h', 'l', or 'L' for integer fields */
	                        /* 'z' support added 23/7/1999 S.H.    */
				/* 'z' changed to 'Z' --davidm 1/25/99 */

	for (str=buf ; *fmt ; ++fmt) {
		if (*fmt != '%') {
			check (1);
			*str++ = *fmt;
			continue;
		}
			
		/* process flags */
		flags = 0;
		repeat:
			++fmt;		/* this also skips first '%' */
			switch (*fmt) {
				case '-': flags |= LEFT; goto repeat;
				case '+': flags |= PLUS; goto repeat;
				case ' ': flags |= SPACE; goto repeat;
				case '#': flags |= SPECIAL; goto repeat;
				case '0': flags |= ZEROPAD; goto repeat;
				}
		
		/* get field width */
		field_width = -1;
		if (isdigit(*fmt))
			field_width = skip_atoi(&fmt);
		else if (*fmt == '*') {
			++fmt;
			/* it's the next argument */
			field_width = va_arg(args, int);
			if (field_width < 0) {
				field_width = -field_width;
				flags |= LEFT;
			}
		}

		/* get the precision */
		precision = -1;
		if (*fmt == '.') {
			++fmt;	
			if (isdigit(*fmt))
				precision = skip_atoi(&fmt);
			else if (*fmt == '*') {
				++fmt;
				/* it's the next argument */
				precision = va_arg(args, int);
			}
			if (precision < 0)
				precision = 0;
		}

		/* get the conversion qualifier */
		qualifier = -1;
		if (*fmt == 'h' || *fmt == 'l' || *fmt == 'L' || *fmt =='Z') {
			qualifier = *fmt;
			++fmt;
			if (qualifier == 'l' && *fmt == 'l') {
				qualifier = 'L';
				++fmt;
			}
		}

		/* default base */
		base = 10;

		switch (*fmt) {
		case 'c':
			check(field_width + 2);
			if (!(flags & LEFT)) {
				while (--field_width > 0)
					*str++ = ' ';
			}
			*str++ = (unsigned char) va_arg(args, int);
			while (--field_width > 0)
				*str++ = ' ';
			continue;

		case 's':
			s = va_arg(args, char *);
			if (!s)
				s = "(null)";
got_string:
			len = strnlen(s, precision);

			check(field_width > len ? field_width : len);
			if (!(flags & LEFT))
				while (len < field_width--)
					*str++ = ' ';
			for (i = 0; i < len; ++i)
				*str++ = *s++;
			while (len < field_width--)
				*str++ = ' ';
			continue;

		case 'p':
			{
			unsigned long ptr;
			ptr = (unsigned long) va_arg(args, void *);
			if (!ptr) {
				if (precision >= 0 && precision < 5)
					precision = 5;
				s = "(nil)";
				goto got_string;
			}
			if (field_width == -1) {
				field_width = 2*sizeof(void *)+2;
				flags |= ZEROPAD;
			}
			check(field_width + 32 + precision);
			str = number(str, ptr, 16,
				field_width, precision, flags | SPECIAL);
			}
			continue;

		case 'n':
			if (qualifier == 'l') {
				long * ip = va_arg(args, long *);
				*ip = (str - buf);
			} else if (qualifier == 'Z') {
				size_t * ip = va_arg(args, size_t *);
				*ip = (str - buf);
			} else {
				int * ip = va_arg(args, int *);
				*ip = (str - buf);
			}
			continue;

		case '%':
			check(1);
			*str++ = '%';
			continue;

		/* integer number formats - set up the flags and "break" */
		case 'o':
			base = 8;
			break;

		case 'X':
			flags |= LARGE;
		case 'x':
			base = 16;
			break;

		case 'd':
		case 'i':
			flags |= SIGN;
		case 'u':
			break;

		case 'e':
		case 'E':
		case 'f':
		case 'g':
		case 'G':
			fputs("Floating point output not supported by xprintf\n", stderr);
			exit(1);

		default:
			check(2);
			*str++ = '%';
			if (*fmt)
				*str++ = *fmt;
			else
				--fmt;
			continue;
		}
		if (qualifier == 'L')
			num = va_arg(args, long long);
		else if (qualifier == 'l') {
			num = va_arg(args, unsigned long);
			if (flags & SIGN)
				num = (signed long) num;
		} else if (qualifier == 'Z') {
			num = va_arg(args, size_t);
		} else if (qualifier == 'h') {
			num = (unsigned short) va_arg(args, int);
			if (flags & SIGN)
				num = (signed short) num;
		} else {
			num = va_arg(args, unsigned int);
			if (flags & SIGN)
				num = (signed int) num;
		}
		check (field_width + 32 + precision);
		str = number(str, num, base, field_width, precision, flags);
	}
	*str++ = '\0';
}

int vsnprintf(char * b, size_t n, const char *fmt, va_list args)
{
	buf = bigbuf;
	lim = buf + 1024;
	xprintf(fmt, args);
	if (str - buf > n) {
		memcpy(b, buf, n - 1);
		b[n - 1] = '\0';
	} else
		strcpy(b, buf);
	if (buf != bigbuf)
		free (buf);
	return str - buf - 1;
}

int snprintf(char * buf, size_t n, const char *fmt, ...)
{
	va_list args;
	int i;

	va_start(args, fmt);
	i=vsnprintf(buf,n,fmt,args);
	va_end(args);
	return i;
}

int vsprintf(char * b, const char *fmt, va_list args)
{
	buf = b;
	lim = (char *)~0UL;
	xprintf(fmt, args);
	return str - buf - 1;
}

int sprintf(char * buf, const char *fmt, ...)
{
	va_list args;
	int i;

	va_start(args, fmt);
	i=vsprintf(buf,fmt,args);
	va_end(args);
	return i;
}

int _IO_vfprintf(FILE *f, const char *fmt, va_list args)
{
	buf = bigbuf;
	lim = buf + 1024;
	xprintf(fmt, args);
	fputs(buf, f);
	if (buf != bigbuf)
		free(buf);
	return str - buf - 1;
}

int fprintf(FILE *f, const char *fmt, ...)
{
	va_list args;
	int i;

	va_start(args, fmt);
	i=vfprintf(f,fmt,args);
	va_end(args);
	return i;
}

int printf(const char *fmt, ...)
{
	va_list args;
	int i;

	va_start(args, fmt);
	i=vfprintf(stdout,fmt,args);
	va_end(args);
	return i;
}

#define SUPPRESS	128

int _IO_sscanf(const char *str, const char *fmt, ...)
{
	va_list args;
	int ret = EOF;
	unsigned long long lnum;
	unsigned long num;
	int suppress, base, numbersigned;
	int field_width;	/* width of output field */
	int qualifier;		/* 'h', 'l', or 'L' for integer fields */
	char *s, *p, *q;
	const char *start = str;

	va_start(args, fmt);

	for (; *fmt ; ++fmt) {
		if (isspace(*fmt)) {
			while (isspace(*str))
				str++;
			continue;
		}
		if (*fmt != '%') {
			if (*str++ != *fmt)
				goto done;
			continue;
		}

		if (ret == EOF) ret = 0;
			
		suppress = 0;
		if (*++fmt == '*') {
			suppress = 1;
			fmt++;
		}

		/* get field width */
		field_width = -1;
		if (isdigit(*fmt))
			field_width = skip_atoi(&fmt);

		/* get the conversion qualifier */
		qualifier = -1;
		if (*fmt == 'h' || *fmt == 'l' || *fmt == 'L') {
			qualifier = *fmt;
			++fmt;
			if (qualifier == 'l' && *fmt == 'l') {
				qualifier = 'L';
				++fmt;
			}
		}
		
		if (strchr ("%c[", *fmt) == NULL) {
			while (isspace(*str))
				str++;
		}

		base = 0;
		numbersigned = 0;

		switch (*fmt) {
		case 'c':
			if (field_width == -1)
				field_width = 1;
			if (strlen(str) < field_width)
				goto done;
			if (!suppress) {
				p = va_arg(args, char *);
				if (!p) goto done;
				memcpy(p, str, field_width);
				ret++;
			}
			str += field_width;
			continue;
		case 's':
			for (s = (char *)str; *s && !isspace(*s) && field_width != 0; s++)
				field_width--;
finish_s:
			if (s == str)
				goto done;
			if (!suppress) {
				p = va_arg(args, char *);
				if (!p) goto done;
				memcpy(p, str, s - str);
				p[s - str] = '\0';
				ret++;
			}
			str = s;
			continue;
		case '[': {
			int not_in = 0;
			memset(bigbuf, 0, 256);
			if (*++fmt == '^') {
				not_in = 1;
				fmt++;
			}
			if (*fmt == ']') {
				bigbuf[']'] = 1;
				fmt++;
			}
			while (*fmt != ']') {
				if (!*fmt) goto done;
				bigbuf[(unsigned char)*fmt] = 1;
				if (fmt[1] == '-' && fmt[2] != ']') {
					unsigned char c = (unsigned char)*fmt + 1;
					while (c <= (unsigned char)fmt[2])
						bigbuf[c++] = 1;
					fmt += 2;
				}
				fmt++;
			}
			if (not_in) {
				int i;
				for (i = 1; i < 256; i++)
					bigbuf[i] ^= 1;
			}
			for (s = (char *)str; bigbuf[(unsigned char)*s] && field_width != 0; s++)
				field_width--;
			}
			goto finish_s;

		case 'n':
			if (qualifier == 'l') {
				long * ip = va_arg(args, long *);
				*ip = (str - start);
			} else {
				int * ip = va_arg(args, int *);
				*ip = (str - start);
			}
			continue;

		case '%':
			if (*str++ != '%')
				goto done;
			continue;

		case 'e':
		case 'E':
		case 'f':
		case 'g':
		case 'G':
			fputs("Floating point output not supported by xprintf\n", stderr);
			exit(1);

		default:
			goto done;

		/* integer number formats - set up the flags and "break" */
		case 'o':
			base = 8;
			break;

		case 'p':
			qualifier = 'l';
		case 'X':
		case 'x':
			base = 16;
			break;

		case 'd':
			base = 10;
		case 'i':
			numbersigned = 1;
			break;
		case 'u':
			base = 10;
			break;
		}
		p = (char *)str;
		if (field_width >= 0) {
			strncpy(bigbuf, str, field_width);
			bigbuf[field_width] = 0;
			p = bigbuf;
		}
		if (numbersigned) {
			if (qualifier == 'L')
				lnum = strtoll(p, &q, base);
			else
				num = strtol(p, &q, base);
		} else {
			if (qualifier == 'L')
				lnum = strtoull(p, &q, base);
			else
				num = strtoull(p, &q, base);
		}
		if (p == q)
			goto done;
		str += (q - p);
		if (!suppress) {
			p = (char *)va_arg(args, char *);
			if (p == NULL)
				goto done;
			if (qualifier == 'L')
				*(unsigned long long *)p = lnum;
			else if (qualifier == 'l')
				*(unsigned long *)p = num;
			else if (qualifier == 'h')
				*(unsigned short *)p = num;
			else
				*(unsigned int *)p = num;
			ret++;
		}
	}
done:
	va_end (args);
	return ret;
}

strong_alias (_IO_vfprintf, vfprintf);
strong_alias (_IO_sscanf, sscanf);
