# -*- coding: utf-8 -*-
#
# network.py - network configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
#               2008, 2009
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
# Author(s): Matt Wilson <ewt@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Brent Fox <bfox@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#            Radek Vykydal <rvykydal@redhat.com>

import shutil
from pyanaconda import iutil
from pyanaconda.iutil import open   # pylint: disable=redefined-builtin
import socket
import os
import time
import threading
import re
import dbus
import IPy
import random
from uuid import uuid4
import itertools

from pyanaconda.simpleconfig import SimpleConfigFile
from blivet.devices import FcoeDiskDevice, iScsiDiskDevice
import blivet.arch

from pyanaconda import nm
from pyanaconda import constants
from pyanaconda.flags import flags, can_touch_runtime_system
from pyanaconda.i18n import _
from pyanaconda.regexes import HOSTNAME_PATTERN_WITHOUT_ANCHORS

from gi.repository import NetworkManager

import logging
log = logging.getLogger("anaconda")

sysconfigDir = "/etc/sysconfig"
netscriptsDir = "%s/network-scripts" % (sysconfigDir)
networkConfFile = "%s/network" % (sysconfigDir)
hostnameFile = "/etc/hostname"
ipv6ConfFile = "/etc/sysctl.d/anaconda.conf"
ifcfgLogFile = "/tmp/ifcfg.log"
DEFAULT_HOSTNAME = "localhost.localdomain"

ifcfglog = None

network_connected = None
network_connected_condition = threading.Condition()

def setup_ifcfg_log():
    # Setup special logging for ifcfg NM interface
    from pyanaconda import anaconda_log
    global ifcfglog
    logger = logging.getLogger("ifcfg")
    logger.setLevel(logging.DEBUG)
    anaconda_log.logger.addFileHandler(ifcfgLogFile, logger, logging.DEBUG)
    anaconda_log.logger.forwardToSyslog(logger)

    ifcfglog = logging.getLogger("ifcfg")

def check_ip_address(address, version=None):
    try:
        _ip, ver = IPy.parseAddress(address)
    except ValueError:
        return False
    if version and version == ver:
        return True
    elif not version:
        return True
    else:
        return False

def sanityCheckHostname(hostname):
    """
    Check if the given string is (syntactically) a valid hostname.

    :param hostname: a string to check
    :returns: a pair containing boolean value (valid or invalid) and
              an error message (if applicable)
    :rtype: (bool, str)

    """

    if not hostname:
        return (False, _("Host name cannot be None or an empty string."))

    if len(hostname) > 255:
        return (False, _("Host name must be 255 or fewer characters in length."))

    if not (re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', hostname)):
        return (False, _("Host names can only contain the characters 'a-z', "
                         "'A-Z', '0-9', '-', or '.', parts between periods "
                         "must contain something and cannot start or end with "
                         "'-'."))

    return (True, "")

# Return a list of IP addresses for all active devices.
def getIPs():
    ipv4_addresses = []
    ipv6_addresses = []
    for devname in nm.nm_activated_devices():
        try:
            ipv4_addresses += nm.nm_device_ip_addresses(devname, version=4)
            ipv6_addresses += nm.nm_device_ip_addresses(devname, version=6)
        except (dbus.DBusException, ValueError) as e:
            log.warning("Got an exception trying to get the ip addr "
                        "of %s: %s", devname, e)
    # prefer IPv4 addresses to IPv6 addresses
    return ipv4_addresses + ipv6_addresses

# Return the first real non-local IP we find
def getFirstRealIP():
    for ip in getIPs():
        if ip not in ("127.0.0.1", "::1"):
            return ip
    return None

def netmask2prefix(netmask):
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix

def prefix2netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    _bytes = []
    for _i in range(4):
        if prefix >= 8:
            _bytes.append(255)
            prefix -= 8
        else:
            _bytes.append(256 - 2**(8-prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask

def generateRandomHostname():
    # Word list taken from the Docker.io project:
    # https://github.com/docker/docker/blob/3fa2ddc452953e0695eda7cda191358010866c7e/pkg/namesgenerator/names-generator.go
    # Some adjectives dropped to avoid potential negative reception.

    domains = [
        "admiring",
        "adoring",
        "agitated",
        "boring",
        "clever",
        "compassionate",
        "determined",
        "distracted",
        "dreamy",
        "ecstatic",
        "elated",
        "elegant",
        "fervent",
        "focused",
        "furious",
        "goofy",
        "grave",
        "happy",
        "high",
        "hopeful",
        "hungry",
        "jolly",
        "jovial",
        "lonely",
        "loving",
        "mad",
        "modest",
        "nostalgic",
        "pensive",
        "prickly",
        "reverent",
        "romantic",
        "serene",
        "sharp",
        "silly",
        "sleepy",
        "stoic",
        "stupefied",
        "tender",
        "thirsty",
        "trusting"
    ]

    domainname = random.choice(domains)

    hostnames = [
        # Muhammad ibn Jābir al-Ḥarrānī al-Battānī was a founding father of astronomy. https://en.wikipedia.org/wiki/Mu%E1%B8%A5ammad_ibn_J%C4%81bir_al-%E1%B8%A4arr%C4%81n%C4%AB_al-Batt%C4%81n%C4%AB
        "albattani",

        # June Almeida - Scottish virologist who took the first pictures of the rubella virus - https://en.wikipedia.org/wiki/June_Almeida
        "almeida",

        # Archimedes was a physicist, engineer and mathematician who invented too many things to list them here. https://en.wikipedia.org/wiki/Archimedes
        "archimedes",

        # Maria Ardinghelli - Italian translator, mathematician and physicist - https://en.wikipedia.org/wiki/Maria_Ardinghelli
        "ardinghelli",

        # Charles Babbage invented the concept of a programmable computer. https://en.wikipedia.org/wiki/Charles_Babbage.
        "babbage",

        # Stefan Banach - Polish mathematician, was one of the founders of modern functional analysis. https://en.wikipedia.org/wiki/Stefan_Banach
        "banach",

        # William Shockley, Walter Houser Brattain and John Bardeen co-invented the transistor (thanks Brian Goff).
        # - https://en.wikipedia.org/wiki/John_Bardeen
        # - https://en.wikipedia.org/wiki/Walter_Houser_Brattain
        # - https://en.wikipedia.org/wiki/William_Shockley
        "bardeen",
        "brattain",
        "shockley",

        # Jean Bartik, born Betty Jean Jennings, was one of the original programmers for the ENIAC computer. https://en.wikipedia.org/wiki/Jean_Bartik
        "bartik",

        # Alexander Graham Bell - an eminent Scottish-born scientist, inventor, engineer and innovator who is credited with inventing the first practical telephone - https://en.wikipedia.org/wiki/Alexander_Graham_Bell
        "bell",

        # Elizabeth Blackwell - American doctor and first American woman to receive a medical degree - https://en.wikipedia.org/wiki/Elizabeth_Blackwell
        "blackwell",

        # Niels Bohr is the father of quantum theory. https://en.wikipedia.org/wiki/Niels_Bohr.
        "bohr",

        # Satyendra Nath Bose - He provided the foundation for Bose–Einstein statistics and the theory of the Bose–Einstein condensate. - https://en.wikipedia.org/wiki/Satyendra_Nath_Bose
        "bose",

        # Emmett Brown invented time travel. https://en.wikipedia.org/wiki/Emmett_Brown (thanks Brian Goff)
        "brown",

        # Rachel Carson - American marine biologist and conservationist, her book Silent Spring and other writings are credited with advancing the global environmental movement. https://en.wikipedia.org/wiki/Rachel_Carson
        "carson",

        # Subrahmanyan Chandrasekhar - Astrophysicist known for his mathematical theory on different stages and evolution in structures of the stars. He has won nobel prize for physics - https://en.wikipedia.org/wiki/Subrahmanyan_Chandrasekhar
        "chandrasekhar",

        # Jane Colden - American botanist widely considered the first female American botanist - https://en.wikipedia.org/wiki/Jane_Colden
        "colden",

        # Gerty Theresa Cori - American biochemist who became the third woman—and first American woman—to win a Nobel Prize in science, and the first woman to be awarded the Nobel Prize in Physiology or Medicine. Cori was born in Prague. https://en.wikipedia.org/wiki/Gerty_Cori
        "cori",

        # Seymour Roger Cray was an American electrical engineer and supercomputer architect who designed a series of computers that were the fastest in the world for decades. https://en.wikipedia.org/wiki/Seymour_Cray
        "cray",

        # Marie Curie discovered radioactivity. https://en.wikipedia.org/wiki/Marie_Curie.
        "curie",

        # Charles Darwin established the principles of natural evolution. https://en.wikipedia.org/wiki/Charles_Darwin.
        "darwin",

        # Leonardo Da Vinci invented too many things to list here. https://en.wikipedia.org/wiki/Leonardo_da_Vinci.
        "davinci",

        # Albert Einstein invented the general theory of relativity. https://en.wikipedia.org/wiki/Albert_Einstein
        "einstein",

        # Gertrude Elion - American biochemist, pharmacologist and the 1988 recipient of the Nobel Prize in Medicine - https://en.wikipedia.org/wiki/Gertrude_Elion
        "elion",

        # Douglas Engelbart gave the mother of all demos: https://en.wikipedia.org/wiki/Douglas_Engelbart
        "engelbart",

        # Euclid invented geometry. https://en.wikipedia.org/wiki/Euclid
        "euclid",

        # Pierre de Fermat pioneered several aspects of modern mathematics. https://en.wikipedia.org/wiki/Pierre_de_Fermat
        "fermat",

        # Enrico Fermi invented the first nuclear reactor. https://en.wikipedia.org/wiki/Enrico_Fermi.
        "fermi",

        # Richard Feynman was a key contributor to quantum mechanics and particle physics. https://en.wikipedia.org/wiki/Richard_Feynman
        "feynman",

        # Benjamin Franklin is famous for his experiments in electricity and the invention of the lightning rod.
        "franklin",

        # Galileo was a founding father of modern astronomy, and faced politics and obscurantism to establish scientific truth.  https://en.wikipedia.org/wiki/Galileo_Galilei
        "galileo",

        # Adele Goldstine, born Adele Katz, wrote the complete technical description for the first electronic digital computer, ENIAC. https://en.wikipedia.org/wiki/Adele_Goldstine
        "goldstine",

        # Jane Goodall - British primatologist, ethologist, and anthropologist who is considered to be the world's foremost expert on chimpanzees - https://en.wikipedia.org/wiki/Jane_Goodall
        "goodall",

        # Stephen Hawking pioneered the field of cosmology by combining general relativity and quantum mechanics. https://en.wikipedia.org/wiki/Stephen_Hawking
        "hawking",

        # Werner Heisenberg was a founding father of quantum mechanics. https://en.wikipedia.org/wiki/Werner_Heisenberg
        "heisenberg",

        # Dorothy Hodgkin was a British biochemist, credited with the development of protein crystallography. She was awarded the Nobel Prize in Chemistry in 1964. https://en.wikipedia.org/wiki/Dorothy_Hodgkin
        "hodgkin",

        # Erna Schneider Hoover revolutionized modern communication by inventing a computerized telephon switching method. https://en.wikipedia.org/wiki/Erna_Schneider_Hoover
        "hoover",

        # Grace Hopper developed the first compiler for a computer programming language and  is credited with popularizing the term "debugging" for fixing computer glitches. https://en.wikipedia.org/wiki/Grace_Hopper
        "hopper",

        # Hypatia - Greek Alexandrine Neoplatonist philosopher in Egypt who was one of the earliest mothers of mathematics - https://en.wikipedia.org/wiki/Hypatia
        "hypatia",

        # Yeong-Sil Jang was a Korean scientist and astronomer during the Joseon Dynasty; he invented the first metal printing press and water gauge. https://en.wikipedia.org/wiki/Jang_Yeong-sil
        "jang",

        # Karen Spärck Jones came up with the concept of inverse document frequency, which is used in most search engines today. https://en.wikipedia.org/wiki/Karen_Sp%C3%A4rck_Jones
        "jones",

        # Jack Kilby and Robert Noyce have invented silicone integrated circuits and gave Silicon Valley its name.
        # - https://en.wikipedia.org/wiki/Jack_Kilby
        # - https://en.wikipedia.org/wiki/Robert_Noyce
        "kilby",
        "noyce",

        # Har Gobind Khorana - Indian-American biochemist who shared the 1968 Nobel Prize for Physiology - https://en.wikipedia.org/wiki/Har_Gobind_Khorana
        "khorana",

        # Maria Kirch - German astronomer and first woman to discover a comet - https://en.wikipedia.org/wiki/Maria_Margarethe_Kirch
        "kirch",

        # Sophie Kowalevski - Russian mathematician responsible for important original contributions to analysis, differential equations and mechanics - https://en.wikipedia.org/wiki/Sofia_Kovalevskaya
        "kowalevski",

        # Marie-Jeanne de Lalande - French astronomer, mathematician and cataloguer of stars - https://en.wikipedia.org/wiki/Marie-Jeanne_de_Lalande
        "lalande",

        # Mary Leakey - British paleoanthropologist who discovered the first fossilized Proconsul skull - https://en.wikipedia.org/wiki/Mary_Leakey
        "leakey",

        # Ada Lovelace invented the first algorithm. https://en.wikipedia.org/wiki/Ada_Lovelace (thanks James Turnbull)
        "lovelace",

        # Auguste and Louis Lumière - the first filmmakers in history - https://en.wikipedia.org/wiki/Auguste_and_Louis_Lumi%C3%A8re
        "lumiere",

        # Maria Mayer - American theoretical physicist and Nobel laureate in Physics for proposing the nuclear shell model of the atomic nucleus - https://en.wikipedia.org/wiki/Maria_Mayer
        "mayer",

        # John McCarthy invented LISP: https://en.wikipedia.org/wiki/John_McCarthy_(computer_scientist)
        "mccarthy",

        # Barbara McClintock - a distinguished American cytogeneticist, 1983 Nobel Laureate in Physiology or Medicine for discovering transposons. https://en.wikipedia.org/wiki/Barbara_McClintock
        "mcclintock",

        # Malcolm McLean invented the modern shipping container: https://en.wikipedia.org/wiki/Malcom_McLean
        "mclean",

        # Lise Meitner - Austrian/Swedish physicist who was involved in the discovery of nuclear fission. The element meitnerium is named after her - https://en.wikipedia.org/wiki/Lise_Meitner
        "meitner",

        # Johanna Mestorf - German prehistoric archaeologist and first female museum director in Germany - https://en.wikipedia.org/wiki/Johanna_Mestorf
        "mestorf",

        # Samuel Morse - contributed to the invention of a single-wire telegraph system based on European telegraphs and was a co-developer of the Morse code - https://en.wikipedia.org/wiki/Samuel_Morse
        "morse",

        # Isaac Newton invented classic mechanics and modern optics. https://en.wikipedia.org/wiki/Isaac_Newton
        "newton",

        # Alfred Nobel - a Swedish chemist, engineer, innovator, and armaments manufacturer (inventor of dynamite) - https://en.wikipedia.org/wiki/Alfred_Nobel
        "nobel",

        # Cecilia Payne-Gaposchkin was an astronomer and astrophysicist who, in 1925, proposed in her Ph.D. thesis an explanation for the composition of stars in terms of the relative abundances of hydrogen and helium. https://en.wikipedia.org/wiki/Cecilia_Payne-Gaposchkin
        "payne",

        # Ambroise Pare invented modern surgery. https://en.wikipedia.org/wiki/Ambroise_Par%C3%A9
        "pare",

        # Louis Pasteur discovered vaccination, fermentation and pasteurization. https://en.wikipedia.org/wiki/Louis_Pasteur.
        "pasteur",

        # Radia Perlman is a software designer and network engineer and most famous for her invention of the spanning-tree protocol (STP). https://en.wikipedia.org/wiki/Radia_Perlman
        "perlman",

        # Rob Pike was a key contributor to Unix, Plan 9, the X graphic system, utf-8, and the Go programming language. https://en.wikipedia.org/wiki/Rob_Pike
        "pike",

        # Henri Poincaré made fundamental contributions in several fields of mathematics. https://en.wikipedia.org/wiki/Henri_Poincar%C3%A9
        "poincare",

        # Laura Poitras is a director and producer whose work, made possible by open source crypto tools, advances the causes of truth and freedom of information by reporting disclosures by whistleblowers such as Edward Snowden. https://en.wikipedia.org/wiki/Laura_Poitras
        "poitras",

        # Claudius Ptolemy - a Greco-Egyptian writer of Alexandria, known as a mathematician, astronomer, geographer, astrologer, and poet of a single epigram in the Greek Anthology - https://en.wikipedia.org/wiki/Ptolemy
        "ptolemy",

        # C. V. Raman - Indian physicist who won the Nobel Prize in 1930 for proposing the Raman effect. - https://en.wikipedia.org/wiki/C._V._Raman
        "raman",

        # Srinivasa Ramanujan - Indian mathematician and autodidact who made extraordinary contributions to mathematical analysis, number theory, infinite series, and continued fractions. - https://en.wikipedia.org/wiki/Srinivasa_Ramanujan
        "ramanujan",

        # Dennis Ritchie and Ken Thompson created UNIX and the C programming language.
        # - https://en.wikipedia.org/wiki/Dennis_Ritchie
        # - https://en.wikipedia.org/wiki/Ken_Thompson
        "ritchie",
        "thompson",

        # Rosalind Franklin - British biophysicist and X-ray crystallographer whose research was critical to the understanding of DNA - https://en.wikipedia.org/wiki/Rosalind_Franklin
        "rosalind",

        # Meghnad Saha - Indian astrophysicist best known for his development of the Saha equation, used to describe chemical and physical conditions in stars - https://en.wikipedia.org/wiki/Meghnad_Saha
        "saha",

        # Jean E. Sammet developed FORMAC, the first widely used computer language for symbolic manipulation of mathematical formulas. https://en.wikipedia.org/wiki/Jean_E._Sammet
        "sammet",

        # Françoise Barré-Sinoussi - French virologist and Nobel Prize Laureate in Physiology or Medicine; her work was fundamental in identifying HIV as the cause of AIDS. https://en.wikipedia.org/wiki/Fran%C3%A7oise_Barr%C3%A9-Sinoussi
        "sinoussi",

        # Richard Matthew Stallman - the founder of the Free Software movement, the GNU project, the Free Software Foundation, and the League for Programming Freedom. He also invented the concept of copyleft to protect the ideals of this movement, and enshrined this concept in the widely-used GPL (General Public License) for software. https://en.wikiquote.org/wiki/Richard_Stallman
        "stallman",

        # Aaron Swartz was influential in creating RSS, Markdown, Creative Commons, Reddit, and much of the internet as we know it today. He was devoted to freedom of information on the web. https://en.wikiquote.org/wiki/Aaron_Swartz
        "swartz",

        # Nikola Tesla invented the AC electric system and every gadget ever used by a James Bond villain. https://en.wikipedia.org/wiki/Nikola_Tesla
        "tesla",

        # Linus Torvalds invented Linux and Git. https://en.wikipedia.org/wiki/Linus_Torvalds
        "torvalds",

        # Alan Turing was a founding father of computer science. https://en.wikipedia.org/wiki/Alan_Turing.
        "turing",

        # Sophie Wilson designed the first Acorn Micro-Computer and the instruction set for ARM processors. https://en.wikipedia.org/wiki/Sophie_Wilson
        "wilson",

        # Steve Wozniak invented the Apple I and Apple II. https://en.wikipedia.org/wiki/Steve_Wozniak
        "wozniak",

        # The Wright brothers, Orville and Wilbur - credited with inventing and building the world's first successful airplane and making the first controlled, powered and sustained heavier-than-air human flight - https://en.wikipedia.org/wiki/Wright_brothers
        "wright",

        # Rosalyn Sussman Yalow - Rosalyn Sussman Yalow was an American medical physicist, and a co-winner of the 1977 Nobel Prize in Physiology or Medicine for development of the radioimmunoassay technique. https://en.wikipedia.org/wiki/Rosalyn_Sussman_Yalow
        "yalow",

        # Ada Yonath - an Israeli crystallographer, the first woman from the Middle East to win a Nobel prize in the sciences. https://en.wikipedia.org/wiki/Ada_Yonath
        "yonath"
    ]

    hostname = random.choice(hostnames)

    return "{}.{}.lan".format(hostname, domainname)

# Try to determine what the hostname should be for this system
def getHostname():

    hn = None

    # First address (we prefer ipv4) of last device (as it used to be) wins
    for dev in nm.nm_activated_devices():
        addrs = (nm.nm_device_ip_addresses(dev, version=4) +
                 nm.nm_device_ip_addresses(dev, version=6))
        for ipaddr in addrs:
            try:
                hinfo = socket.gethostbyaddr(ipaddr)
            except socket.herror as e:
                log.debug("Exception caught trying to get host name of %s: %s", ipaddr, e)
            else:
                if len(hinfo) == 3:
                    hn = hinfo[0]
                    break

    if not hn or hn in ('(none)', 'localhost', 'localhost.localdomain'):
        hn = socket.gethostname()

    if not hn or hn in ('(none)', 'localhost', 'localhost.localdomain'):
        hn = generateRandomHostname()

    return hn

def logIfcfgFile(path, message=""):
    content = ""
    if os.access(path, os.R_OK):
        f = open(path, 'r')
        content = f.read()
        f.close()
    else:
        content = "file not found"
    ifcfglog.debug("%s%s:\n%s", message, path, content)

def _ifcfg_files(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(os.path.join(directory, name))
    return rv

def logIfcfgFiles(message=""):
    ifcfglog.debug("content of files (%s):", message)
    for path in _ifcfg_files(netscriptsDir):
        ifcfglog.debug("%s:", path)
        with open(path, "r") as f:
            for line in f:
                ifcfglog.debug("  %s", line.strip())
    ifcfglog.debug("all settings: %s", nm.nm_get_all_settings())

class IfcfgFile(SimpleConfigFile):
    def __init__(self, filename):
        SimpleConfigFile.__init__(self, always_quote=True, filename=filename)
        self._dirty = False

    def read(self, filename=None):
        self.reset()
        ifcfglog.debug("IfcfFile.read %s", self.filename)
        SimpleConfigFile.read(self)
        self._dirty = False

    def write(self, filename=None, use_tmp=False):
        if self._dirty or filename:
            # ifcfg-rh is using inotify IN_CLOSE_WRITE event so we don't use
            # temporary file for new configuration
            ifcfglog.debug("IfcfgFile.write %s:\n%s", self.filename, self.__str__())
            SimpleConfigFile.write(self, filename, use_tmp=use_tmp)
            self._dirty = False

    def set(self, *args):
        for (key, data) in args:
            if self.get(key) != data:
                break
        else:
            return
        ifcfglog.debug("IfcfgFile.set %s: %s", self.filename, args)
        SimpleConfigFile.set(self, *args)
        self._dirty = True

    def unset(self, *args):
        for key in args:
            if self.get(key):
                self._dirty = True
                break
        else:
            return
        ifcfglog.debug("IfcfgFile.unset %s: %s", self.filename, args)
        SimpleConfigFile.unset(self, *args)

def dumpMissingDefaultIfcfgs():
    """
    Dump missing default ifcfg file for wired devices.
    For default auto connections created by NM upon start - which happens
    in case of missing ifcfg file - rename the connection using device name
    and dump its ifcfg file. (For server, default auto connections will
    be turned off in NetworkManager.conf.)
    The connection id (and consequently ifcfg file) is set to device name.
    Returns list of devices for which ifcfg file was dumped.

    """
    rv = []

    for devname in nm.nm_devices():
        # for each ethernet device
        # FIXME add more types (infiniband, bond...?)
        if not nm.nm_device_type_is_ethernet(devname):
            continue

        # check that device has connection without ifcfg file
        try:
            nm.nm_device_setting_value(devname, "connection", "uuid")
        except nm.SettingsNotFoundError:
            continue
        if find_ifcfg_file_of_device(devname):
            continue

        try:
            nm.nm_update_settings_of_device(devname, [['connection', 'id', devname, None]])
            log.debug("network: dumping ifcfg file for default autoconnection on %s", devname)
            nm.nm_update_settings_of_device(devname, [['connection', 'autoconnect', False, None]])
            log.debug("network: setting autoconnect of %s to False", devname)
        except nm.SettingsNotFoundError:
            log.debug("network: no ifcfg file for %s", devname)
        rv.append(devname)

    return rv

# get a kernel cmdline string for dracut needed for access to storage host
def dracutSetupArgs(networkStorageDevice):

    if networkStorageDevice.nic == "default" or ":" in networkStorageDevice.nic:
        nic = ifaceForHostIP(networkStorageDevice.host_address)
        if not nic:
            return ""
    else:
        nic = networkStorageDevice.nic

    if nic not in nm.nm_devices():
        log.error('Unknown network interface: %s', nic)
        return ""

    ifcfg_path = find_ifcfg_file_of_device(nic)
    if not ifcfg_path:
        log.error("dracutSetupArgs: can't find ifcfg file for %s", nic)
        return ""
    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    return dracutBootArguments(nic,
                               ifcfg,
                               networkStorageDevice.host_address,
                               getHostname())

def dracutBootArguments(devname, ifcfg, storage_ipaddr, hostname=None):

    netargs = set()

    if ifcfg.get('BOOTPROTO') == 'ibft':
        netargs.add("ip=ibft")
    elif storage_ipaddr:
        if hostname is None:
            hostname = ""
        # if using ipv6
        if ':' in storage_ipaddr:
            if ifcfg.get('DHCPV6C') == "yes":
                # XXX combination with autoconf not yet clear,
                # support for dhcpv6 is not yet implemented in NM/ifcfg-rh
                netargs.add("ip=%s:dhcp6" % devname)
            elif ifcfg.get('IPV6_AUTOCONF') == "yes":
                netargs.add("ip=%s:auto6" % devname)
            elif ifcfg.get('IPV6ADDR'):
                ipaddr = "[%s]" % ifcfg.get('IPV6ADDR')
                if ifcfg.get('IPV6_DEFAULTGW'):
                    gateway = "[%s]" % ifcfg.get('IPV6_DEFAULTGW')
                else:
                    gateway = ""
                netargs.add("ip=%s::%s::%s:%s:none" % (ipaddr, gateway,
                            hostname, devname))
        else:
            if iutil.lowerASCII(ifcfg.get('bootproto')) == 'dhcp':
                netargs.add("ip=%s:dhcp" % devname)
            else:
                cfgidx = ''
                if ifcfg.get('IPADDR0'):
                    cfgidx = '0'
                if ifcfg.get('GATEWAY%s' % cfgidx):
                    gateway = ifcfg.get('GATEWAY%s' % cfgidx)
                else:
                    gateway = ""
                netmask = ifcfg.get('NETMASK%s' % cfgidx)
                prefix = ifcfg.get('PREFIX%s' % cfgidx)
                if not netmask and prefix:
                    netmask = prefix2netmask(int(prefix))
                ipaddr = ifcfg.get('IPADDR%s' % cfgidx)
                netargs.add("ip=%s::%s:%s:%s:%s:none" %
                            (ipaddr, gateway, netmask, hostname, devname))

        hwaddr = ifcfg.get("HWADDR")
        if hwaddr:
            netargs.add("ifname=%s:%s" % (devname, hwaddr.lower()))

        if ifcfg.get("TYPE") == "Team" or ifcfg.get("DEVICETYPE") == "Team":
            slaves = get_team_slaves([devname, ifcfg.get("UUID")])
            netargs.add("team=%s:%s" % (devname,
                                        ",".join(dev for dev, _cfg in slaves)))

    nettype = ifcfg.get("NETTYPE")
    subchannels = ifcfg.get("SUBCHANNELS")
    if blivet.arch.isS390() and nettype and subchannels:
        znet = "rd.znet=%s,%s" % (nettype, subchannels)
        options = ifcfg.get("OPTIONS").strip("'\"")
        if options:
            options = filter(lambda x: x != '', options.split(' '))
            znet += ",%s" % (','.join(options))
        netargs.add(znet)

    return netargs

def _get_ip_setting_values_from_ksdata(networkdata):
    values = []

    # ipv4 settings
    method4 = "auto"
    if networkdata.bootProto == "static":
        method4 = "manual"
    values.append(["ipv4", "method", method4, "s"])

    if method4 == "manual":
        addr4 = nm.nm_ipv4_to_dbus_int(networkdata.ip)
        if networkdata.gateway:
            gateway4 = nm.nm_ipv4_to_dbus_int(networkdata.gateway)
        else:
            gateway4 = 0 # will be ignored by NetworkManager
        prefix4 = netmask2prefix(networkdata.netmask)
        values.append(["ipv4", "addresses", [[addr4, prefix4, gateway4]], "aau"])

    # ipv6 settings
    if networkdata.noipv6:
        method6 = "ignore"
    else:
        if not networkdata.ipv6:
            method6 = "auto"
        elif networkdata.ipv6 == "auto":
            method6 = "auto"
        elif networkdata.ipv6 == "dhcp":
            method6 = "dhcp"
        else:
            method6 = "manual"
    values.append(["ipv6", "method", method6, "s"])

    if method6 == "manual":
        addr6, _slash, prefix6 = networkdata.ipv6.partition("/")
        if prefix6:
            prefix6 = int(prefix6)
        else:
            prefix6 = 64
        addr6 = nm.nm_ipv6_to_dbus_ay(addr6)
        if networkdata.ipv6gateway:
            gateway6 = nm.nm_ipv6_to_dbus_ay(networkdata.ipv6gateway)
        else:
            gateway6 = [0] * 16
        values.append(["ipv6", "addresses", [(addr6, prefix6, gateway6)], "a(ayuay)"])

    # nameservers
    nss4 = []
    nss6 = []
    if networkdata.nameserver:
        for ns in [str.strip(i) for i in networkdata.nameserver.split(",")]:
            if check_ip_address(ns, version=6):
                nss6.append(nm.nm_ipv6_to_dbus_ay(ns))
            elif check_ip_address(ns, version=4):
                nss4.append(nm.nm_ipv4_to_dbus_int(ns))
            else:
                log.error("IP address %s is not valid", ns)
    values.append(["ipv4", "dns", nss4, "au"])
    values.append(["ipv6", "dns", nss6, "aay"])

    return values

def update_settings_with_ksdata(devname, networkdata):
    new_values = _get_ip_setting_values_from_ksdata(networkdata)
    new_values.append(['connection', 'autoconnect', networkdata.onboot, None])
    uuid = nm.nm_device_setting_value(devname, "connection", "uuid")
    nm.nm_update_settings_of_device(devname, new_values)
    return uuid

def bond_options_ksdata_to_dbus(opts_str):
    retval = {}
    for option in opts_str.split(";" if ';' in opts_str else ","):
        key, _sep, value = option.partition("=")
        retval[key] = value
    return retval

def add_connection_for_ksdata(networkdata, devname):

    added_connections = []
    con_uuid = str(uuid4())
    values = _get_ip_setting_values_from_ksdata(networkdata)
    # HACK preventing NM to autoactivate the connection
    #values.append(['connection', 'autoconnect', networkdata.onboot, 'b'])
    values.append(['connection', 'autoconnect', False, 'b'])
    values.append(['connection', 'uuid', con_uuid, 's'])

    # type "bond"
    if networkdata.bondslaves:
        # bond connection is autoactivated
        values.append(['connection', 'type', 'bond', 's'])
        values.append(['connection', 'id', devname, 's'])
        values.append(['bond', 'interface-name', devname, 's'])
        options = bond_options_ksdata_to_dbus(networkdata.bondopts)
        values.append(['bond', 'options', options, 'a{ss}'])
        for slave in networkdata.bondslaves.split(","):
            suuid = _add_slave_connection('bond', slave, devname, networkdata.activate)
            added_connections.append((suuid, slave))
        dev_spec = None
    # type "team"
    elif networkdata.teamslaves:
        values.append(['connection', 'type', 'team', 's'])
        values.append(['connection', 'id', devname, 's'])
        values.append(['team', 'interface-name', devname, 's'])
        values.append(['team', 'config', networkdata.teamconfig, 's'])
        for (slave, cfg) in networkdata.teamslaves:
            values = [['team-port', 'config', cfg, 's']]
            suuid = _add_slave_connection('team', slave, devname, networkdata.activate, values)
            added_connections.append((suuid, slave))
        dev_spec = None
    # type "vlan"
    elif networkdata.vlanid:
        values.append(['vlan', 'parent', networkdata.parent, 's'])
        values.append(['connection', 'type', 'vlan', 's'])
        values.append(['connection', 'id', devname, 's'])
        values.append(['vlan', 'interface-name', devname, 's'])
        values.append(['vlan', 'id', int(networkdata.vlanid), 'u'])
        dev_spec = None
    # type "bridge"
    elif networkdata.bridgeslaves:
        # bridge connection is autoactivated
        values.append(['connection', 'type', 'bridge', 's'])
        values.append(['connection', 'id', devname, 's'])
        values.append(['bridge', 'interface-name', devname, 's'])
        for opt in networkdata.bridgeopts.split(","):
            key, _sep, value = opt.partition("=")
            if key == "stp":
                if value == "yes":
                    values.append(['bridge', key, True, 'b'])
                elif value == "no":
                    values.append(['bridge', key, False, 'b'])
                continue
            try:
                value = int(value)
            except ValueError:
                log.error("Invalid bridge option %s", opt)
                continue
            values.append(['bridge', key, int(value), 'u'])
        for slave in networkdata.bridgeslaves.split(","):
            suuid = _add_slave_connection('bridge', slave, devname, networkdata.activate)
            added_connections.append((suuid, slave))
        dev_spec = None
    # type "802-3-ethernet"
    else:
        mac = nm.nm_device_perm_hwaddress(devname)
        if flags.cmdline.get("ifname", "").upper() == "{0}:{1}".format(devname, mac).upper():
            mac = [int(b, 16) for b in mac.split(":")]
            values.append(['802-3-ethernet', 'mac-address', mac, 'ay'])
        else:
            values.append(['802-3-ethernet', 'name', devname, 's'])
        values.append(['connection', 'type', '802-3-ethernet', 's'])
        values.append(['connection', 'id', devname, 's'])
        values.append(['connection', 'interface-name', devname, 's'])

        dev_spec = devname

    try:
        nm.nm_add_connection(values)
    except nm.BondOptionsError as e:
        log.error(e)
        return []
    added_connections.insert(0, (con_uuid, dev_spec))
    return added_connections

def _add_slave_connection(slave_type, slave, master, activate, values=None):
    values = values or []
    #slave_name = "%s slave %d" % (devname, slave_idx)
    slave_name = slave

    values = []
    suuid = str(uuid4())
    # assume ethernet, TODO: infiniband, wifi, vlan
    values.append(['connection', 'uuid', suuid, 's'])
    values.append(['connection', 'id', slave_name, 's'])
    values.append(['connection', 'slave-type', slave_type, 's'])
    values.append(['connection', 'master', master, 's'])
    values.append(['connection', 'type', '802-3-ethernet', 's'])
    mac = nm.nm_device_perm_hwaddress(slave)
    mac = [int(b, 16) for b in mac.split(":")]
    values.append(['802-3-ethernet', 'mac-address', mac, 'ay'])

    # disconnect slaves
    if activate:
        try:
            nm.nm_disconnect_device(slave)
        except nm.DeviceNotActiveError:
            pass
    # remove ifcfg file
    ifcfg_path = find_ifcfg_file_of_device(slave)
    if ifcfg_path and os.access(ifcfg_path, os.R_OK):
        os.unlink(ifcfg_path)

    nm.nm_add_connection(values)

    return suuid

def ksdata_from_ifcfg(devname, uuid=None):

    if devname not in nm.nm_devices():
        return None

    if nm.nm_device_is_slave(devname):
        return None
    if nm.nm_device_type_is_wifi(devname):
        # wifi from kickstart is not supported yet
        return None

    if not uuid:
        # Find ifcfg file for the device.
        # If the device is active, use uuid of its active connection.
        uuid = nm.nm_device_active_con_uuid(devname)

    if uuid:
        ifcfg_path = find_ifcfg_file([("UUID", uuid)])
    else:
        # look it up by other values depending on its type
        ifcfg_path = find_ifcfg_file_of_device(devname)

    if not ifcfg_path:
        return None

    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    nd = ifcfg_to_ksdata(ifcfg, devname)

    if not nd:
        return None

    if nm.nm_device_type_is_ethernet(devname):
        nd.device = devname
    elif nm.nm_device_type_is_wifi(devname):
        nm.device = ""
    elif nm.nm_device_type_is_bond(devname):
        nd.device = devname
    elif nm.nm_device_type_is_team(devname):
        nd.device = devname
    elif nm.nm_device_type_is_bridge(devname):
        nd.device = devname
    elif nm.nm_device_type_is_vlan(devname):
        if devname != default_ks_vlan_interface_name(nd.device, nd.vlanid):
            nd.interfacename = devname

    return nd

def ifcfg_to_ksdata(ifcfg, devname):

    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    kwargs = {}

    # no network command for bond slaves
    if ifcfg.get("MASTER"):
        return None
    # no network command for team slaves
    if ifcfg.get("TEAM_MASTER"):
        return None
    # no network command for bridge slaves
    if ifcfg.get("BRIDGE"):
        return None

    # ipv4 and ipv6
    if ifcfg.get("ONBOOT") and ifcfg.get("ONBOOT") == "no":
        kwargs["onboot"] = False
    if ifcfg.get('MTU') and ifcfg.get('MTU') != "0":
        kwargs["mtu"] = ifcfg.get('MTU')
    # ipv4
    if not ifcfg.get('BOOTPROTO'):
        kwargs["noipv4"] = True
    else:
        if iutil.lowerASCII(ifcfg.get('BOOTPROTO')) == 'dhcp':
            kwargs["bootProto"] = "dhcp"
            if ifcfg.get('DHCPCLASS'):
                kwargs["dhcpclass"] = ifcfg.get('DHCPCLASS')
        elif ifcfg.get('IPADDR'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR')
            netmask = ifcfg.get('NETMASK')
            prefix = ifcfg.get('PREFIX')
            if not netmask and prefix:
                netmask = prefix2netmask(int(prefix))
            if netmask:
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY'):
                kwargs["gateway"] = ifcfg.get('GATEWAY')
        elif ifcfg.get('IPADDR0'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR0')
            prefix = ifcfg.get('PREFIX0')
            if prefix:
                netmask = prefix2netmask(int(prefix))
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY0'):
                kwargs["gateway"] = ifcfg.get('GATEWAY0')


    # ipv6
    if (not ifcfg.get('IPV6INIT') or
        ifcfg.get('IPV6INIT') == "no"):
        kwargs["noipv6"] = True
    else:
        if ifcfg.get('IPV6_AUTOCONF') in ("yes", ""):
            kwargs["ipv6"] = "auto"
        else:
            if ifcfg.get('IPV6ADDR'):
                kwargs["ipv6"] = ifcfg.get('IPV6ADDR')
                if ifcfg.get('IPV6_DEFAULTGW') \
                   and ifcfg.get('IPV6_DEFAULTGW') != "::":
                    kwargs["ipv6gateway"] = ifcfg.get('IPV6_DEFAULTGW')
            if ifcfg.get('DHCPV6C') == "yes":
                kwargs["ipv6"] = "dhcp"

    # ipv4 and ipv6
    dnsline = ''
    for key in ifcfg.info.keys():
        if iutil.upperASCII(key).startswith('DNS'):
            if dnsline == '':
                dnsline = ifcfg.get(key)
            else:
                dnsline += "," + ifcfg.get(key)
    if dnsline:
        kwargs["nameserver"] = dnsline

    if ifcfg.get("ETHTOOL_OPTS"):
        kwargs["ethtool"] = ifcfg.get("ETHTOOL_OPTS")

    if ifcfg.get("ESSID"):
        kwargs["essid"] = ifcfg.get("ESSID")

    # hostname
    if ifcfg.get("DHCP_HOSTNAME"):
        kwargs["hostname"] = ifcfg.get("DHCP_HOSTNAME")

    # bonding
    # FIXME: dracut has only BOND_OPTS
    if ifcfg.get("BONDING_MASTER") == "yes" or ifcfg.get("TYPE") == "Bond":
        slaves = get_slaves_from_ifcfgs("MASTER", [devname, ifcfg.get("UUID")])
        if slaves:
            kwargs["bondslaves"] = ",".join(slaves)
        bondopts = ifcfg.get("BONDING_OPTS")
        if bondopts:
            sep = ","
            if sep in bondopts:
                sep = ";"
            kwargs["bondopts"] = sep.join(bondopts.split())

    # vlan
    if ifcfg.get("VLAN") == "yes" or ifcfg.get("TYPE") == "Vlan":
        kwargs["device"] = ifcfg.get("PHYSDEV")
        kwargs["vlanid"] = ifcfg.get("VLAN_ID")

    # bridging
    if ifcfg.get("TYPE") == "Bridge":
        slaves = get_slaves_from_ifcfgs("BRIDGE", [devname, ifcfg.get("UUID")])
        if slaves:
            kwargs["bridgeslaves"] = ",".join(slaves)

        bridgeopts = ifcfg.get("BRIDGING_OPTS").replace('_', '-').split()
        if ifcfg.get("STP"):
            bridgeopts.append("%s=%s" % ("stp", ifcfg.get("STP")))
        if ifcfg.get("DELAY"):
            bridgeopts.append("%s=%s" % ("forward-delay", ifcfg.get("DELAY")))
        if bridgeopts:
            kwargs["bridgeopts"] = ",".join(bridgeopts)

    # pylint: disable=no-member
    nd = handler.NetworkData(**kwargs)

    # teaming
    if ifcfg.get("TYPE") == "Team" or ifcfg.get("DEVICETYPE") == "Team":
        slaves = get_team_slaves([devname, ifcfg.get("UUID")])
        for dev, cfg in slaves:
            nd.teamslaves.append((dev, cfg))

        teamconfig = nm.nm_device_setting_value(devname, "team", "config")
        if teamconfig:
            nd.teamconfig = teamconfig

    return nd

def hostname_ksdata(hostname):
    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    # pylint: disable=no-member
    return handler.NetworkData(hostname=hostname, bootProto="")

def find_ifcfg_file_of_device(devname, root_path=""):
    ifcfg_path = None

    if devname not in nm.nm_devices():
        return None

    if nm.nm_device_type_is_wifi(devname):
        ssid = nm.nm_device_active_ssid(devname)
        if ssid:
            ifcfg_path = find_ifcfg_file([("ESSID", ssid)])
    elif nm.nm_device_type_is_bond(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_team(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_vlan(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_bridge(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_ethernet(devname):
        try:
            hwaddr = nm.nm_device_perm_hwaddress(devname)
        except nm.PropertyNotFoundError:
            hwaddr = None
        if hwaddr:
            hwaddr_check = lambda mac: mac.upper() == hwaddr.upper()
            nonempty = lambda x: x
            # slave configration created in GUI takes precedence
            ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                          ("MASTER", nonempty)],
                                         root_path)
            if not ifcfg_path:
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                              ("TEAM_MASTER", nonempty)],
                                             root_path)
            if not ifcfg_path:
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                              ("BRIDGE", nonempty)],
                                             root_path)
            if not ifcfg_path:
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check)], root_path)
        if not ifcfg_path:
            ifcfg_path = find_ifcfg_file([("DEVICE", devname)], root_path)

    return ifcfg_path

def find_ifcfg_file(values, root_path=""):
    for filepath in _ifcfg_files(os.path.normpath(root_path+netscriptsDir)):
        ifcfg = IfcfgFile(filepath)
        ifcfg.read()
        for key, value in values:
            if callable(value):
                if not value(ifcfg.get(key)):
                    break
            else:
                if ifcfg.get(key) != value:
                    break
        else:
            return filepath
    return None

def get_slaves_from_ifcfgs(master_option, master_specs):
    """List of slaves of master specified by master_specs in master_option.

       master_option is ifcfg option containing spec of master
       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for filepath in _ifcfg_files(netscriptsDir):
        ifcfg = IfcfgFile(filepath)
        ifcfg.read()
        master = ifcfg.get(master_option)
        if master in master_specs:
            device = ifcfg.get("DEVICE")
            if device:
                slaves.append(device)
            else:
                hwaddr = ifcfg.get("HWADDR")
                for devname in nm.nm_devices():
                    try:
                        h = nm.nm_device_property(devname, "PermHwAddress")
                    except nm.PropertyNotFoundError:
                        log.debug("can't get PermHwAddress of devname %s", devname)
                        continue
                    if h.upper() == hwaddr.upper():
                        slaves.append(devname)
                        break
    return slaves

# why not from ifcfg? because we want config json value without escapes
def get_team_slaves(master_specs):
    """List of slaves of master specified by master_specs (name, opts).

       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for master in master_specs:
        slave_settings = nm.nm_get_settings(master, "connection", "master")
        for settings in slave_settings:
            try:
                cfg = settings["team-port"]["config"]
            except KeyError:
                cfg = ""
            devname = settings["connection"].get("interface-name")
            #nm-c-e doesn't save device name
            # TODO: wifi, infiniband
            if not devname:
                ty = settings["connection"]["type"]
                if ty == "802-3-ethernet":
                    hwaddr = settings["802-3-ethernet"]["mac-address"]
                    hwaddr = ":".join("%02X" % b for b in hwaddr)
                    devname = nm.nm_hwaddr_to_device_name(hwaddr)
            if devname:
                slaves.append((devname, cfg))
            else:
                uuid = settings["connection"].get("uuid")
                log.debug("network: can't get team slave device name of %s", uuid)

    return slaves

def ifaceForHostIP(host):
    route = iutil.execWithCapture("ip", ["route", "get", "to", host])
    if not route:
        log.error("Could not get interface for route to %s", host)
        return ""

    routeInfo = route.split()
    if routeInfo[0] != host or len(routeInfo) < 5 or \
       "dev" not in routeInfo or routeInfo.index("dev") > 3:
        log.error('Unexpected "ip route get to %s" reply: %s', host, routeInfo)
        return ""

    return routeInfo[routeInfo.index("dev") + 1]

def default_route_device():
    routes = iutil.execWithCapture("ip", ["route", "show"])
    if not routes:
        log.error("Could not get default route device")
        return None

    for line in routes.split("\n"):
        if line.startswith("default"):
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "dev":
                return parts[4]
            else:
                log.error("Could not parse default route device: %s", line)
                return None

    return None

def copyFileToPath(fileName, destPath='', overwrite=False):
    if not os.path.isfile(fileName):
        return False
    destfile = os.path.join(destPath, fileName.lstrip('/'))
    if (os.path.isfile(destfile) and not overwrite):
        return False
    if not os.path.isdir(os.path.dirname(destfile)):
        iutil.mkdirChain(os.path.dirname(destfile))
    shutil.copy(fileName, destfile)
    return True

# /etc/sysconfig/network-scripts/ifcfg-*
# /etc/sysconfig/network-scripts/keys-*
# TODO: routing info from /etc/sysconfig/network-scripts?
def copyIfcfgFiles(destPath):
    files = os.listdir(netscriptsDir)
    for cfgFile in files:
        if cfgFile.startswith(("ifcfg-", "keys-")):
            srcfile = os.path.join(netscriptsDir, cfgFile)
            copyFileToPath(srcfile, destPath)

# /etc/dhcp/dhclient-DEVICE.conf
# TODORV: do we really don't want overwrite on live cd?
def copyDhclientConfFiles(destPath):
    for devName in nm.nm_devices():
        dhclientfile = os.path.join("/etc/dhcp/dhclient-%s.conf" % devName)
        copyFileToPath(dhclientfile, destPath)

def ks_spec_to_device_name(ksspec=""):
    """
    Find the first network device which matches the kickstart specification.
    Will not match derived types such as bonds and vlans.

    :param ksspec: kickstart-specified device name
    :returns: a string naming a physical device, or "" meaning none matched
    :rtype: str

    """
    bootif_mac = ''
    if ksspec == 'bootif' and "BOOTIF" in flags.cmdline:
        bootif_mac = flags.cmdline["BOOTIF"][3:].replace("-", ":").upper()
    for dev in sorted(nm.nm_devices()):
        # "eth0"
        if ksspec == dev:
            break
        # "link" - match the first device which is plugged (has a carrier)
        elif ksspec == 'link':
            try:
                link_up = nm.nm_device_carrier(dev)
            except ValueError as e:
                log.debug("ks_spec_to_device_name: %s", e)
                continue
            if link_up:
                ksspec = dev
                break
        # "XX:XX:XX:XX:XX:XX" (mac address)
        elif ':' in ksspec:
            try:
                hwaddr = nm.nm_device_perm_hwaddress(dev)
            except ValueError as e:
                log.debug("ks_spec_to_device_name: %s", e)
                continue
            if ksspec.lower() == hwaddr.lower():
                ksspec = dev
                break
        # "bootif" and BOOTIF==XX:XX:XX:XX:XX:XX
        elif ksspec == 'bootif':
            try:
                hwaddr = nm.nm_device_perm_hwaddress(dev)
            except ValueError as e:
                log.debug("ks_spec_to_device_name: %s", e)
                continue
            if bootif_mac.lower() == hwaddr.lower():
                ksspec = dev
                break

    return ksspec

def set_hostname(hn):
    if can_touch_runtime_system("set hostname", touch_live=True):
        log.info("setting installation environment host name to %s", hn)
        iutil.execWithRedirect("hostnamectl", ["set-hostname", hn])

def write_hostname(rootpath, ksdata, overwrite=False):
    cfgfile = os.path.normpath(rootpath + hostnameFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    f = open(cfgfile, "w")
    f.write("%s\n" % ksdata.network.hostname)
    f.close()

    return True

def disableIPV6(rootpath):
    cfgfile = os.path.normpath(rootpath + ipv6ConfFile)
    if ('noipv6' in flags.cmdline
        and all(nm.nm_device_setting_value(dev, "ipv6", "method") == "ignore"
                for dev in nm.nm_devices() if nm.nm_device_type_is_ethernet(dev))):
        log.info('Disabling ipv6 on target system')
        with open(cfgfile, "a") as f:
            f.write("# Anaconda disabling ipv6 (noipv6 option)\n")
            f.write("net.ipv6.conf.all.disable_ipv6=1\n")
            f.write("net.ipv6.conf.default.disable_ipv6=1\n")

def disableNMForStorageDevices(rootpath, storage):
    for devname in nm.nm_devices():
        if (usedByFCoE(devname, storage) or
            usedByRootOnISCSI(devname, storage)):
            ifcfg_path = find_ifcfg_file_of_device(devname, root_path=rootpath)
            if not ifcfg_path:
                log.warning("disableNMForStorageDevices: ifcfg file for %s not found",
                            devname)
                continue
            ifcfg = IfcfgFile(ifcfg_path)
            ifcfg.read()
            ifcfg.set(('NM_CONTROLLED', 'no'))
            ifcfg.write()
            log.info("network device %s used by storage will not be "
                     "controlled by NM", devname)

# sets ONBOOT=yes (and its mirror value in ksdata) for devices used by FCoE
def autostartFCoEDevices(rootpath, storage, ksdata):
    for devname in nm.nm_devices():
        if usedByFCoE(devname, storage):
            ifcfg_path = find_ifcfg_file_of_device(devname, root_path=rootpath)
            if not ifcfg_path:
                log.warning("autoconnectFCoEDevices: ifcfg file for %s not found", devname)
                continue

            ifcfg = IfcfgFile(ifcfg_path)
            ifcfg.read()
            ifcfg.set(('ONBOOT', 'yes'))
            ifcfg.write()
            log.debug("setting ONBOOT=yes for network device %s used by fcoe", devname)
            for nd in ksdata.network.network:
                if nd.device == devname:
                    nd.onboot = True
                    break

def usedByFCoE(iface, storage):
    for d in storage.devices:
        if (isinstance(d, FcoeDiskDevice) and
            d.nic == iface):
            return True
    return False

def usedByRootOnISCSI(iface, storage):
    rootdev = storage.rootDevice
    for d in storage.devices:
        if (isinstance(d, iScsiDiskDevice) and
            rootdev.dependsOn(d)):
            if d.nic == "default" or ":" in d.nic:
                if iface == ifaceForHostIP(d.host_address):
                    return True
            elif d.nic == iface:
                return True

    return False

def write_sysconfig_network(rootpath, overwrite=False):

    cfgfile = os.path.normpath(rootpath + networkConfFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    with open(cfgfile, "w") as f:
        f.write("# Created by anaconda\n")
    return True

def write_network_config(storage, ksdata, instClass, rootpath):
    write_hostname(rootpath, ksdata, overwrite=flags.livecdInstall)
    set_hostname(ksdata.network.hostname)
    write_sysconfig_network(rootpath, overwrite=flags.livecdInstall)
    disableIPV6(rootpath)
    copyIfcfgFiles(rootpath)
    copyDhclientConfFiles(rootpath)
    copyFileToPath("/etc/resolv.conf", rootpath, overwrite=flags.livecdInstall)
    instClass.setNetworkOnbootDefault(ksdata)
    # NM_CONTROLLED is not mirrored in ksdata
    disableNMForStorageDevices(rootpath, storage)
    autostartFCoEDevices(rootpath, storage, ksdata)

def update_hostname_data(ksdata, hostname):
    log.debug("updating host name %s", hostname)
    hostname_found = False
    for nd in ksdata.network.network:
        if nd.hostname:
            nd.hostname = hostname
            hostname_found = True
    if not hostname_found:
        nd = hostname_ksdata(hostname)
        ksdata.network.network.append(nd)

def get_device_name(network_data):
    """
    Find the first network device which matches the kickstart specification.

    :param network_data: A pykickstart NetworkData object
    :returns: a string naming a physical device, or "" meaning none matched
    :rtype: str

    """
    ksspec = network_data.device or flags.cmdline.get('ksdevice') or ""
    dev_name = ks_spec_to_device_name(ksspec)
    if not dev_name:
        return ""
    if dev_name not in nm.nm_devices():
        if not any((network_data.vlanid, network_data.bondslaves, network_data.teamslaves, network_data.bridgeslaves)):
            return ""
    if network_data.vlanid:
        network_data.parent = dev_name
        dev_name = network_data.interfacename or default_ks_vlan_interface_name(network_data.parent, network_data.vlanid)

    return dev_name

def setOnboot(ksdata):
    updated_devices = []
    for network_data in ksdata.network.network:

        devname = get_device_name(network_data)
        if not devname:
            log.warning("network: set ONBOOT: --device %s does not exist", network_data.device)
            continue

        updated_devices.append(devname)
        try:
            nm.nm_update_settings_of_device(devname, [['connection', 'autoconnect', network_data.onboot, None]])
        except (nm.SettingsNotFoundError, nm.UnknownDeviceError) as e:
            log.debug("setOnboot: %s", e)
    return updated_devices

def apply_kickstart(ksdata):
    applied_devices = []

    for i, network_data in enumerate(ksdata.network.network):

        # TODO: wireless not supported yet
        if network_data.essid:
            continue

        dev_name = get_device_name(network_data)
        if not dev_name:
            log.warning("network: apply kickstart: --device %s does not exist", network_data.device)
            continue

        ifcfg_path = find_ifcfg_file_of_device(dev_name)
        if ifcfg_path:
            with open(ifcfg_path, 'r') as f:
                # If we have kickstart ifcfg from initramfs
                if "Generated by parse-kickstart" in f.read():
                    # and we should activate the device
                    if i == 0 or network_data.activate:
                        ifcfg = IfcfgFile(ifcfg_path)
                        ifcfg.read()
                        con_uuid = ifcfg.get("UUID")
                        # and the ifcfg had not been already applied to device by NM
                        if con_uuid != nm.nm_device_active_con_uuid(dev_name):
                            # apply it overriding configuration generated by NM
                            # taking over connection activated in initramfs
                            log.debug("network: kickstart - reactivating device %s with %s", dev_name, con_uuid)
                            try:
                                nm.nm_activate_device_connection(dev_name, con_uuid)
                            except nm.UnknownConnectionError:
                                log.warning("network: kickstart - can't activate connection %s on %s",
                                            con_uuid, dev_name)
                    continue

        # If we don't have kickstart ifcfg from initramfs the command was added
        # in %pre section after switch root, so apply it now
        applied_devices.append(dev_name)
        if ifcfg_path:
            # if the device was already configured in initramfs update the settings
            log.debug("network: pre kickstart - updating settings of device %s", dev_name)
            con_uuid = update_settings_with_ksdata(dev_name, network_data)
            added_connections = [(con_uuid, dev_name)]
        else:
            log.debug("network: pre kickstart - adding connection for %s", dev_name)
            # Virtual devices (eg vlan, bond) return dev_name == None
            added_connections = add_connection_for_ksdata(network_data, dev_name)

        if network_data.activate:
            for con_uuid, dev_name in added_connections:
                try:
                    nm.nm_activate_device_connection(dev_name, con_uuid)
                except (nm.UnknownConnectionError, nm.UnknownDeviceError) as e:
                    log.warning("network: pre kickstart: can't activate connection %s on %s: %s",
                                con_uuid, dev_name, e)
    return applied_devices

def networkInitialize(ksdata):
    if not can_touch_runtime_system("networkInitialize", touch_live=True):
        return

    log.debug("network: devices found %s", nm.nm_devices())
    logIfcfgFiles("network initialization")

    devnames = apply_kickstart(ksdata)
    if devnames:
        msg = "kickstart pre section applied for devices %s" % devnames
        log.debug("network: %s", msg)
        logIfcfgFiles(msg)
    devnames = dumpMissingDefaultIfcfgs()
    if devnames:
        msg = "missing ifcfgs created for devices %s" % devnames
        log.debug("network: %s", msg)
        logIfcfgFiles(msg)

    # For kickstart network --activate option we set ONBOOT=yes
    # in dracut to get devices activated by NM. The real network --onboot
    # value is set here.
    devnames = setOnboot(ksdata)
    if devnames:
        msg = "setting real kickstart ONBOOT value for devices %s" % devnames
        log.debug("network: %s", msg)
        logIfcfgFiles(msg)

    if ksdata.network.hostname is None:
        hostname = getHostname()
        update_hostname_data(ksdata, hostname)

def _get_ntp_servers_from_dhcp(ksdata):
    """Check if some NTP servers were returned from DHCP and set them
    to ksdata (if not NTP servers were specified in the kickstart)"""
    ntp_servers = nm.nm_ntp_servers_from_dhcp()
    log.info("got %d NTP servers from DHCP", len(ntp_servers))
    hostnames = []
    for server_address in ntp_servers:
        try:
            hostname = socket.gethostbyaddr(server_address)[0]
        except socket.error:
            # getting hostname failed, just use the address returned from DHCP
            log.debug("getting NTP server host name failed for address: %s",
                      server_address)
            hostname = server_address
        hostnames.append(hostname)
    # check if some NTP servers were specified from kickstart
    if not ksdata.timezone.ntpservers \
       and not (flags.imageInstall or flags.dirInstall):
        # no NTP servers were specified, add those from DHCP
        ksdata.timezone.ntpservers = hostnames

def _wait_for_connecting_NM():
    """If NM is in connecting state, wait for connection.
    Return value: NM has got connection."""

    if nm.nm_is_connected():
        return True

    if nm.nm_is_connecting():
        log.debug("waiting for connecting NM (dhcp?)")
    else:
        return False

    i = 0
    while nm.nm_is_connecting() and i < constants.NETWORK_CONNECTION_TIMEOUT:
        i += constants.NETWORK_CONNECTED_CHECK_INTERVAL
        time.sleep(constants.NETWORK_CONNECTED_CHECK_INTERVAL)
        if nm.nm_is_connected():
            log.debug("connected, waited %d seconds", i)
            return True

    log.debug("not connected, waited %d of %d secs", i, constants.NETWORK_CONNECTION_TIMEOUT)
    return False

def wait_for_network_devices(devices, timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    devices = set(devices)
    i = 0
    log.debug("waiting for connection of devices %s for iscsi", devices)
    while  i < timeout:
        if not devices - set(nm.nm_activated_devices()):
            return True
        i += 1
        time.sleep(1)
    return False

def wait_for_connecting_NM_thread(ksdata):
    """This function is called from a thread which is run at startup
    to wait for Network Manager to connect."""
    # connection (e.g. auto default dhcp) is activated by NM service
    connected = _wait_for_connecting_NM()
    if connected:
        if ksdata.network.hostname == DEFAULT_HOSTNAME:
            hostname = getHostname()
            update_hostname_data(ksdata, hostname)
        _get_ntp_servers_from_dhcp(ksdata)
    with network_connected_condition:
        global network_connected
        network_connected = connected
        network_connected_condition.notify_all()


def wait_for_connectivity(timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    """Wait for network connectivty to become available

    :param timeout: how long to wait in seconds
    :type param: integer of float"""
    connected = False
    network_connected_condition.acquire()
    # if network_connected is None, network connectivity check
    # has not yet been run or is in progress, so wait for it to finish
    if network_connected is None:
        # wait releases the lock and reacquires it once the thread is unblocked
        network_connected_condition.wait(timeout=timeout)
    connected = network_connected
    # after wait() unblocks, we get the lock back,
    # so we need to release it
    network_connected_condition.release()
    return connected

def status_message():
    """ A short string describing which devices are connected. """

    msg = _("Unknown")

    state = nm.nm_state()
    if state == NetworkManager.State.CONNECTING:
        msg = _("Connecting...")
    elif state == NetworkManager.State.DISCONNECTING:
        msg = _("Disconnecting...")
    else:
        active_devs = nm.nm_activated_devices()
        if active_devs:

            slaves = {}
            ssids = {}

            # first find slaves and wireless aps
            for devname in active_devs:
                slaves[devname] = nm.nm_device_slaves(devname) or []
                if nm.nm_device_type_is_wifi(devname):
                    ssids[devname] = nm.nm_device_active_ssid(devname) or ""

            all_slaves = set(itertools.chain.from_iterable(slaves.values()))
            nonslaves = [dev for dev in active_devs if dev not in all_slaves]

            if len(nonslaves) == 1:
                devname = nonslaves[0]
                if nm.nm_device_type_is_ethernet(devname):
                    msg = _("Wired (%(interface_name)s) connected") \
                          % {"interface_name": devname}
                elif nm.nm_device_type_is_wifi(devname):
                    msg = _("Wireless connected to %(access_point)s") \
                          % {"access_point" : ssids[devname]}
                elif nm.nm_device_type_is_bond(devname):
                    msg = _("Bond %(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_team(devname):
                    msg = _("Team%(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_bridge(devname):
                    msg = _("Bridge%(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_vlan(devname):
                    parent = nm.nm_device_setting_value(devname, "vlan", "parent")
                    vlanid = nm.nm_device_setting_value(devname, "vlan", "id")
                    msg = _("VLAN %(interface_name)s (%(parent_device)s, ID %(vlanid)s) connected") \
                          % {"interface_name": devname, "parent_device": parent, "vlanid": vlanid}
            elif len(nonslaves) > 1:
                devlist = []
                for devname in nonslaves:
                    if nm.nm_device_type_is_ethernet(devname):
                        devlist.append("%s" % devname)
                    elif nm.nm_device_type_is_wifi(devname):
                        devlist.append("%s" % ssids[devname])
                    elif nm.nm_device_type_is_bond(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_team(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_bridge(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_vlan(devname):
                        devlist.append("%s" % devname)
                msg = _("Connected: %(list_of_interface_names)s") \
                      % {"list_of_interface_names": ", ".join(devlist)}
        else:
            msg = _("Not connected")

    if not nm.nm_devices():
        msg = _("No network devices available")

    return msg

def default_ks_vlan_interface_name(parent, vlanid):
    return "%s.%s" % (parent, vlanid)

def has_some_wired_autoconnect_device():
    """Is there a wired network device with autoconnect?"""
    for dev in nm.nm_devices():
        if nm.nm_device_type_is_wifi(dev):
            continue
        try:
            onboot = nm.nm_device_setting_value(dev, "connection", "autoconnect")
        except nm.SettingsNotFoundError:
            continue
        # None means the setting was not found, which means NM is using
        # default (True)
        if onboot == True or onboot is None:
            return True
    return False

def update_onboot_value(devname, value, ksdata):
    """Update onboot value in ifcfg files and ksdata"""
    log.debug("network: setting ONBOOT value of %s to %s", devname, value)
    ifcfg_path = find_ifcfg_file_of_device(devname, root_path=iutil.getSysroot())
    if not ifcfg_path:
        log.debug("network: can't find ifcfg file of %s", devname)
        return
    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    ifcfg.set(('ONBOOT', 'yes'))
    ifcfg.write()
    for nd in ksdata.network.network:
        if nd.device == devname:
            nd.onboot = True
            break

def is_using_team_device():
    return any(nm.nm_device_type_is_team(d) for d in nm.nm_devices())
