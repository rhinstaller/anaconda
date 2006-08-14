#ifndef SELINUX_H
#define SELINUX_H

int loadpolicy();

#define ANACONDA_CONTEXT "system_u:system_r:anaconda_t:s0"

#endif
