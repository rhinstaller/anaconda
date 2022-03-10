# Makefile include for branch specific configuration settings
#
# Copyright (C) 2020  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Store a branch specific configuration here to avoid dealing with
# conflicts on multiple places.


# Name of the development branch. This could be master, fXX-release, rhelX-branch, rhel-X ...
GIT_BRANCH ?= rhel-8.6

# Directory for this anaconda branch in anaconda-l10n repository. This could be master, fXX, rhel-8 etc.
L10N_DIR ?= rhel-8.6
