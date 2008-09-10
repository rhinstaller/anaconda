/*
   File name: ibft.h
   Date:      2008/09/02
   Author:    Martin Sivak

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


#ifndef __IBFT_H__
#define __IBFT_H__


int ibft_init();
int ibft_present();

int ibft_iface_dhcp();

char* ibft_iface_mac();
char* ibft_iface_ip();
char* ibft_iface_mask();
char* ibft_iface_gw();
char* ibft_iface_iface();
char* ibft_iface_dns1();
char* ibft_iface_dns2();


#endif

/* end of ibft.h */
