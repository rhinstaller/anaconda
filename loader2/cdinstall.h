/*
 * cdinstall.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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

#ifndef H_CDINSTALL
#define H_CDINSTALL

#include "method.h"

char * mountCdromImage(struct installMethod * method,
                       char * location, struct loaderData_s * loaderData);

char * findAnacondaCD(char * location);

void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv);

int kickstartFromCD(char *kssrc);
#endif
