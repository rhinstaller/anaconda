#
# tree.py - functions to build trees from lists
#
# Paul Fisher <rao@gnu.org>
#
# Copyright 1999 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# Uh.  Don't ask me what this does.  It's Paul's fault.

def build_tree (x):
    if (x == ()): return ()
    if (len (x) == 1): return (x[0],)
    else: return (x[0], build_tree (x[1:]))

def merge (a, b):
    if a == (): return build_tree (b)
    if b == (): return a
    if b[0] == a[0]:
        if len (a) > 1 and isinstance (a[1], type (())):
            return (a[0],) + (merge (a[1], b[1:]),) + a[2:]
        elif b[1:] == (): return a
        else: return (a[0],) + (build_tree (b[1:]),) + a[1:]
    else:
        return (a[0],) + merge (a[1:], b)

