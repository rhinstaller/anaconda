# controlunits.sh: define some common control unit mappings
# Copyright (C) IBM Corp. 2009
# Author: Steffen Maier <maier@de.ibm.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License only.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# The arrays (among other things) should be adapted, if any of those device
# drivers start supporting different CU types/models.

readonly -a CU=(
    1731/01
    1731/05
    3088/08
    3088/1f
    3088/1e
    3088/01
    3088/60
    3088/61
)

readonly -a CU_DEVDRV=(
    qeth
    qeth
    ctcm
    ctcm
    ctcm
    lcs
    lcs
    lcs
)

# Searches for a match of argument 1 on the array $CU and sets $cu_idx
# to the matched array index on success.
# Returns 0 on success, 1 on failure.
function search_cu() {
    local scu=$1
    local i
    for ((i=0; i < ${#CU[@]}; i++)); do
        if [ "$scu" == "${CU[i]}" ]; then
            cu_idx=$i
            return 0
        fi
    done
    return 1
}
