/*
 * mem.h
 *
 * Copyright (C) 2010
 * Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef _MEM_H_
#define _MEM_H_

#if defined(__powerpc64__) || defined(__sparc__)
  #define MIN_RAM                 1024*1024 // 1 GB
  #define GUI_INSTALL_EXTRA_RAM   512*1024  // 512 MB
#else
  #define MIN_RAM                 640 * 1024 // 640 MB
  #define GUI_INSTALL_EXTRA_RAM   0 * 1024 // 0 MB
#endif
#define MIN_GUI_RAM             MIN_RAM + GUI_INSTALL_EXTRA_RAM
#define EARLY_SWAP_RAM          1152 * 1024 // 1152 MB

int totalMemory(void);

#endif /* _MEM_H_ */
