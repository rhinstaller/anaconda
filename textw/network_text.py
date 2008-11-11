#
# network_text.py: text mode network configuration dialogs
#
# Jeremy Katz <katzj@redhat.com>
# Michael Fulbright <msf@redhat.com>
# David Cantrell <dcantrell@redhat.com>
#
# Copyright 2000-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import os
import isys
import string
import network
import socket
from snack import *
from constants_text import *
from constants import *
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

def handleIPError(screen, field, msg):
    try:
        newfield = descr[field]
    except:
        newfield = field

    ButtonChoiceWindow(screen, _("Error With %s Data") % (newfield,),
                       _("%s") % msg.__str__(), buttons = [ _("OK") ])

def handleIPMissing(screen, field):
    try:
        newfield = descr[field]
    except:
        newfield = field

    ButtonChoiceWindow(screen, _("Error With Data"),
                       _("A value is required for the field %s.")
                       % (newfield,), buttons = [ _("OK") ])

def handleMissingOptionalIP(screen, field):
    ButtonChoiceWindow(screen, _("Error With Data"),
                       _("You have not specified the field %s.  Depending on "
                         "your network environment this may cause problems "
                         "later.") % (field,), buttons = [ _("Continue") ])

def handleBroadCastError(screen):
    ButtonChoiceWindow(screen, _("Error With Data"),
                       _("The IPv4 information you have entered is invalid."))

def handleInvalidPrefix(screen, family):
    if family == socket.AF_INET:
        ver = 4
        upper = 32
    elif family == socket.AF_INET6:
        ver = 6
        upper = 128

    ButtonChoiceWindow(screen, _("Invalid Prefix"),
        _("IPv%d prefix must be between 0 and %d." % (ver, upper,)),
        buttons = [_("OK")])

def handleValueErrorPrefix(screen, field):
    ButtonChoiceWindow(screen, _("Integer Required for Prefix"),
        _("You must enter a valid integer for the %s.  For IPv4, the "
          "value can be between 0 and 32.  For IPv6 it can be between "
          "0 and 128." % (field,)), buttons = [_("OK")])

class NetworkDeviceWindow:
    def createManualEntryGrid(self, ipEntry, prefixEntry, family):
        if family == socket.AF_INET:
            prefixLabel = Label(_("Prefix (Netmask)"))
        elif family == socket.AF_INET6:
            prefixLabel = Label(_("Prefix"))

        manualgrid = Grid(3, 2)

        manualgrid.setField(Label(_("IP Address")), 0, 0, anchorLeft = 1,
                            padding = (4, 0, 0, 0))
        manualgrid.setField(ipEntry, 0, 1, anchorLeft = 1,
                            padding = (4, 0, 0, 0))
        manualgrid.setField(Label("/"), 1, 1, anchorLeft = 1,
                            padding = (1, 0, 1, 0))
        manualgrid.setField(prefixLabel, 2, 0, anchorLeft = 1)
        manualgrid.setField(prefixEntry, 2, 1, anchorLeft = 1)
        manualgrid.setField(Label(" "), 1, 0, anchorLeft = 1,
                            padding = (1, 0, 1, 0))

        return manualgrid

    def ipMethodCb(self, obj):
        (radio, ipEntry, prefixEntry) = obj
        if radio.getSelection() == "static":
            sense = FLAGS_RESET
        else:
            sense = FLAGS_SET
        ipEntry.setFlags(FLAG_DISABLED, sense)
        prefixEntry.setFlags(FLAG_DISABLED, sense)

    def runMainScreen(self, screen, dev, showonboot=1):
        onboot = dev.get('onboot')
        isPtp = network.isPtpDev(dev.info["DEVICE"])
        isWifi = isys.isWireless(dev.info["DEVICE"])

        devnames = self.devices.keys()
        devnames.sort(cmp=isys.compareNetDevices)
        if devnames.index(dev.get('DEVICE')) == 0 and not onboot:
            onbootIsOn = 1
        else:
            onbootIsOn = (onboot == 'yes')

        # Create options grid
        ipmiscrows = 0
        if isPtp:
            ipmiscrows += 1
        if isWifi:
            ipmiscrows += 2

        maingridrows = 5
        if ipmiscrows > 0:
            maingridrows += 1

        maingrid = Grid(1, maingridrows)
        mainrow = 0

        # Activate on boot option
        onbootCb = Checkbox(_("Activate on boot"), isOn = onbootIsOn)
        if showonboot:
            maingrid.setField(onbootCb, 0, mainrow, anchorLeft = 1,
                              growx = 1, padding = (0, 0, 0, 0))
            mainrow += 1

        # Use IPv4 option
        ipv4Cb = Checkbox(_("Enable IPv4 support"),
                          int(bool(dev.get('useIPv4'))))
        maingrid.setField(ipv4Cb, 0, mainrow, anchorLeft = 1, growx = 1,
                          padding = (0, 0, 0, 0))
        mainrow += 1

        # Use IPv6 option
        ipv6Cb = Checkbox(_("Enable IPv6 support"),
                          int(bool(dev.get('useIPv6'))))
        maingrid.setField(ipv6Cb, 0, mainrow, anchorLeft = 1, growx = 1,
                          padding = (0, 0, 0, 0))
        mainrow += 1

        if ipmiscrows > 0:
            ipmiscgrid = Grid(2, ipmiscrows)
            ipmiscrow = 0

        # Point to Point address
        ptpaddr = None
        if isPtp:
            ipmiscgrid.setField(Label(_("P-to-P:")), 0, ipmiscrow,
                                anchorLeft = 1, padding = (0, 1, 1, 0))
            ptpaddr = Entry(41)
            ptpaddr.set(dev.get('remip'))
            ipmiscgrid.setField(ptpaddr, 1, ipmiscrow, anchorLeft = 1,
                                padding = (0, 1, 0, 0))

            ipmiscrow += 1

        # Wireless settings
        essid = None
        wepkey = None
        if isWifi:
            if isPtp:
                padtop = 0
            else:
                padtop = 1

            ipmiscgrid.setField(Label(_("ESSID:")), 0, ipmiscrow,
                                anchorLeft = 1, padding = (0, padtop, 1, 0))
            essid = Entry(41)
            essid.set(dev.get('essid'))
            ipmiscgrid.setField(essid, 1, ipmiscrow, anchorLeft = 1,
                                padding = (0, padtop, 0, 0))

            ipmiscrow += 1

            ipmiscgrid.setField(Label(_("WEP Key:")), 0, ipmiscrow,
                                anchorLeft = 1, padding = (0, 0, 1, 0))
            wepkey = Entry(41)
            wepkey.set(dev.get('key'))
            ipmiscgrid.setField(wepkey, 1, ipmiscrow, anchorLeft = 1)

        # Add the IP misc subtable
        if ipmiscrows > 0:
            maingrid.setField(ipmiscgrid, 0, mainrow, anchorLeft = 1,
                              growx = 1, padding = (0, 0, 0, 0))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp(screen, _("Network Configuration for %s") %
                                (dev.info['DEVICE']), "networkdev", 1, 5)

        toplevel.add(self.topgrid, 0, 0, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(maingrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(bb, 0, 2, (0, 1, 0, 0), growx = 1, growy = 0)

        ipv4Cb.isOn = int(bool(dev.get('useIPv4')))
        ipv6Cb.isOn = int(bool(dev.get('useIPv6')))

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if not ipv4Cb.selected() and not ipv6Cb.selected():
                ButtonChoiceWindow(screen, _("Missing Protocol"),
                    _("You must select at least IPv4 or IPv6 support."),
                    buttons = [_("OK")])
                continue

            dev.set(('useIPv4', bool(ipv4Cb.selected())))
            dev.set(('useIPv6', bool(ipv6Cb.selected())))

            if onbootCb.selected():
                dev.set(('onboot', 'yes'))
            else:
                dev.unset('onboot')

            if isPtp:
                try:
                    network.sanityCheckIPString(ptpaddr.value())
                    dev.set(('remip', ptpaddr.value()))
                except network.IPMissing, msg:
                    handleIPMissing(screen, _("point-to-point IP address"))
                    continue
                except network.IPError, msg:
                    handleIPError(screen, _("point-to-point IP address"), msg)
                    continue

            if isWifi:
                if essid is not None:
                    if not essid.value() == '':
                        dev.set(('essid', essid.value()))

                if wepkey is not None:
                    if not wepkey.value() == '':
                        dev.set(('key', wepkey.value()))

            break

        screen.popWindow()
        return INSTALL_OK

    def runIPv4Screen(self, screen, dev):
        bootproto = dev.get('bootproto').lower()
        if not bootproto == "query" and \
           not bootproto == "dhcp" and \
           not bootproto == "static":
            dev.set(('bootproto', 'dhcp'))
            bootproto = dev.get('bootproto').lower()

        radio = RadioGroup()

        maingrid = Grid(1, 3)
        dhcpCb = radio.add(_("Dynamic IP configuration (DHCP)"),
                           "dhcp", (bootproto == "dhcp"))
        maingrid.setField(dhcpCb, 0, 0, growx = 1, anchorLeft = 1)
        manualCb = radio.add(_("Manual address configuration"),
                             "static", (bootproto == "static"))
        maingrid.setField(manualCb, 0, 1, growx = 1, anchorLeft = 1)

        ipEntry = Entry(16)
        ipEntry.set(dev.get('ipaddr'))
        prefixEntry = Entry(16)
        prefixEntry.set(dev.get('netmask'))

        manualgrid = self.createManualEntryGrid(ipEntry, prefixEntry,
                                                socket.AF_INET)
        maingrid.setField(manualgrid, 0, 2, anchorLeft = 1, growx = 1,
                          padding = (0, 1, 0, 0))
        dhcpCb.setCallback(self.ipMethodCb, (radio, ipEntry, prefixEntry))
        manualCb.setCallback(self.ipMethodCb, (radio, ipEntry, prefixEntry))

        self.ipMethodCb((radio, ipEntry, prefixEntry))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        title = _("IPv4 Configuration for %s") % (dev.info['DEVICE'])
        toplevel = GridFormHelp(screen, title, "networkipv4", 1, 5)

        toplevel.add(self.topgrid, 0, 0, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(maingrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(bb, 0, 2, (0, 1, 0, 0), growx = 1, growy = 0)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            bootproto = radio.getSelection()
            dev.set(('bootproto', bootproto))

            if bootproto == 'dhcp':
                dev.unset('ipaddr')
                dev.unset('netmask')
                dev.unset('network')
                dev.unset('broadcast')
                break

            ip = ipEntry.value()
            nm = prefixEntry.value()

            # check for missing values
            if ip == '' or ip is None:
                handleIPMissing(screen, _('IPv4 address'))
                continue

            if nm == '' or nm is None:
                handleIPMissing(screen, _('IPv4 network mask'))
                continue

            # validate IP address
            try:
                network.sanityCheckIPString(ip)
                dev.set(('ipaddr', ip))
            except network.IPMissing, msg:
                handleIPMissing(screen, _('IPv4 address'))
                continue
            except network.IPError, msg:
                handleIPError(screen, _('IPv4 address'), msg)
                continue

            # validate prefix (netmask)
            try:
                if nm.find('.') == -1:
                    if int(nm) > 32 or int(nm) < 0:
                        handleInvalidPrefix(screen, socket.AF_INET)
                        continue
                    else:
                        nm = isys.prefix2netmask(int(nm))

                network.sanityCheckIPString(nm)
                dev.set(('netmask', nm))
            except network.IPMissing, msg:
                handleIPMissing(screen, _('IPv4 prefix (network mask)'))
                continue
            except network.IPError, msg:
                handleIPError(screen, _('IPv4 prefix (network mask)'), msg)
                continue
            except ValueError:
                handleValueErrorPrefix(screen, _('IPv4 prefix (network mask)'))
                continue

            # calculate network and broadcast addresses (IPv4-only)
            try:
                (net, bc) = isys.inet_calcNetBroad(dev.get('ipaddr'),
                                                   dev.get('netmask'))
                dev.set(('network', net), ('broadcast', bc))
            except Exception, e:
                handleBroadCastError(screen)
                continue 

            break

        screen.popWindow()
        return INSTALL_OK

    def runIPv6Screen(self, screen, dev):
        ipv6autoconf = dev.get('ipv6_autoconf').lower()
        ipv6addr = dev.get('ipv6addr')
        ipv6prefix = None
        brk = ipv6addr.find('/')
        if brk != -1:
            ipv6addr = ipv6addr[0:brk]
            brk += 1
            ipv6prefix = ipv6addr[brk:]

        # default to automatic neighbor discovery if no ipv6 values exist
        if ipv6autoconf == '' or ipv6autoconf is None or \
           ipv6addr == '' or ipv6addr is None:
            ipv6autoconf = 'yes'
            ipv6addr = None
            ipv6prefix = None
            dev.unset('ipv6_autoconf')
            dev.unset('ipv6addr')

        radio = RadioGroup()

        maingrid = Grid(1, 4)
        autoCb = radio.add(_('Automatic neighbor discovery'), 'auto',
                           (ipv6autoconf == 'yes'))
        maingrid.setField(autoCb, 0, 0, growx = 1, anchorLeft = 1)
        dhcpCb = radio.add(_('Dynamic IP configuration (DHCPv6)'), 'dhcp',
                           (ipv6addr is not None and ipv6addr == 'dhcp'))
        maingrid.setField(dhcpCb, 0, 1, growx = 1, anchorLeft = 1)
        manualCb = radio.add(_('Manual address configuration'), 'static',
                             (ipv6addr is not None and ipv6addr != 'dhcp'))
        maingrid.setField(manualCb, 0, 2, growx = 1, anchorLeft = 1)

        manualgrid = Grid(3, 2)
        ipEntry = Entry(41)
        prefixEntry = Entry(6)
        if radio.getSelection() == 'static':
            ipEntry.set(ipv6addr)
            if ipv6prefix is not None:
                prefixEntry.set(ipv6prefix)

        manualgrid = self.createManualEntryGrid(ipEntry, prefixEntry,
                                                socket.AF_INET6)
        maingrid.setField(manualgrid, 0, 3, anchorLeft = 1, growx = 1,
                          padding = (0, 1, 0, 0))
        autoCb.setCallback(self.ipMethodCb, (radio, ipEntry, prefixEntry))
        dhcpCb.setCallback(self.ipMethodCb, (radio, ipEntry, prefixEntry))
        manualCb.setCallback(self.ipMethodCb, (radio, ipEntry, prefixEntry))

        self.ipMethodCb((radio, ipEntry, prefixEntry))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        title = _("IPv6 Configuration for %s") % (dev.info['DEVICE'])
        toplevel = GridFormHelp(screen, title, "networkipv6", 1, 6)

        toplevel.add(self.topgrid, 0, 0, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(maingrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(bb, 0, 2, (0, 1, 0, 0), growx = 1, growy = 0)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            dev.unset('ipv6_autoconf')
            dev.unset('ipv6addr')

            if radio.getSelection() == 'auto':
                dev.set(('ipv6_autoconf', 'yes'))
                break
            elif radio.getSelection() == 'dhcp':
                dev.set(('ipv6addr', 'dhcp'))
                break

            ip = ipEntry.value()
            prefix = prefixEntry.value()

            # check for missing values
            if ip == '' or ip is None:
                handleIPMissing(screen, _('IPv6 address'))
                continue

            if prefix == '' or prefix is None:
                handleIPMissing(screen, _('IPv6 prefix'))
                continue

            # validate the IP address
            try:
                network.sanityCheckIPString(ip)
            except network.IPMissing, msg:
                handleIPMissing(screen, _('IPv6 address'))
                continue
            except network.IPError, msg:
                handleIPError(screen, _('IPv6 address'), msg)
                continue

            # validate the prefix
            try:
                if int(prefix) > 128 or int(prefix) < 0:
                    handleInvalidPrefix(screen, socket.AF_INET6)
                    continue
            except:
                handleValueErrorPrefix(screen, _('IPv6 prefix'))
                continue

            # set the manual IPv6 address/prefix
            if prefix != '':
                addr = "%s/%s" % (ip, prefix,)
            else:
                addr = "%s" % (ip,)

            dev.set(('ipv6addr', addr))

            break

        screen.popWindow()
        return INSTALL_OK

    def chooseNetworkDevice(self, screen):
        devs = self.devices.keys()
        devs.sort(cmp=isys.compareNetDevices)

        # return if there are no NICs
        if len(devs) == 0:
            return INSTALL_OK

        # only ask Yes/No if this system has just one NIC (most end users)
        if len(devs) == 1:
            rc = self.intf.messageWindow(_("Configure Network Interface"),
                     _("Would you like to configure the %s network "
                       "interface in your system?") % (devs[0],),
                     type = "yesno")

            if rc == 1:
                return self.devices[devs[0]]
            else:
                return INSTALL_OK

        # create list box of network devices
        devList = Listbox(height=5, scroll=1)
        for item in devs:
            try:
                if self.devListDescs[item] is None:
                    self.devListDescs[item] = _("UNCONFIGURED")
            except KeyError, e:
                self.devListDescs[item] = _("UNCONFIGURED")

            desc = "%s: %s" % (item, self.devListDescs[item],)
            devList.append(desc, item)

        # create some sort of dialog box
        toplevel = GridFormHelp(screen, _("Network Configuration"),
                                "netconfig", 1, 5)
        text = TextboxReflowed(65,
                               _("The current configuration settings for each "
                                 "interface are listed next to the device "
                                 "name.  Unconfigured interfaces are shown as "
                                 "UNCONFIGURED.  To configure an interface, "
                                 "highlight it and choose Edit.  When you are "
                                 "finished, press OK to continue."))
        toplevel.add(text, 0, 0, (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_EDIT_BUTTON,
                                TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel.add(devList, 0, 1, padding = (0, 0, 0, 0))
        toplevel.add(bb, 0, 2, (0, 1, 0, 0), growx = 1, growy = 0)

        result = toplevel.run()
        while result != TEXT_F12_CHECK:
            rc = bb.buttonPressed (result)

            devname = devList.current()

            screen.popWindow()
            if rc == TEXT_BACK_CHECK:
                return INSTALL_BACK
            elif rc == TEXT_OK_CHECK:
                return INSTALL_OK
            elif rc == TEXT_EDIT_CHECK:
                return self.devices[devname]
            result = toplevel.run()

        screen.popWindow()
        return INSTALL_OK

    def __call__(self, screen, anaconda, showonboot=1):
        self.intf = anaconda.intf
        self.devListDescs = {}
        self.devices = anaconda.id.network.available()

        if not self.devices:
            return INSTALL_NOOP

        for (key, dev) in self.devices.iteritems():
            # set the listbox description text
            if bool(dev.get('onboot')):
                onboot = _("Active on boot")
            else:
                onboot = _("Inactive on boot")

            if dev.get('bootproto').lower() == 'dhcp':
                ipv4 = _("DHCP")
            else:
                ipv4 = dev.get('ipaddr')

            if bool(dev.get('ipv6_autoconf')):
                ipv6 = _("Auto IPv6")
            elif dev.get('ipv6addr').lower() == 'dhcp':
                ipv6 = _("DHCPv6")
            else:
                ipv6 = dev.get('ipv6addr')

            devname = dev.get('device').lower()
            if ipv4 != '' and ipv6 != '':
                desc = _("%s, %s, %s") % (onboot, ipv4, ipv6,)
            elif ipv4 != '' and ipv6 == '':
                desc = _("%s, %s") % (onboot, ipv4,)
            elif ipv4 == '' and ipv6 != '':
                desc = _("%s, %s") % (onboot, ipv6,)
            else:
                desc = None
            self.devListDescs[devname] = desc

        # collect configuration data for each interface selected by the user
        doConf = True
        while doConf is True:
            if len(self.devices) == 1 and doConf is False:
                return INSTALL_OK

            dev = self.chooseNetworkDevice(screen)

            if dev == INSTALL_OK or dev == INSTALL_BACK:
                doConf = False
                return dev

            descr = dev.get('desc')
            hwaddr = dev.get('hwaddr')
            if descr is None or len(descr) == 0:
                descr = None
            if hwaddr is None or len(hwaddr) == 0:
                hwaddr = None

            self.topgrid = Grid(1, 2)

            if descr is not None:
                self.topgrid.setField(Label (_("%s") % (descr[:70],)),
                                      0, 0, padding = (0, 0, 0, 0),
                                      anchorLeft = 1, growx = 1)
            if hwaddr is not None:
                self.topgrid.setField(Label (_("%s") %(hwaddr,)),
                                      0, 1, padding = (0, 0, 0, 1),
                                      anchorLeft = 1, growx = 1)

            # 1st netconfig dialog: protocol and active on boot
            rc = self.runMainScreen(screen, dev, showonboot)
            if rc == INSTALL_BACK:
                continue
            else:
                doIPv4 = bool(dev.get('useIPv4'))
                doIPv6 = bool(dev.get('useIPv6'))

            # 2nd netconfig dialog: IPv4 settings
            if doIPv4:
                rc = self.runIPv4Screen(screen, dev)
                if rc == INSTALL_BACK:
                    continue

            # 3rd netconfig dialog: IPv6 settings
            if doIPv6:
                rc = self.runIPv6Screen(screen, dev)
                if rc == INSTALL_BACK:
                    continue

            # set the listbox description text
            if bool(dev.get('onboot')):
                onboot = _("Active on boot")
            else:
                onboot = _("Inactive on boot")

            if dev.get('bootproto').lower() == 'dhcp':
                ipv4 = _("DHCP")
            else:
                ipv4 = dev.get('ipaddr')

            if bool(dev.get('ipv6_autoconf')):
                ipv6 = _("Auto IPv6")
            elif dev.get('ipv6addr').lower() == 'dhcp':
                ipv6 = _("DHCPv6")
            else:
                ipv6 = dev.get('ipv6addr')

            devname = dev.get('device').lower()
            if ipv4 != '' and ipv6 != '':
                desc = _("%s, %s, %s") % (onboot, ipv4, ipv6,)
            elif ipv4 != '' and ipv6 == '':
                desc = _("%s, %s") % (onboot, ipv4,)
            elif ipv4 == '' and ipv6 != '':
                desc = _("%s, %s") % (onboot, ipv6,)
            self.devListDescs[devname] = desc

            if len(self.devices) == 1 and doConf is True:
                doConf = False

        return INSTALL_OK


class NetworkGlobalWindow:
    def __call__(self, screen, anaconda, showonboot = 1):
        devices = anaconda.id.network.available()
        if not devices:
            return INSTALL_NOOP

        # we don't let you set gateway/dns if you've got any interfaces
        # using dhcp (for better or worse)
        if network.anyUsingDHCP(devices, anaconda):
            return INSTALL_NOOP

        thegrid = Grid(2, 4)

        thegrid.setField(Label(_("Gateway:")), 0, 0, anchorLeft = 1)
        gwEntry = Entry(41)
        # if it's set already, use that... otherwise, make them enter it
        if anaconda.id.network.gateway:
            gwEntry.set(anaconda.id.network.gateway)
        else:
            gwEntry.set("")
        thegrid.setField(gwEntry, 1, 0, padding = (1, 0, 0, 0))
        
        thegrid.setField(Label(_("Primary DNS:")), 0, 1, anchorLeft = 1)
        ns1Entry = Entry(41)
        ns1Entry.set(anaconda.id.network.primaryNS)
        thegrid.setField(ns1Entry, 1, 1, padding = (1, 0, 0, 0))
        
        thegrid.setField(Label(_("Secondary DNS:")), 0, 2, anchorLeft = 1)
        ns2Entry = Entry(41)
        ns2Entry.set(anaconda.id.network.secondaryNS)
        thegrid.setField(ns2Entry, 1, 2, padding = (1, 0, 0, 0))
        
        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp (screen, _("Miscellaneous Network Settings"),
                                 "miscnetwork", 1, 3)
        toplevel.add (thegrid, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add (bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            try:
                network.sanityCheckIPString(gwEntry.value())
                anaconda.id.network.gateway = gwEntry.value()
            except network.IPMissing, msg:
                handleMissingOptionalIP(screen, _("gateway"))
                pass
            except network.IPError, msg:
                handleIPError(screen, _("gateway"), msg)
                continue

            try:
                network.sanityCheckIPString(ns1Entry.value())
                anaconda.id.network.primaryNS = ns1Entry.value()
            except network.IPMissing, msg:
                handleMissingOptionalIP(screen, _("primary DNS"))
                pass
            except network.IPError, msg:
                handleIPError(screen, _("primary DNS"), msg)
                continue

            try:
                network.sanityCheckIPString(ns2Entry.value())
                anaconda.id.network.secondaryNS = ns2Entry.value()
            except network.IPMissing, msg:
                pass
            except network.IPError, msg:
                handleIPError(screen, _("secondary DNS"), msg)
                continue

            break

        screen.popWindow()        
        return INSTALL_OK
        
class HostnameWindow:
    def hostTypeCb(self, (radio, hostEntry)):
        if radio.getSelection() != "manual":
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        hostEntry.setFlags(FLAG_DISABLED, sense)
            
    def __call__(self, screen, anaconda):
        devices = anaconda.id.network.available ()
        if not devices:
            return INSTALL_NOOP

        # figure out if the hostname is currently manually set
        if network.anyUsingDHCP(devices, anaconda):
            if (anaconda.id.network.hostname != "localhost.localdomain" and
                anaconda.id.network.overrideDHCPhostname):
                manual = 1
            else:
                manual = 0
        else:
            manual = 1

        thegrid = Grid(2, 2)
        radio = RadioGroup()
        autoCb = radio.add(_("automatically via DHCP"), "dhcp", not manual)
        thegrid.setField(autoCb, 0, 0, growx = 1, anchorLeft = 1)

        manualCb = radio.add(_("manually"), "manual", manual)
        thegrid.setField(manualCb, 0, 1, anchorLeft = 1)
        hostEntry = Entry(24)
        if anaconda.id.network.hostname != "localhost.localdomain":
            hostEntry.set(anaconda.id.network.hostname)
        thegrid.setField(hostEntry, 1, 1, padding = (1, 0, 0, 0),
                         anchorLeft = 1)            

        # disable the dhcp if we don't have any dhcp
        if network.anyUsingDHCP(devices, anaconda):
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)            
        else:
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

        self.hostTypeCb((radio, hostEntry))

        autoCb.setCallback(self.hostTypeCb, (radio, hostEntry))
        manualCb.setCallback(self.hostTypeCb, (radio, hostEntry))

        toplevel = GridFormHelp(screen, _("Hostname Configuration"),
                                "hostname", 1, 4)
        text = TextboxReflowed(55,
                               _("If your system is part of a larger network "
                                 "where hostnames are assigned by DHCP, "
                                 "select automatically via DHCP. Otherwise, "
                                 "select manually and enter a hostname for "
                                 "your system. If you do not, your system "
                                 "will be known as 'localhost.'"))
        toplevel.add(text, 0, 0, (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add(thegrid, 0, 1, padding = (0, 0, 0, 1))
        toplevel.add(bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)
            
            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if radio.getSelection() != "manual":
                anaconda.id.network.overrideDHCPhostname = 0
                anaconda.id.network.hostname = "localhost.localdomain"
            else:
                hname = string.strip(hostEntry.value())
                if len(hname) == 0:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("You have not specified a hostname."),
                                       buttons = [ _("OK") ])
                    continue
                neterrors = network.sanityCheckHostname(hname)
                if neterrors is not None:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("The hostname \"%s\" is not valid "
                                         "for the following reason:\n\n%s")
                                       %(hname, neterrors),
                                       buttons = [ _("OK") ])
                    continue

                anaconda.id.network.overrideDHCPhostname = 1
                anaconda.id.network.hostname = hname
            break

        screen.popWindow()
        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
