#ifndef SELINUX_H
#define SELINUX_H

int setexeccon(char * context);
int loadpolicy();

#define ANACONDA_CONTEXT "system_u:object_r:anaconda_t"

#endif
