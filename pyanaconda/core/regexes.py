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
# and additionally allows a final $, because Samba. It doesn't allow fully
# numeric names or just "." or "..".
#
# shadow-utils also defines length limits for names: 32 for group names,
# and UT_NAMESIZE for user names (which is defined as 32 bits/utmp.h). This
# expression captures all of that: the initial character, followed by either
# up to 30 portable characters and a dollar sign or up to 31 portable characters,
# both for a maximum total of 32. The empty string is not allowed.

PORTABLE_FS_CHARS = r'a-zA-Z0-9._-'
_NAME_BASE = r'[a-zA-Z0-9._][' + PORTABLE_FS_CHARS + r']{0,30}([' + PORTABLE_FS_CHARS + r']|\$)?'

# A regex for user and group names.
NAME_VALID = re.compile(r'^' + _NAME_BASE + '$')

# A comma-separated list of groups, validated as in NAME_VALID
# Any number of spaces are allowed at the start and end of the list and
# before and after the commas. The empty string is allowed.
GROUPLIST_SIMPLE_VALID = re.compile(r'^\s*(' + _NAME_BASE + r'(\s*,\s*' + _NAME_BASE + r')*)?\s*$')

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
# be validated with NAME_VALID.
GROUPLIST_FANCY_PARSE = re.compile(r'^(?:\s*)(?P<name>.*?)\s*(?:\((?P<gid>\d+)\))?(?:\s*)$')

# IPv4 address without anchors
IPV4_PATTERN_WITHOUT_ANCHORS = r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'

IPV4_PATTERN_WITH_ANCHORS = re.compile("^" + IPV4_PATTERN_WITHOUT_ANCHORS + "$")

# IPv4 address or dhcp with anchors
IPV4_OR_DHCP_PATTERN_WITH_ANCHORS = re.compile("^(?:" + IPV4_PATTERN_WITHOUT_ANCHORS + "|dhcp)$")

# IPv6 address without anchors
# Adapted from the IPv6address ABNF definition in RFC 3986, so it has all those
# IPv4 compatibility bits too. All groups are non-capturing to make it easy to
# use in an expression with groups and completely impossible to read
IPV6_PATTERN_WITHOUT_ANCHORS = r'(?:' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){6})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:::(?:(?:[0-9a-fA-F]{1,4}:){5})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:[0-9a-fA-F]{1,4})?::(?:(?:[0-9a-fA-F]{1,4}:){4})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,1}(?:[0-9a-fA-F]{1,4}))?::(?:(?:[0-9a-fA-F]{1,4}:){3})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,2}(?:[0-9a-fA-F]{1,4}))?::(?:(?:[0-9a-fA-F]{1,4}:){2})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,3}(?:[0-9a-fA-F]{1,4}))?::(?:(?:[0-9a-fA-F]{1,4}:){1})(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,4}(?:[0-9a-fA-F]{1,4}))?::(?:(?:(?:[0-9a-fA-F]{1,4}):(?:[0-9a-fA-F]{1,4}))|(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,5}(?:[0-9a-fA-F]{1,4}))?::(?:[0-9a-fA-F]{1,4}))|' + \
                               r'(?:(?:(?:[0-9a-fA-F]{1,4}:){,6}(?:[0-9a-fA-F]{1,4}))?::)' + \
                               r')'

# IPv4 dotted-quad netmask validation
IPV4_NETMASK_WITHOUT_ANCHORS = r'((128|192|224|240|248|252|254)\.0\.0\.0)|(255\.(((0|128|192|224|240|248|252|254)\.0\.0)|(255\.(((0|128|192|224|240|248|252|254)\.0)|255\.(0|128|192|224|240|248|252|254)))))'

# IPv4 netmask with anchors
IPV4_NETMASK_WITH_ANCHORS = re.compile("^" + IPV4_NETMASK_WITHOUT_ANCHORS + "$")

# Hostname validation
# A hostname consists of sections separated by periods. Each of these sections
# must be between 1 and 63 characters, contain only alphanumeric characters or
# hyphens, and may not start or end with a hyphen. The whole string cannot start
# with a period, but it can end with one.
# This regex uses negative lookahead and lookback assertions to enforce the
# hyphen rules and make it way more confusing
HOSTNAME_PATTERN_WITHOUT_ANCHORS = r'(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?)'

# URL Hostname
# This matches any hostname, IPv4 literal or properly encased IPv6 literal
# This does not match the "IPvFuture" form because come the hell on
URL_HOSTNAME_PATTERN_WITHOUT_ANCHORS = r'(?:' + IPV4_PATTERN_WITHOUT_ANCHORS + r')|(?:\[' + IPV6_PATTERN_WITHOUT_ANCHORS + r'])|(?:' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + ')'

# Matches the "scheme" defined by RFC 3986
URL_SCHEME_PATTERN_WITHOUT_ANCHORS = r'[A-Za-z][A-Za-z0-9+.-]*'

# Matches any unreserved or percent-encoded character
URL_NORMAL_CHAR = r'[A-Za-z0-9._~-]|(?:%[0-9A-Fa-f]{2})'

# The above but also matches 'sub-delims' and :, @ and /
URL_PATH_CHAR = URL_NORMAL_CHAR + "|[!$&'()*+,;=:@/]"

# Parse a URL
# Parses a URL of the form [protocol://][username[:password]@]host[:port][path][?query][#fragment]
# into the following named groups:
#   1: protocol (e.g., http://)
#   2: username
#   3: password
#   4: host
#   5: port
#   6: path
#   7: query
#   8: fragment
URL_PARSE = re.compile(r'^(?P<protocol>' + URL_SCHEME_PATTERN_WITHOUT_ANCHORS + r'://)?' +
                       r'(?:(?P<username>(?:' + URL_NORMAL_CHAR + r')*)(?::(?P<password>(?:' + URL_NORMAL_CHAR + r')*))?@)?' +
                       r'(?P<host>' + URL_HOSTNAME_PATTERN_WITHOUT_ANCHORS + ')' +
                       r'(?::(?P<port>[0-9]+))?' +
                       r'(?P<path>/(?:' + URL_PATH_CHAR + r')*)?' +
                       r'(?:\?(?P<query>(?:' + URL_PATH_CHAR + r'|\?)*))?' +
                       r'(?:#(?P<fragment>(?:' + URL_PATH_CHAR + r'|\?)*))?$')


# Valid characters for repository names
REPO_NAME_VALID = re.compile(r'^[a-zA-Z0-9_.:-]+$')

# Product Version string, just the starting numbers like 21 or 21.1
VERSION_DIGITS = re.compile(r'([\d.]+)')

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
ISCSI_IQN_NAME_REGEX = re.compile(r'^iqn\.\d{4}-\d{2}((?<!-)\.(?!-)[a-zA-Z0-9\-]+){1,63}(?<!-)(?<!\.)(:[\S]+)?$')

#2. For eui format:
#    a. The format is "eui." followed by an EUI-64 identifier (16 ASCII-encoded hexadecimal digits).
ISCSI_EUI_NAME_REGEX = re.compile(r'^eui\.[a-fA-F0-9]{16}$')

# Device with this name was configured from ibft (and renamed) by dracut
IBFT_CONFIGURED_DEVICE_NAME = re.compile(r'^ibft\d+$')

# Regex to validate a DASD device number (full or partial).
#
# A DASD number has the format n.n.hhhh, where n is any decimal
# digit and h any hexadecimal digit, e.g., 0.0.abcd, 0.0.002A.
#
# The partial form of the DASD number is missing hexadecimal digits,
# e.g., 0.0.b, or missing a bus number, e.g., 0012. The minimal
# partial number contains a single digit. For example a.
DASD_DEVICE_NUMBER = re.compile(r'^(?:[0-9]\.[0-9]\.|\.|)[0-9A-Fa-f]{1,4}$')

# Regex to validate the Logical Unit Number (LUN).
# The LUN is a 16 digit hexadecimal value padded with zeroes to the right,
# for example 0x4010403300000000.
ZFCP_LUN_NUMBER = re.compile(r'^(?:0x|)[0-9A-Fa-f]{1,16}$')

# Regex to validate the Worldwide Port Name (WWPN).
# The WWPN is a 16 digit hexadecimal number prefixed with 0x,
# for example 0x5005076303000104.
ZFCP_WWPN_NUMBER = re.compile(r'^(?:0x|)[0-9A-Fa-f]{16}$')

# IPv6 address in dracut IP option (including the square brackets)
IPV6_ADDRESS_IN_DRACUT_IP_OPTION = re.compile(r'\[[^\]]+\]')

# Octet of MAC address
MAC_OCTET = re.compile(r'[a-fA-F0-9][a-fA-F0-9]')

# Name of initramfs connection created by NM based on MAC
NM_MAC_INITRAMFS_CONNECTION = re.compile(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$')

# Screen resolution format for the boot option "inst.resolution"
SCREEN_RESOLUTION_CONFIG = re.compile(r'^[0-9]+x[0-9]+$')
