/* src/sysconf.h.  Generated automatically by configure.  */
/* -*- c -*- */
/* Note: this is for unix only. */

#ifndef SL_CONFIG_H
#define SL_CONFIG_H

/* define if you have stdlib.h */
#define HAVE_STDLIB_H 1

/* define if you have unistd.h */
#define HAVE_UNISTD_H 1

/* define if you have termios.h */
#define HAVE_TERMIOS_H 1

/* define if you have memory.h */
#define HAVE_MEMORY_H 1

/* define if you have malloc.h */
#define HAVE_MALLOC_H 1

/* define if you have memset */
#define HAVE_MEMSET 1

/* define if you have memcpy */
#define HAVE_MEMCPY 1

#define HAVE_VFSCANF 1

/* define if you have fcntl.h */
#define HAVE_FCNTL_H 1

/* Define if you have the vsnprintf, snprintf functions and they return
 * EOF upon failure.
 */
#define HAVE_VSNPRINTF 1
#define HAVE_SNPRINTF 1

/* define if you have sys/fcntl.h */
#define HAVE_SYS_FCNTL_H 1

#define HAVE_SYS_TYPES_H 1
#define HAVE_SYS_WAIT_H 1

/* define if you have this. */
#define HAVE_PUTENV 1
#define HAVE_GETCWD 1
#define HAVE_TCGETATTR 1
#define HAVE_TCSETATTR 1
#define HAVE_CFGETOSPEED 1
#define HAVE_LSTAT 1
#define HAVE_KILL 1
#define HAVE_CHOWN 1
#define HAVE_VSNPRINTF 1

/* #undef USE_TERMCAP */

/* #undef mode_t */
/* #undef uid_t */
/* #undef pid_t */
/* #undef gid_t */

/* Do we have posix signals? */
#define HAVE_SIGACTION 1
#define HAVE_SIGPROCMASK 1
#define HAVE_SIGEMPTYSET 1
#define HAVE_SIGADDSET 1

#if defined(HAVE_SIGADDSET) && defined(HAVE_SIGEMPTYSET)
# if defined(HAVE_SIGACTION) && defined(HAVE_SIGPROCMASK)
#  define SLANG_POSIX_SIGNALS
# endif
#endif

/* Define if you need to in order for stat and other things to work.  */
/* #undef _POSIX_SOURCE */

#ifdef _AIX
# ifndef _POSIX_SOURCE
#  define _POSIX_SOURCE 1
# endif
# ifndef _ALL_SOURCE
#  define _ALL_SOURCE
# endif
/* This may generate warnings but the fact is that without it, xlc will 
 * INCORRECTLY inline many str* functions. */
/* # undef __STR__ */
#endif

/* define USE_TERMCAP if you want to use it instead of terminfo. */
#if defined(sequent) || defined(NeXT)
# ifndef USE_TERMCAP
#  define USE_TERMCAP
# endif
#endif

#if defined(ultrix) && !defined(__GNUC__)
# ifndef NO_PROTOTYPES
#  define NO_PROTOTYPES
# endif
#endif

#ifndef unix
# define unix 1
#endif

#ifndef __unix__
# define __unix__ 1
#endif

#define _SLANG_SOURCE_	1
#endif /* SL_CONFIG_H */
