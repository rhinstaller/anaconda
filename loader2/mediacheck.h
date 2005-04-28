#ifndef MEDIACHECK_H
#define MEDIACHECK_H

/* simple program to check implanted md5sum in an iso 9660 image   */
/* Copyright 2001 Red Hat, Inc.                                    */
/* Michael Fulbright msf@redhat.com                                */

/* Length in characters of string used for fragment md5sum checking */
#define FRAGMENT_SUM_LENGTH 60

int mediaCheckFile(char *file, char *descr);
int parsepvd(int isofd, char *mediasum, int *skipsectors, long long *isosize, int *supported, char *fragmentsums, long long *fragmentcount);

#endif
