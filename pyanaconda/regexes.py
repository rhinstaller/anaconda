#
# regexes.py: anaconda regular expressions
#
# Copyright (C) 2013  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): David Shea <dshea@redhat.com>
#

import re

# Validation expressions

# The full name field can contain anything except a colon.
# The empty string allowed.
GECOS_VALID = re.compile(r'^[^:]*$')

# Everyone has different ideas for what can go in a username. Here's ours:
# POSIX recommends that user and group names use only the characters within
# the portable filesystem character set (ASCII alnum plus dot, underscore,
# and hyphen), with the additional restriction that names not start with a
# hyphen. The Red Hat modification to shadow-utils starts with these rules
# and additionally allows a final $, because Samba.
#
# shadow-utils also defines length limits for names: 32 for group names,
# and UT_NAMESIZE for user names (which is defined as 32 bits/utmp.h). This
# expression captures all of that: the initial character, followed by either
# up to 30 portable characters and a dollar sign or up to 31 portable characters,
# both for a maximum total of 32. The empty string is not allowed. "root" is not
# allowed.

# a base expression without anchors, helpful for building other expressions
# If the string is the right length to match "root", use a lookback expression
# to make sure it isn't.
_USERNAME_BASE = r'[a-zA-Z0-9._](([a-zA-Z0-9._-]{0,2})|([a-zA-Z0-9._-]{3}(?<!root))|([a-zA-Z0-9._-]{4,31})|([a-zA-Z0-9._-]{,30}\$))'

USERNAME_VALID = re.compile(r'^' + _USERNAME_BASE + '$')
GROUPNAME_VALID = USERNAME_VALID

# A comma-separated list of groups, validated as in GROUPNAME_VALID
# Any number of spaces are allowed at the start and end of the list and
# before and after the commas. The empty string is allowed.
GROUPLIST_SIMPLE_VALID = re.compile(r'^\s*(' + _USERNAME_BASE + r'(\s*,\s*' + _USERNAME_BASE + r')*)?\s*$')

# Parse the <gr-name> (<gid>) strings in the group list.
#
# The name match is non-greedy so that it doesn't match the whitespace betweeen
# the name and ID.
#
# There's some non-capturing groups ("clusters" in the perlre parlance) thrown
# in there, and, haha, wow, that's confusing to look at. There are two groups
# that actually end up in the match object, and they're named to try to make
# it a little easier: the first is "name", and the second is "gid".
#
# EVERY STRING IS MATCHED. This expression cannot be used for validation.
# If there is no GID, or the GID contains non-digits, everything except
# leading or trailing whitespace ends up in the name group. The result needs to
# be validated with GROUPNAME_VALID.
GROUPLIST_FANCY_PARSE = re.compile(r'^(?:\s*)(?P<name>.*?)\s*(?:\((?P<gid>\d+)\))?(?:\s*)$')

# IPv4 address without anchors
IPV4_PATTERN_WITHOUT_ANCHORS = r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'

# Hostname validation
# A hostname consists of sections separated by periods. Each of these sections
# must be between 1 and 63 characters, contain only alphanumeric characters or
# hyphens, and may not start or end with a hyphen. The whole string cannot start
# with a period, but it can end with one.
# This regex uses negative lookahead and lookback assertions to enforce the
# hyphen rules and make it way more confusing
HOSTNAME_PATTERN_WITHOUT_ANCHORS = r'(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?)'

# Matches the "scheme" defined by RFC 3986
URL_SCHEME_PATTERN_WITHOUT_ANCHORS = r'[A-Za-z][A-Za-z0-9+.-]*'

# Matches any unreserved or percent-encoded character
URL_NORMAL_CHAR = r'[A-Za-z0-9._~-]|(?:%[0-9A-Fa-f]{2})'

# The above but also matches 'sub-delims' and :, @ and /
URL_PATH_CHAR = URL_NORMAL_CHAR + "|[!$&'()*+,;=:@/]"

# Valid characters for repository names
REPO_NAME_VALID = re.compile(r'^[a-zA-Z0-9_.:-]+$')

# Product Version string, just the starting numbers like 21 or 21.1
VERSION_DIGITS = r'([\d.]+)'


#Regexes to validate iSCSI Names according to RFC 3720 and RFC 3721
#The conditions for iSCSI name used in the following regexes are
#(https://tools.ietf.org/html/rfc3720#section-3.2.6.3.1 , https://tools.ietf.org/html/rfc3721#page-5 and http://standards.ieee.org/regauth/oui/tutorials/EUI64.html):
#1. For iqn format:
#    a. Starts with string 'iqn.'
#    b. A date code specifying the year and month in which the organization
#       registered the domain or sub-domain name used as the naming authority
#       string. "yyyy-mm"
#    c. A dot (".")
#    d. The organizational naming authority string, which consists of a
#       valid, reversed domain or subdomain name.
#    e. Optionally, a colon (":"), followed by a string of the assigning
#       organization's choosing, which must make each assigned iSCSI name
#       unique. With the exception of the colon prefix, the owner of the domain
#       name can assign everything after the reversed domain name as desired.
ISCSI_IQN_NAME_REGEX = re.compile(r'^iqn\.\d{4}-\d{2}((?<!-)\.(?!-)[a-zA-Z0-9\-]+){1,63}(?<!-)(?<!\.)(:[^:]+)?$')

#2. For eui format:
#    a. The format is "eui." followed by an EUI-64 identifier (16 ASCII-encoded hexadecimal digits).
ISCSI_EUI_NAME_REGEX = re.compile(r'^eui\.[a-fA-F0-9]{16}$')
