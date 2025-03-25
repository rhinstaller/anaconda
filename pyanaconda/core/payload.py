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
from urllib.parse import quote, unquote

from pyanaconda.core.i18n import _
from pyanaconda.core.regexes import URL_PARSE
from pyanaconda.core.util import ensure_str


def parse_nfs_url(nfs_url):
    """Parse NFS URL into components.

    :param str nfs_url: The raw URL, including "nfs:"
    :return: Tuple with options, host, and path
    :rtype: (str, str, str) or None
    """
    options = ''
    host = ''
    path = ''
    if nfs_url:
        s = nfs_url.split(":")
        s.pop(0)
        if len(s) >= 3:
            (options, host, path) = s[:3]
        elif len(s) == 2:
            (host, path) = s
        else:
            host = s[0]

    return options, host, path


def create_nfs_url(host, path, options=None):
    """Compose NFS url from components.

    :param str host: NFS server
    :param str path: path on the NFS server to the shared folder
    :param options: NFS mount options
    :type options: str or None if not set
    :return: NFS url created from the components given
    :rtype: str
    """
    if host == "":
        return ""

    if options:
        return "nfs:{opts}:{server}:{path}".format(opts=options, server=host, path=path)

    return "nfs:{server}:{path}".format(server=host, path=path)


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
class ProxyString(object):
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
        self.url = ensure_str(url, keep_none=True)
        self.protocol = ensure_str(protocol, keep_none=True)
        self.host = ensure_str(host, keep_none=True)
        self.port = str(port)
        self.username = ensure_str(username, keep_none=True)
        self.password = ensure_str(password, keep_none=True)
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
            self.username = ensure_str(unquote(m.group("username")))

        if m.group("password"):
            self.password = ensure_str(unquote(m.group("password")))

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
