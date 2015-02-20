#
# regexcheck.py: check a regular expression against lists of matching and non-matching strings
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Author: David Shea <dshea@redhat.com>

def regex_match(expression, goodlist, badlist):
    """ Check that a regular expression matches and does not match lists of strings.

        This method will print a message for any failure and return a a bool
        to indicate whether the testcase passed.

        :param expression: a compiled regular expression object
        :param goodlist: a list of strings expected to be matched by expression
        :param badlist: a list of strings expected not to be matched by expression
        :returns: True if all strings in the lists matched or did not match as expected
        :rtype: bool
    """

    success = True

    for good in goodlist:
        if expression.match(good) is None:
            success = False
            print("Good string %s did not match expression" % good)

    for bad in badlist:
        if expression.match(bad) is not None:
            success = False
            print("Bad string %s matched expression" % bad)

    return success

def regex_group(expression, test_cases):
    """ Check that a regex parses strings into expected groups.

        Test cases is a list of tuples of the form (test_string, expected_result)
        where expected_result is the groups tuples that should be returned by
        regex.match.

        :param expression: a compiled expression object
        :param test_cases: a list of test strings and expected results
        :returns: True if all test cases return the expected groups
        :rtype: bool
    """

    success = True
    for test_str, result in test_cases:
        match = expression.match(test_str)
        if match is not None:
            match = match.groups()

        if match != result:
            print("Test case `%s' did not parse as `%s': %s" % (test_str, result, match))
            success = False

    return success
