#include <stdarg.h>

#define _LOOSE_KERNEL_NAMES 1

#define NULL ((void *) 0)

#define	WIFSTOPPED(status)	(((status) & 0xff) == 0x7f)
#define	WIFSIGNALED(status)	(!WIFSTOPPED(status) && !WIFEXITED(status))
#define	WEXITSTATUS(status)	(((status) & 0xff00) >> 8)
#define	WTERMSIG(status)	((status) & 0x7f)
#define	WSTOPSIG(status)	WEXITSTATUS(status)
#define	WIFEXITED(status)	(WTERMSIG(status) == 0)
#define S_IFBLK			0060000

#define MS_MGC_VAL 0xc0ed0000

#define isspace(a) (a == ' ' || a == '\t')

extern char ** _environ;

extern int errno;

/* from /usr/include/bits/sigset.h */
/* A `sigset_t' has a bit for each signal.  */
#if defined(__i386__)
#define _SIGSET_NWORDS (1024 / (8 * sizeof (unsigned long int)))
typedef struct
  {
    unsigned long int __val[_SIGSET_NWORDS];
  } __sigset_t;

/* from /usr/include/signal.h */
typedef __sigset_t sigset_t;
#endif

/* Aieee, gcc 2.95+ creates a stub for posix_types.h on i386 which brings
   glibc headers in and thus makes __FD_SET etc. not defined with 2.3+ kernels. */
#define _FEATURES_H 1
#include <linux/socket.h>
#include <linux/types.h>
#include <linux/time.h>
#include <linux/if.h>
#include <linux/un.h>
#include <linux/loop.h>
#include <linux/net.h>
#include <asm/posix_types.h>
#include <asm/termios.h>
#include <asm/ioctls.h>
#include <asm/unistd.h>
#include <asm/fcntl.h>
#include <asm/signal.h>
#include <asm/stat.h>

/* x86_64 sucks and has this stuff only available to the kernel.  cheat. */
#if defined(__x86_64__)
#undef __FD_SET
static __inline__ void __FD_SET(unsigned long fd, __kernel_fd_set *fdsetp)
{
        unsigned long _tmp = fd / __NFDBITS;
        unsigned long _rem = fd % __NFDBITS;
        fdsetp->fds_bits[_tmp] |= (1UL<<_rem);
}

#undef __FD_CLR
static __inline__ void __FD_CLR(unsigned long fd, __kernel_fd_set *fdsetp)
{
        unsigned long _tmp = fd / __NFDBITS;
        unsigned long _rem = fd % __NFDBITS;
        fdsetp->fds_bits[_tmp] &= ~(1UL<<_rem);
}

#undef __FD_ISSET
static __inline__ int __FD_ISSET(unsigned long fd, __const__ __kernel_fd_set *p){
        unsigned long _tmp = fd / __NFDBITS;
        unsigned long _rem = fd % __NFDBITS;
        return (p->fds_bits[_tmp] & (1UL<<_rem)) != 0;

}

/*
 * This will unroll the loop for the normal constant cases (8 or 32 longs,
 * for 256 and 1024-bit fd_sets respectively)
 */
#undef __FD_ZERO
static __inline__ void __FD_ZERO(__kernel_fd_set *p)
{
        unsigned long *tmp = p->fds_bits;
        int i;

        if (__builtin_constant_p(__FDSET_LONGS)) {
                switch (__FDSET_LONGS) {
                        case 32:
                          tmp[ 0] = 0; tmp[ 1] = 0; tmp[ 2] = 0; tmp[ 3] = 0;
                          tmp[ 4] = 0; tmp[ 5] = 0; tmp[ 6] = 0; tmp[ 7] = 0;
                          tmp[ 8] = 0; tmp[ 9] = 0; tmp[10] = 0; tmp[11] = 0;
                          tmp[12] = 0; tmp[13] = 0; tmp[14] = 0; tmp[15] = 0;
                          tmp[16] = 0; tmp[17] = 0; tmp[18] = 0; tmp[19] = 0;
                          tmp[20] = 0; tmp[21] = 0; tmp[22] = 0; tmp[23] = 0;
                          tmp[24] = 0; tmp[25] = 0; tmp[26] = 0; tmp[27] = 0;
                          tmp[28] = 0; tmp[29] = 0; tmp[30] = 0; tmp[31] = 0;
                          return;
                        case 16:
                          tmp[ 0] = 0; tmp[ 1] = 0; tmp[ 2] = 0; tmp[ 3] = 0;
                          tmp[ 4] = 0; tmp[ 5] = 0; tmp[ 6] = 0; tmp[ 7] = 0;
                          tmp[ 8] = 0; tmp[ 9] = 0; tmp[10] = 0; tmp[11] = 0;
                          tmp[12] = 0; tmp[13] = 0; tmp[14] = 0; tmp[15] = 0;
                          return;
                        case 8:
                          tmp[ 0] = 0; tmp[ 1] = 0; tmp[ 2] = 0; tmp[ 3] = 0;
                          tmp[ 4] = 0; tmp[ 5] = 0; tmp[ 6] = 0; tmp[ 7] = 0;
                          return;
                        case 4:
                          tmp[ 0] = 0; tmp[ 1] = 0; tmp[ 2] = 0; tmp[ 3] = 0;
                          return;
                }
        }
        i = __FDSET_LONGS;
        while (i) {
                i--;
                *tmp = 0;
                tmp++;
        }
}
#endif /* x86_64 hackery */

void * alloca(size_t size);
void exit(int arg);

/* x86_64 doesn't have some old crufty syscalls */
#if defined(__x86_64__) 
#define __NR__newselect __NR_select
#define __NR_signal __NR_rt_sigaction
#endif


#ifndef MINILIBC_INTERNAL
static inline _syscall5(int,mount,const char *,spec,const char *,dir,const char *,type,unsigned long,rwflag,const void *,data);
static inline _syscall5(int,_newselect,int,n,fd_set *,rd,fd_set *,wr,fd_set *,ex,struct timeval *,timeval);
static inline _syscall4(int,wait4,pid_t,pid,int *,status,int,opts,void *,rusage)
static inline _syscall3(int,write,int,fd,const char *,buf,unsigned long,count)
static inline _syscall3(int,reboot,int,magic,int,magic_too,int,flag)
static inline _syscall3(int,execve,const char *,fn,void *,argv,void *,envp)
static inline _syscall3(int,read,int,fd,const char *,buf,unsigned long,count)
static inline _syscall3(int,open,const char *,fn,int,flags,mode_t,mode)
static inline _syscall3(int,ioctl,int,fd,int,request,void *,argp)
static inline _syscall3(int,mknod,char *,path,int,mode,short,dev)
static inline _syscall2(int,dup2,int,one,int,two)
static inline _syscall2(int,kill,pid_t,pid,int,sig)
static inline _syscall2(int,symlink,const char *,a,const char *,b)
static inline _syscall2(int,chmod,const char * ,path,mode_t,mode)
static inline _syscall2(int,sethostname,const char *,name,int,len)
static inline _syscall2(int,setdomainname,const char *,name,int,len)
static inline _syscall2(int,setpgid,int,name,int,len)
static inline _syscall2(int,signal,int,num,void *,len)
static inline _syscall2(int,stat,const char *,file,struct stat *,buf)
static inline _syscall2(int,umount2,const char *,dir,int,flags)
static inline _syscall1(int,unlink,const char *,fn)
static inline _syscall1(int,close,int,fd)
static inline _syscall1(int,swapoff,const char *,fn)
static inline _syscall1(int,umask,int,mask)
static inline _syscall0(int,getpid)
static inline _syscall0(int,getppid)
static inline _syscall0(int,sync)
#ifdef __sparc__
/* Nonstandard fork calling convention :( */
static inline int fork(void) {
  int __res;
  __asm__ __volatile__ (
    "mov %0, %%g1\n\t"
    "t 0x10\n\t"
    "bcc 1f\n\t"
    "dec %%o1\n\t"
    "sethi %%hi(%2), %%g1\n\t"
    "st %%o0, [%%g1 + %%lo(%2)]\n\t"
    "b 2f\n\t"
    "mov -1, %0\n\t"
    "1:\n\t"
    "and %%o0, %%o1, %0\n\t"
    "2:\n\t"
    : "=r" (__res)
    : "0" (__NR_fork), "i" (&errno)
    : "g1", "o0", "cc");
  return __res;
}
#else
static inline _syscall0(int,fork)
#endif
static inline _syscall0(pid_t,setsid)
static inline _syscall3(int,syslog,int, type, char *, buf, int, len);

/* socket calls don't use the socketcall multiplexor on x86_64 */
#if defined(__x86_64__)
static inline _syscall3(int,socket,int,domain,int,type,int,protocol);
static inline _syscall3(int,bind,int,sockfd,void *,addr,int,addrlen);
static inline _syscall2(int,listen,int,sockfd,int,backlog);
static inline _syscall3(int,accept,int,sockfd,void *,addr,void *,addrlen);
#endif /* x86_64 */


#else
static inline _syscall5(int,_newselect,int,n,fd_set *,rd,fd_set *,wr,fd_set *,ex,struct timeval *,timeval);
static inline _syscall3(int,write,int,fd,const char *,buf,unsigned long,count)
#if !defined(__x86_64__)
static inline _syscall2(int,socketcall,int,code,unsigned long *, args)
#endif
#define __NR__do_exit __NR_exit
extern inline _syscall1(int,_do_exit,int,exitcode)
#endif

#define select _newselect

extern int errno;

/* socket calls don't use the socketcall multiplexor on x86_64 */
#if !defined(__x86_64__)
inline int socket(int a, int b, int c);
inline int bind(int a, void * b, int c);
inline int listen(int a, int b);
inline int accept(int a, void * addr, void * addr2);
#endif


size_t strlen(const char * string);
char * strcpy(char * dst, const char * src);
void * memcpy(void * dst, const void * src, size_t count);
void sleep(int secs);
int strcmp(const char * a, const char * b);
int strncmp(const char * a, const char * b, size_t len);
void printint(int i);
void printf(char * fmt, ...);
char * strchr(char * str, int ch);
char * strncpy(char * dst, const char * src, size_t len);
int memcmp(const void *dst, const void *src, size_t count);
void* memset(void * dst, int s, size_t count);

void printstr(char * string);
