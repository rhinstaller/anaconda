/*
 * udelay.h -- udelay and other time related functions.
 *
 * Peter Jones (pjones@redhat.com)
 *
 * Copyright 2006-2007 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License, version 2.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#ifndef UDELAY_H
#define UDELAY_H 1

#include <sys/types.h>
#include <sys/param.h>
#include <sys/time.h>
#include <time.h>

#define USECS_PER_SEC 1000000LL
#define NSECS_PER_USEC 1000LL
#define NSECS_PER_SEC (NSECS_PER_USEC * USECS_PER_SEC)

static inline void
nsectospec(long long nsecs, struct timespec *ts)
{
    if (nsecs < 0) {
        ts->tv_sec = -1;
        ts->tv_nsec = -1;
        return;
    }
    ts->tv_sec = nsecs / NSECS_PER_SEC;
    ts->tv_nsec = (nsecs % NSECS_PER_SEC);
}

static inline void
usectospec(long long usecs, struct timespec *ts)
{
    if (usecs > 0 && LLONG_MAX / NSECS_PER_USEC > usecs)
        usecs *= NSECS_PER_USEC;
    
    nsectospec(usecs, ts);
}

static inline int
speczero(struct timespec *ts)
{
    return (ts->tv_sec == 0 && ts->tv_nsec == 0);
}

static inline int
specinf(struct timespec *ts)
{
    return (ts->tv_sec < 0 || ts->tv_nsec < 0);
}

static inline long long
spectonsec(struct timespec *ts)
{
    long long nsecs = 0;
    if (specinf(ts))
        return -1;
    
    nsecs = ts->tv_sec * NSECS_PER_SEC;
    nsecs += ts->tv_nsec;
    return nsecs;
}

static inline long long
spectousec(struct timespec *ts)
{
    long long usecs = spectonsec(ts);

    return usecs < 0 ? usecs : usecs / NSECS_PER_USEC;
}

static inline int
gettimespecofday(struct timespec *ts)
{
    struct timeval tv = {0, 0};
    int rc;

    rc = gettimeofday(&tv, NULL);
    if (rc >= 0) {
        ts->tv_sec = tv.tv_sec;
#if 0
        ts->tv_nsec = (tv.tv_usec % NSECS_PER_USEC >= NSECS_PER_USEC / 2) ?
            tv.tv_usec / NSECS_PER_USEC + 1 :
            tv.tv_usec / NSECS_PER_USEC;
#else
        ts->tv_nsec = tv.tv_usec / NSECS_PER_USEC;
#endif
    }
    return rc;
}

/* minuend minus subtrahend equals difference */
static inline void
tssub(struct timespec *minuend, struct timespec *subtrahend,
      struct timespec *difference)
{
    long long m, s, d;

    m = spectonsec(minuend);
    s = spectonsec(subtrahend);

    if (s < 0) {
        d = 0;
    } else if (m < 0) {
        d = -1;
    } else {
        m -= s;
        d = m < 0 ? 0 : m;
    }

    nsectospec(d, difference);
    return;
}

static inline void
tsadd(struct timespec *augend, struct timespec *addend, struct timespec *sum)
{
    long long aug, add;

    aug = spectonsec(augend);
    add = spectonsec(addend);

//    printf("aug: %Ld add: %Ld\n", aug, add);

    if (aug < 0 || add < 0)
        nsectospec(-1, sum);
    else if (LLONG_MAX - MAX(add,aug) < MAX(add,aug))
        nsectospec(LLONG_MAX, sum);
    else
        nsectospec(aug+add, sum);
    return;
}

#define tsGT(x,y) (tscmp((x), (y)) < 0)
#define tsGE(x,y) (tscmp((x), (y)) <= 0)
#define tsET(x,y) (tscmp((x), (y)) == 0)
#define tsNE(x,y) (tscmp((x), (y)) != 0)
#define tsLE(x,y) (tscmp((x), (y)) >= 0)
#define tsLT(x,y) (tscmp((x), (y)) > 0)

static inline int
tscmp(struct timespec *a, struct timespec *b)
{
    long long m, s;
    long long rc;

    m = spectonsec(a);
    s = spectonsec(b);

    if (s < 0) {
        rc = 1;
        if (m < 0)
            rc = 0;
    } else if (m < 0) {
        rc = -1;
    } else {
        rc = MIN(MAX(s-m, -1), 1);
    }

    return rc;
}

static inline void
udelayspec(struct timespec total)
{
    struct timespec rem;
    if (specinf(&total)) {
        do {
            usectospec(LLONG_MAX, &rem);
        } while (nanosleep(&rem, &rem) == -1 && errno == EINTR);
    } else {
        rem = total;
        while (nanosleep(&rem, &rem) == -1 && errno == EINTR)
            ;
    }
}

static inline void
udelay(long long usecs)
{
    struct timespec rem = {0,0};

    usectospec(usecs, &rem);
    udelayspec(rem);
}

#endif /* UDELAY_H */
/*
 * vim:ts=8:sw=4:sts=4:et
 */
