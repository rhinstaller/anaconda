#
# Copyright (C) 2020  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from collections import namedtuple
from functools import cmp_to_key
from urllib.parse import quote, unquote

import rpm

from pyanaconda.core.i18n import _
from pyanaconda.core.regexes import URL_PARSE
from pyanaconda.core.string import split_in_two

NFSUrl = namedtuple("NFSUrl", ["options", "host", "path"])
HDDUrl = namedtuple("HDDUrl", ["device", "path"])

rpm_version_key = cmp_to_key(rpm.labelCompare)  # pylint: disable=no-member


def parse_hdd_url(url):
    """Parse HDD URL into components.

    :param str url: a raw URL, including "hd:"
    :return HDDUrl: a tuple with a device and a path
    """
    # Remove the prefix.
    url = url.removeprefix("hd:")

    # Split the specified URL into two components.
    device, path = split_in_two(url, delimiter=":")

    # Return a named tuple.
    return HDDUrl(device=device, path=path)


def create_hdd_url(device, path=None):
    """Compose the HDD URL from components.

    :param str device: a device spec
    :param str path: a path or None
    """
    if not device:
        return ""

    if path:
        return ":".join(["hd", device, path])
    else:
        return ":".join(["hd", device])


def parse_nfs_url(nfs_url):
    """Parse NFS URL into components.

    :param str nfs_url: a URL with the nfs: or nfs:// prefix
    :return NFSUrl: a tuple with options, host and path
    """
    host, path, options = "", "", ""

    if nfs_url.startswith("nfs://"):
        args = nfs_url.removeprefix("nfs://").split(":")

        # Parse nfs://<server>:<path>
        if len(args) >= 2:
            host, path = args[:2]

        # Parse nfs://<server>
        elif len(args) >= 1:
            host = args[0]

    elif nfs_url.startswith("nfs:"):
        args = nfs_url.removeprefix("nfs:").split(":")

        # Parse nfs:<options>:<server>:<path>
        if len(args) >= 3:
            options, host, path = args[:3]

        # Parse nfs:<server>:<path>
        elif len(args) >= 2:
            host, path = args[:2]

        # Parse nfs:<server>
        elif len(args) >= 1:
            host = args[0]

    return NFSUrl(options=options, host=host, path=path)


def create_nfs_url(host, path, options=None):
    """Compose NFS url from components.

    :param str host: NFS server
    :param str path: path on the NFS server to the shared folder
    :param options: NFS mount options
    :type options: str or None if not set
    :return: NFS url created from the components given
    :rtype: str
    """
    if not host:
        return ""

    if options:
        return ":".join(["nfs", options, host, path])
    elif path:
        return ":".join(["nfs", host, path])
    else:
        return ":".join(["nfs", host])


def split_protocol(url):
    """Split protocol from url

    The function will look for ://.

    - If found more than once in the url then raising an error.
    - If found exactly once it will return tuple with [protocol, rest_of_url].
    - If an empty string is given it will return tuple with empty strings ("", "").

    :param str url: base url we want to split protocol from
    :return: tuple of (protocol, rest of url)
    :raise: ValueError if url is invalid
    """
    ret = url.split("://")

    if len(ret) > 2:
        raise ValueError("Invalid url to split protocol '{}'".format(url))

    if len(ret) == 2:
        # return back part removed when splitting
        return (ret[0] + "://", ret[1])

    if len(ret) == 1:
        return ("", ret[0])

    return ("", "")


class ProxyStringError(Exception):
    pass


# TODO: Add tests
class ProxyString:
    """ Handle a proxy url."""
    def __init__(self, url=None, protocol="http://", host=None, port="3128",
                 username=None, password=None):
        """ Initialize with either url
        ([protocol://][username[:password]@]host[:port]) or pass host and
        optionally:

        protocol    http, https, ftp
        host        hostname without protocol
        port        port number (defaults to 3128)
        username    username
        password    password

        The str() of the object is the full proxy url

        ProxyString.url is the full url including username:password@
        ProxyString.noauth_url is the url without username:password@
        """
        self.url = url
        self.protocol = protocol
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.proxy_auth = ""
        self.noauth_url = None

        if url:
            self.parse_url()
        elif not host:
            raise ProxyStringError(_("No host url"))
        else:
            self.parse_components()

    def parse_url(self):
        """ Parse the proxy url into its component pieces
        """
        # NOTE: If this changes, update tests/regex/proxy.py
        #
        # proxy=[protocol://][username[:password]@]host[:port][path][?query][#fragment]
        # groups (both named and numbered)
        # 1 = protocol
        # 2 = username
        # 3 = password
        # 4 = host
        # 5 = port
        # 6 = path
        # 7 = query
        # 8 = fragment
        m = URL_PARSE.match(self.url)
        if not m:
            raise ProxyStringError(_("malformed URL, cannot parse it."))

        # If no protocol was given default to http.
        self.protocol = m.group("protocol") or "http://"

        if m.group("username"):
            self.username = unquote(m.group("username"))

        if m.group("password"):
            self.password = unquote(m.group("password"))

        if m.group("host"):
            self.host = m.group("host")
            if m.group("port"):
                self.port = m.group("port")
        else:
            raise ProxyStringError(_("URL has no host component"))

        self.parse_components()

    def parse_components(self):
        """ Parse the components of a proxy url into url and noauth_url
        """
        if self.username or self.password:
            self.proxy_auth = "%s:%s@" % (quote(self.username or ""),
                                          quote(self.password or ""))

        self.url = self.protocol + self.proxy_auth + self.host + ":" + self.port
        self.noauth_url = self.protocol + self.host + ":" + self.port

    def __str__(self):
        return self.url
