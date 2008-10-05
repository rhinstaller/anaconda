/*
   File name: ibft.c
   Date:      2008/09/02
   Author:    Martin Sivak <msivak@redhat.com>

   Copyright (C) 2008 Red Hat

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation; either version 2 of the
   License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   General Public License for more details.

   You should have received a copy of the GNU General Public License
   in a file called COPYING along with this program; if not, write to
   the Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA
   02139, USA.
*/


#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include <fw_context.h>
extern int fwparam_ibft_sysfs(struct boot_context *context, const char *filepath);

#include "ibft.h"

struct boot_context ibft_context;
int ibft_ispresent = 0;
int ibft_initialized = 0;

int ibft_init(void)
{
  int ret;

  memset(&ibft_context, 0, sizeof(ibft_context));

  ret = fwparam_ibft_sysfs(&ibft_context, NULL);

  /* ret == 0 -> OK */
  ibft_ispresent = !ret;
  ibft_initialized = 1;

  return ibft_initialized;
}

/* Is iBFT available on this system */
int ibft_present()
{
  if(!ibft_initialized)
    ibft_init();

  return ibft_ispresent;
}

/* Is the iBFT network configured to use DHCP */
int ibft_iface_dhcp()
{
  if(!ibft_initialized)
    ibft_init();

  if(!ibft_present())
    return -1;

  return (ibft_context.dhcp!=NULL && strlen(ibft_context.dhcp) && strcmp(ibft_context.dhcp, "0.0.0.0"));
}

#define ibft_iface_charfunc(name, var) char* ibft_iface_##name()\
{\
  if(!ibft_initialized)\
    ibft_init();\
\
  if(!ibft_present())\
    return NULL;\
\
  if(ibft_context.var==NULL)\
    return NULL;\
\
  if(!strlen(ibft_context.var))\
    return NULL;\
\
  return ibft_context.var;\
}


/* Get the iBFT MAC address */
ibft_iface_charfunc(mac, mac)

/* Get the iBFT ip address */
ibft_iface_charfunc(ip, ipaddr)

/* Get the iBFT subnet mask */
ibft_iface_charfunc(mask, mask)

/* Get the iBFT gateway */
ibft_iface_charfunc(gw, gateway)

/* Get the iBFT iface name */
ibft_iface_charfunc(iface, iface)

/* Get the iBFT dns servers */
ibft_iface_charfunc(dns1, primary_dns)
ibft_iface_charfunc(dns2, secondary_dns)

