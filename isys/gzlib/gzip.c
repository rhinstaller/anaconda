/* gzip (GNU zip) -- compress files with zip algorithm and 'compress' interface
 * Copyright (C) 1992-1993 Jean-loup Gailly
 * The unzip code was written and put in the public domain by Mark Adler.
 * Portions of the lzw code are derived from the public domain 'compress'
 * written by Spencer Thomas, Joe Orost, James Woods, Jim McKie, Steve Davies,
 * Ken Turkowski, Dave Mack and Peter Jannesen.
 *
 * See the license_msg below and the file COPYING for the software license.
 * See the file algorithm.doc for the compression algorithms and file formats.
 */


/* Compress files with zip algorithm and 'compress' interface.
 * See usage() and help() functions below for all options.
 * Outputs:
 *        file.gz:   compressed file with same mode, owner, and utimes
 *     or stdout with -c option or if stdin used as input.
 * If the output file name had to be truncated, the original name is kept
 * in the compressed file.
 * On MSDOS, file.tmp -> file.tmz. On VMS, file.tmp -> file.tmp-gz.
 *
 * Using gz on MSDOS would create too many file name conflicts. For
 * example, foo.txt -> foo.tgz (.tgz must be reserved as shorthand for
 * tar.gz). Similarly, foo.dir and foo.doc would both be mapped to foo.dgz.
 * I also considered 12345678.txt -> 12345txt.gz but this truncates the name
 * too heavily. There is no ideal solution given the MSDOS 8+3 limitation. 
 *
 * For the meaning of all compilation flags, see comments in Makefile.in.
 */

#ifdef RCSID
static char rcsid[] = "$Id$";
#endif

#include <config.h>
#include <ctype.h>
#include <sys/types.h>
#include <signal.h>
#include <sys/stat.h>
#include <errno.h>

#include "tailor.h"
#include "gzip.h"
#include "lzw.h"

		/* configuration */

#ifdef HAVE_TIME_H
#  include <time.h>
#else
#  include <sys/time.h>
#endif

#ifdef HAVE_FCNTL_H
#  include <fcntl.h>
#endif

#ifdef HAVE_LIMITS_H
#  include <limits.h>
#endif

#ifdef HAVE_UNISTD_H
#  include <unistd.h>
#endif

#if defined STDC_HEADERS || defined HAVE_STDLIB_H
#  include <stdlib.h>
#endif

#ifdef HAVE_DIRENT_H
#  include <dirent.h>
#  define NAMLEN(direct) strlen((direct)->d_name)
#  define DIR_OPT "DIRENT"
#else
#  define dirent direct
#  define NAMLEN(direct) ((direct)->d_namlen)
#  ifdef HAVE_SYS_NDIR_H
#    include <sys/ndir.h>
#    define DIR_OPT "SYS_NDIR"
#  endif
#  ifdef HAVE_SYS_DIR_H
#    include <sys/dir.h>
#    define DIR_OPT "SYS_DIR"
#  endif
#  ifdef HAVE_NDIR_H
#    include <ndir.h>
#    define DIR_OPT "NDIR"
#  endif
#  ifndef DIR_OPT
#    define DIR_OPT "NO_DIR"
#  endif
#endif

#ifdef CLOSEDIR_VOID
# define CLOSEDIR(d) (closedir(d), 0)
#else
# define CLOSEDIR(d) closedir(d)
#endif

#ifdef HAVE_UTIME
#  ifdef HAVE_UTIME_H
#    include <utime.h>
#    define TIME_OPT "UTIME"
#  else
#    ifdef HAVE_SYS_UTIME_H
#      include <sys/utime.h>
#      define TIME_OPT "SYS_UTIME"
#    else
       struct utimbuf {
         time_t actime;
         time_t modtime;
       };
#      define TIME_OPT "STRUCT_UTIMBUF"
#    endif
#  endif
#else
#  define TIME_OPT "NO_UTIME"
#endif

#if !defined(S_ISDIR) && defined(S_IFDIR)
#  define S_ISDIR(m) (((m) & S_IFMT) == S_IFDIR)
#endif
#if !defined(S_ISREG) && defined(S_IFREG)
#  define S_ISREG(m) (((m) & S_IFMT) == S_IFREG)
#endif

typedef RETSIGTYPE (*sig_type) OF((int));

#ifndef	O_BINARY
#  define  O_BINARY  0  /* creation mode for open() */
#endif

#ifndef O_CREAT
   /* Pure BSD system? */
#  include <sys/file.h>
#  ifndef O_CREAT
#    define O_CREAT FCREAT
#  endif
#  ifndef O_EXCL
#    define O_EXCL FEXCL
#  endif
#endif

#ifndef S_IRUSR
#  define S_IRUSR 0400
#endif
#ifndef S_IWUSR
#  define S_IWUSR 0200
#endif
#define RW_USER (S_IRUSR | S_IWUSR)  /* creation mode for open() */

#ifndef MAX_PATH_LEN
#  define MAX_PATH_LEN   1024 /* max pathname length */
#endif

#ifndef SEEK_END
#  define SEEK_END 2
#endif

#ifndef CHAR_BIT
#  define CHAR_BIT 8
#endif

#ifdef off_t
  off_t lseek OF((int fd, off_t offset, int whence));
#endif

#ifndef OFF_T_MIN
#define OFF_T_MIN (~ (off_t) 0 << (sizeof (off_t) * CHAR_BIT - 1))
#endif

#ifndef OFF_T_MAX
#define OFF_T_MAX (~ (off_t) 0 - OFF_T_MIN)
#endif

		/* global buffers */

DECLARE(uch, inbuf,  INBUFSIZ +INBUF_EXTRA);
DECLARE(uch, outbuf, OUTBUFSIZ+OUTBUF_EXTRA);
DECLARE(ush, d_buf,  DIST_BUFSIZE);
DECLARE(uch, window, 2L*WSIZE);
#ifndef MAXSEG_64K
    DECLARE(ush, tab_prefix, 1L<<BITS);
#else
    DECLARE(ush, tab_prefix0, 1L<<(BITS-1));
    DECLARE(ush, tab_prefix1, 1L<<(BITS-1));
#endif

		/* local variables */

long block_start;
unsigned strstart;      /* start of string to insert */

int to_stdout = 0;    /* output to stdout (-c) */
int decompress = 0;   /* decompress (-d) */
int force = 1;        /* don't ask questions, compress links (-f) */
int no_name = -1;     /* don't save or restore the original file name */
int no_time = -1;     /* don't save or restore the original file time */
int recursive = 0;    /* recurse through directories (-r) */
int list = 0;         /* list the file contents (-l) */
int quiet = 0;        /* be very quiet (-q) */
int do_lzw = 0;       /* generate output compatible with old compress (-Z) */
int test = 0;         /* test .gz file integrity */
int foreground;       /* set if program run in foreground */
char *progname = "gzlib";
int maxbits = BITS;   /* max bits per code for LZW */
int method = DEFLATED;/* compression method */
int level = 6;        /* compression level */
int exit_code = OK;   /* program exit code */
int last_member;      /* set for .zip and .Z files */
int part_nb;          /* number of parts in .gz file */
time_t time_stamp;      /* original time stamp (modification time) */
off_t ifile_size;      /* input file size, -1 for devices (debug only) */
char *env;            /* contents of GZIP env variable */
char **args = NULL;   /* argv pointer if GZIP env variable defined */
char *z_suffix;       /* default suffix (can be set with --suffix) */
int  z_len;           /* strlen(z_suffix) */

off_t bytes_in;             /* number of input bytes */
off_t bytes_out;            /* number of output bytes */
off_t total_in;		    /* input bytes for all files */
off_t total_out;	    /* output bytes for all files */
char ifname[MAX_PATH_LEN]; /* input file name */
char ofname[MAX_PATH_LEN]; /* output file name */
int  remove_ofname = 0;	   /* remove output file on error */
struct stat istat;         /* status for input file */
int  ifd;                  /* input file descriptor */
int  ofd;                  /* output file descriptor */
unsigned insize;           /* valid bytes in inbuf */
unsigned inptr;            /* index of next byte to be processed in inbuf */
unsigned outcnt;           /* bytes in output buffer */

/* local functions */

local int input_eof	OF((void));
local void treat_stdin  OF((void));
local int  get_method   OF((int in));
local void do_exit      OF((int exitcode));
int (*work) OF((int infile, int outfile)) = zip;

#define strequ(s1, s2) (strcmp((s1),(s2)) == 0)

local void progerror (char * string) __attribute__ ((unused));

local void progerror (string) 
     char *string; 
{
    int e = errno;
    fprintf(stderr, "%s: ", progname);
    errno = e;
    perror(string);
    exit_code = ERROR;
}

/* ======================================================================== */
int gunzip_main (int do_decompress_arg)
{
    int file_count;     /* number of files to precess */
    int proglen;        /* length of progname */
    int optc __attribute__ ((unused));           /* current option */
    int argc __attribute__ ((unused)) = 1;
    char *argv[] __attribute__ ((unused)) = { "gunzip ", NULL };

    EXPAND(argc, argv); /* wild card expansion if necessary */

    proglen = strlen(progname);

    /* Suppress .exe for MSDOS, OS/2 and VMS: */
    if (proglen > 4 && strequ(progname+proglen-4, ".exe")) {
        progname[proglen-4] = '\0';
    }

    foreground = signal(SIGINT, SIG_IGN) != SIG_IGN;
    if (foreground) {
	(void) signal (SIGINT, (sig_type)abort_gzip);
    }
#ifdef SIGTERM
    if (signal(SIGTERM, SIG_IGN) != SIG_IGN) {
	(void) signal(SIGTERM, (sig_type)abort_gzip);
    }
#endif
#ifdef SIGHUP
    if (signal(SIGHUP, SIG_IGN) != SIG_IGN) {
	(void) signal(SIGHUP,  (sig_type)abort_gzip);
    }
#endif

    if (do_decompress_arg)
	decompress = 1;

    z_suffix = Z_SUFFIX;
    z_len = strlen(z_suffix);

#ifdef SIGPIPE
    /* Ignore "Broken Pipe" message with --quiet */
    if (quiet && signal (SIGPIPE, SIG_IGN) != SIG_IGN)
      signal (SIGPIPE, (sig_type) abort_gzip);
#endif

    /* By default, save name and timestamp on compression but do not
     * restore them on decompression.
     */
    if (no_time < 0) no_time = decompress;
    if (no_name < 0) no_name = decompress;

    file_count = argc - optind;

    /* Allocate all global buffers (for DYN_ALLOC option) */
    ALLOC(uch, inbuf,  INBUFSIZ +INBUF_EXTRA);
    ALLOC(uch, outbuf, OUTBUFSIZ+OUTBUF_EXTRA);
    ALLOC(ush, d_buf,  DIST_BUFSIZE);
    ALLOC(uch, window, 2L*WSIZE);
#ifndef MAXSEG_64K
    ALLOC(ush, tab_prefix, 1L<<BITS);
#else
    ALLOC(ush, tab_prefix0, 1L<<(BITS-1));
    ALLOC(ush, tab_prefix1, 1L<<(BITS-1));
#endif

    treat_stdin();

    do_exit(exit_code);
    return exit_code; /* just to avoid lint warning */
}

/* Return nonzero when at end of file on input.  */
local int
input_eof ()
{
  if (!decompress || last_member)
    return 1;

  if (inptr == insize)
    {
      if (insize != INBUFSIZ || fill_inbuf (1) == EOF)
	return 1;

      /* Unget the char that fill_inbuf got.  */
      inptr = 0;
    }

  return 0;
}

/* ========================================================================
 * Compress or decompress stdin
 */
local void treat_stdin()
{
    strcpy(ifname, "stdin");
    strcpy(ofname, "stdout");

    /* Get the time stamp on the input file. */
    time_stamp = 0; /* time unknown by default */

    ifile_size = -1L; /* convention for unknown size */

    clear_bufs(); /* clear input and output buffers */
    to_stdout = 1;
    part_nb = 0;

    if (decompress) {
	method = get_method(ifd);
	if (method < 0) {
	    do_exit(exit_code); /* error message already emitted */
	}
    }

    /* Actually do the compression/decompression. Loop over zipped members.
     */
    for (;;) {
	if ((*work)(fileno(stdin), fileno(stdout)) != OK) return;

	if (input_eof ())
	  break;

	method = get_method(ifd);
	if (method < 0) return; /* error message already emitted */
	bytes_out = 0;            /* required for length check */
    }

}


/* ========================================================================
 * Check the magic number of the input file and update ofname if an
 * original name was given and to_stdout is not set.
 * Return the compression method, -1 for error, -2 for warning.
 * Set inptr to the offset of the next byte to be processed.
 * Updates time_stamp if there is one and --no-time is not used.
 * This function may be called repeatedly for an input file consisting
 * of several contiguous gzip'ed members.
 * IN assertions: there is at least one remaining compressed member.
 *   If the member is a zip file, it must be the only one.
 */
local int get_method(in)
    int in;        /* input file descriptor */
{
    uch flags;     /* compression flags */
    char magic[2]; /* magic header */
    int imagic1;   /* like magic[1], but can represent EOF */
    ulg stamp;     /* time stamp */

    /* If --force and --stdout, zcat == cat, so do not complain about
     * premature end of file: use try_byte instead of get_byte.
     */
    if (force && to_stdout) {
	magic[0] = (char)try_byte();
	imagic1 = try_byte ();
	magic[1] = (char) imagic1;
	/* If try_byte returned EOF, magic[1] == (char) EOF.  */
    } else {
	magic[0] = (char)get_byte();
	magic[1] = (char)get_byte();
	imagic1 = 0; /* avoid lint warning */
    }
    method = -1;                 /* unknown yet */
    part_nb++;                   /* number of parts in gzip file */
    header_bytes = 0;
    last_member = RECORD_IO;
    /* assume multiple members in gzip file except for record oriented I/O */

    if (memcmp(magic, GZIP_MAGIC, 2) == 0
        || memcmp(magic, OLD_GZIP_MAGIC, 2) == 0) {

	method = (int)get_byte();
	if (method != DEFLATED) {
	    fprintf(stderr,
		    "%s: %s: unknown method %d -- get newer version of gzip\n",
		    progname, ifname, method);
	    exit_code = ERROR;
	    return -1;
	}
	work = unzip;
	flags  = (uch)get_byte();

	stamp  = (ulg)get_byte();
	stamp |= ((ulg)get_byte()) << 8;
	stamp |= ((ulg)get_byte()) << 16;
	stamp |= ((ulg)get_byte()) << 24;
	if (stamp != 0 && !no_time) time_stamp = stamp;

	(void)get_byte();  /* Ignore extra flags for the moment */
	(void)get_byte();  /* Ignore OS type for the moment */

	if ((flags & CONTINUATION) != 0) {
	    unsigned part = (unsigned)get_byte();
	    part |= ((unsigned)get_byte())<<8;
	}
	if ((flags & EXTRA_FIELD) != 0) {
	    unsigned len = (unsigned)get_byte();
	    len |= ((unsigned)get_byte())<<8;
	    while (len--) (void)get_byte();
	}

	/* Get original file name if it was truncated */
	if ((flags & ORIG_NAME) != 0) {
	    char c; /* dummy used for NeXTstep 3.0 cc optimizer bug */
	    do {c=get_byte();} while (c != 0);
	} /* ORIG_NAME */

	/* Discard file comment if any */
	if ((flags & COMMENT) != 0) {
	    while (get_char() != 0) /* null */ ;
	}
	if (part_nb == 1) {
	    header_bytes = inptr + 2*sizeof(long); /* include crc and size */
	}

    } else if (force && to_stdout && !list) { /* pass input unchanged */
	method = STORED;
	work = copy;
        inptr = 0;
	last_member = 1;
    }
    
    if (method >= 0) return method;

    if (part_nb == 1) {
	fprintf(stderr, "\n%s: %s: not in gzip format\n", progname, ifname);
	exit_code = ERROR;
	return -1;
    } else {
	if (magic[0] == 0)
	  {
	    int inbyte;
	    for (inbyte = imagic1;  inbyte == 0;  inbyte = try_byte ())
	      continue;
	    if (inbyte == EOF)
	      {
		return -3;
	      }
	  }

	WARN((stderr, "\n%s: %s: decompression OK, trailing garbage ignored\n",
	      progname, ifname));
	return -2;
    }
}

/* ========================================================================
 * Free all dynamically allocated variables and exit with the given code.
 */
local void do_exit(exitcode)
    int exitcode;
{
    static int in_exit = 0;

    if (in_exit) exit(exitcode);
    in_exit = 1;
    if (env != NULL)  free(env),  env  = NULL;
    if (args != NULL) free((char*)args), args = NULL;
    FREE(inbuf);
    FREE(outbuf);
    FREE(d_buf);
    FREE(window);
#ifndef MAXSEG_64K
    FREE(tab_prefix);
#else
    FREE(tab_prefix0);
    FREE(tab_prefix1);
#endif
    exit(exitcode);
}

/* ========================================================================
 * Signal and error handler.
 */
RETSIGTYPE abort_gzip()
{
   if (remove_ofname) {
       close(ofd);
       unlink (ofname);
   }
   do_exit(ERROR);
}
