#!/usr/bin/python
# tsort.py
# Topological sorting.
#
# Copyright (C) 2010  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

class CyclicGraphError(Exception):
    pass

def tsort(graph):
    order = []  # sorted list of items

    if not graph or not graph['items']:
        return order

    # determine which nodes have no incoming edges
    roots = [n for n in graph['items'] if graph['incoming'][n] == 0]
    if not roots:
        raise CyclicGraphError("no root nodes")

    visited = []    # list of nodes visited, for cycle detection
    while roots:
        # remove a root, add it to the order
        root = roots.pop()
        if root in visited:
            raise CyclicGraphError("graph contains cycles")

        visited.append(root)
        i = graph['items'].index(root)
        order.append(root)
        # remove each edge from the root to another node
        for (parent, child) in [e for e in graph['edges'] if e[0] == root]:
            graph['incoming'][child] -= 1
            graph['edges'].remove((parent, child))
            # if destination node is now a root, add it to roots
            if graph['incoming'][child] == 0:
                roots.append(child)

    if len(graph['items']) != len(visited):
        raise CyclicGraphError("graph contains cycles")


    return order

def create_graph(items, edges):
    """ Create a graph based on a list of items and a list of edges.

        Arguments:

            items   -   an iterable containing (hashable) items to sort
            edges   -   an iterable containing (parent, child) edge pair tuples

        Return Value:

            The return value is a dictionary representing the directed graph.
            It has three keys:

                items is the same as the input argument of the same name
                edges is the same as the input argument of the same name
                incoming is a dict of incoming edge count hashed by item

    """
    graph = {'items': [],       # the items to sort
             'edges': [],       # partial order info: (parent, child) pairs
             'incoming': {}}    # incoming edge count for each item

    graph['items'] = items
    graph['edges'] = edges
    for item in items:
        graph['incoming'][item] = 0

    for (parent, child) in edges:
        graph['incoming'][child] += 1

    return graph 


if __name__ == "__main__":

    items = [5, 2, 3, 4, 1]
    edges = [(1, 2), (2, 4), (4, 5), (3, 2)]

    print items
    print edges

    graph = create_graph(items, edges)
    print tsort(graph)

