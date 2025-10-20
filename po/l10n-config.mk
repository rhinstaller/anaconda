#
# Copyright (C) 2023  Red Hat, Inc.
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

# What to pull from the l10n repo when getting translations
# This supports anything that git can use, but is intended to be a SHA of a commit that works.
# This line must be always in the same format, because it is changed by automation.
GIT_L10N_SHA ?= 424e128aea6da4a8f24d8429c6c237403ede8fd8

# Localization repository location
L10N_REPOSITORY ?= https://github.com/rhinstaller/anaconda-l10n.git

# Branch used in localization repository. This should be main all the time.
GIT_L10N_BRANCH ?= main
