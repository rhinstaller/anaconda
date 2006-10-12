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
from snack import *
from constants_text import *
from constants import *
from rhpl.translate import _

descr = { 'ipaddr':   'IPv4 address',
          'netmask':  'IPv4 network mask',
          'remip':    'point-to-point IP address',
          'ipv6addr': 'IPv6 address'
        }

# order to check input values
checkorder = ['ipaddr', 'netmask', 'ipv6addr', 'ipv6prefix',
              'remip', 'essid', 'key'
             ]

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

class NetworkDeviceWindow:
    def runScreen(self, screen, net, dev, showonboot=1):
        bootproto = dev.get('bootproto').lower()
        onboot = dev.get('onboot')
        v4list = []
        v6list = []
        ptplist = []
        wifilist = []

        def DHCPtoggled():
            active = self.dhcpCb.selected()

            if wifilist:
                for widget in wifilist:
                    widget.setFlags(FLAG_DISABLED, FLAGS_RESET)

            if active:
                bootproto = 'dhcp'

                for widget in v4list:
                    widget.setFlags(FLAG_DISABLED, FLAGS_SET)

                for widget in v6list:
                    widget.setFlags(FLAG_DISABLED, FLAGS_SET)

                if ptplist:
                    for widget in ptplist:
                        widget.setFlags(FLAG_DISABLED, FLAGS_SET)
            else:
                bootproto = 'static'

                if self.ipv4Cb.selected() != 0:
                    for widget in v4list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_RESET)

                    for widget in v6list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_RESET)

                    if ptplist:
                        for widget in ptplist:
                            widget.setFlags(FLAG_DISABLED, FLAGS_RESET)

        def IPV4toggled():
            active = self.ipv4Cb.selected()
            net.useIPv4 = active
            if not self.dhcpCb.selected():
                if active:
                    for widget in v4list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_RESET)
                else:
                    for widget in v4list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_SET)

        def IPV6toggled():
            active = self.ipv6Cb.selected()
            net.useIPv6 = active
            if not self.dhcpCb.selected():
                if active:
                    for widget in v6list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_RESET)
                else:
                    for widget in v6list:
                        widget.setFlags(FLAG_DISABLED, FLAGS_SET)

        devnames = self.devices.keys()
        devnames.sort(cmp=isys.compareNetDevices)
        if devnames.index(dev.get('DEVICE')) == 0 and not onboot:
            onbootIsOn = 1
        else:
            onbootIsOn = (onboot == 'yes')
        if not bootproto:
            bootproto = 'dhcp'

        descr = dev.get('desc')
        hwaddr = dev.get('hwaddr')
        if descr is None or len(descr) == 0:
            descr = None
        if hwaddr is None or len(hwaddr) == 0:
            hwaddr = None

        topgrid = Grid(1, 2)

        if descr is not None:
            topgrid.setField(Label (_("Description: %s") % (descr[:70],)),
                             0, 0, padding = (0, 0, 0, 0), anchorLeft = 1,
                             growx = 1)
        if hwaddr is not None:
            topgrid.setField(Label (_("Hardware Address: %s") %(hwaddr,)),
                             0, 1, padding = (0, 0, 0, 0), anchorLeft = 1,
                             growx = 1)

        # Create options grid
        maingrid = Grid(1, 5)
        mainrow = 0

        if not showonboot:
            ypad = 1
        else:
            ypad = 0

        # DHCP option
        self.dhcpCb = Checkbox(_("Use dynamic IP configuration (DHCP)"),
                               isOn = (bootproto == "dhcp"))
        maingrid.setField(self.dhcpCb, 0, mainrow, anchorLeft = 1, growx = 1,
                          padding = (0, 0, 0, ypad))
        mainrow += 1

        # Use IPv4 option
        self.ipv4Cb = Checkbox(_("Enable IPv4 support"), net.useIPv4)
        maingrid.setField(self.ipv4Cb, 0, mainrow, anchorLeft = 1, growx = 1,
                          padding = (0, 0, 0, ypad))
        mainrow += 1

        # Use IPv6 option
        self.ipv6Cb = Checkbox(_("Enable IPv6 support"), net.useIPv6)
        maingrid.setField(self.ipv6Cb, 0, mainrow, anchorLeft = 1, growx = 1,
                          padding = (0, 0, 0, ypad))
        mainrow += 1

        # Activate on boot option
        self.onbootCb = Checkbox(_("Activate on boot"), isOn = onbootIsOn)
        if showonboot:
            maingrid.setField(self.onbootCb, 0, mainrow, anchorLeft = 1,
                              growx = 1, padding = (0, 0, 0, 1))
            mainrow += 1

        # IP address subtable
        ipTableLength = 3

        if (network.isPtpDev(dev.info['DEVICE'])):
            ipTableLength += 1

        if (isys.isWireless(dev.info['DEVICE'])):
            ipTableLength += 2

        ipgrid = Grid(4, ipTableLength)

        self.dhcpCb.setCallback(DHCPtoggled)
        self.ipv4Cb.setCallback(IPV4toggled)
        self.ipv6Cb.setCallback(IPV6toggled)

        entrys = {}

        # IP subtable labels
        ipgrid.setField(Label(" "), 0, 0)
        ipgrid.setField(Label(_("Address")), 1, 0)
        ipgrid.setField(Label(" "), 2, 0)
        ipgrid.setField(Label(_("Prefix (Netmask)")), 3, 0)
        ipgrid.setField(Label(_("IPv4:")), 0, 1, anchorLeft = 1,
                        padding = (0, 0, 1, 0))
        ipgrid.setField(Label("/"), 2, 1, padding = (1, 0, 1, 0))
        ipgrid.setField(Label(_("IPv6:")), 0, 2, anchorLeft = 1,
                        padding = (0, 0, 1, 0))
        ipgrid.setField(Label("/"), 2, 2, padding = (1, 0, 1, 0))

        # IPv4 entries
        v4list.append(Entry(41))
        v4list[0].set(dev.get('ipaddr'))
        entrys['ipaddr'] = v4list[0]
        ipgrid.setField(v4list[0], 1, 1, anchorLeft = 1)

        v4list.append(Entry(16))
        v4list[1].set(dev.get('netmask'))
        entrys['netmask'] = v4list[1]
        ipgrid.setField(v4list[1], 3, 1, anchorLeft = 1)

        # IPv6 entries
        v6list.append(Entry(41))

        ipv6addr = dev.get('ipv6addr')
        brk = ipv6addr.find('/')
        if brk != -1:
            ipv6addr = ipv6addr[0:brk]
            brk += 1
            ipv6prefix = ipv6addr[brk:]

        v6list[0].set(ipv6addr)
        entrys['ipv6addr'] = v6list[0]
        ipgrid.setField(v6list[0], 1, 2, anchorLeft = 1)

        v6list.append(Entry(16))
        v6list[1].set(dev.get('ipv6prefix'))
        entrys['ipv6prefix'] = v6list[1]
        ipgrid.setField(v6list[1], 3, 2, anchorLeft = 1)

        iprow = 3

        # Point to Point address
        if (network.isPtpDev(dev.info["DEVICE"])):
            ipgrid.setField(Label(_("P-to-P:")), 0, iprow, anchorLeft = 1,
                            padding = (0, 0, 1, 0))

            ptplist.append(Entry(41))
            ptplist[0].set(dev.get('remip'))
            entrys['remip'] = ptplist[0]
            ipgrid.setField(ptplist[0], 1, iprow, anchorLeft = 1)

            iprow += 1

        # Wireless settings
        if (isys.isWireless(dev.info["DEVICE"])):
            ipgrid.setField(Label(_("ESSID:")), 0, iprow, anchorLeft = 1,
                            padding = (0, 0, 1, 0))
            wifilist.append(Entry(41))
            wifilist[0].set(dev.get('essid'))
            entrys['essid'] = wifilist[0]
            ipgrid.setField(wifilist[0], 1, iprow, anchorLeft = 1)

            iprow += 1

            ipgrid.setField(Label(_("WEP Key:")), 0, iprow, anchorLeft = 1,
                            padding = (0, 0, 1, 0))
            wifilist.append(Entry(41))
            wifilist[1].set(dev.get('key'))
            entrys['key'] = wifilist[1]
            ipgrid.setField(wifilist[1], 1, iprow, anchorLeft = 1)

        # Add the IP subtable
        maingrid.setField(ipgrid, 0, mainrow, anchorLeft = 1,
                          growx = 1, padding = (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp(screen, _("Network Configuration for %s") %
                                (dev.info['DEVICE']), "networkdev", 1, 3)

        if ipTableLength == 6:
            pbottom = 0
        else:
            pbottom = 1

        toplevel.add(topgrid,  0, 0, (0, 0, 0, pbottom), anchorLeft = 1)
        toplevel.add(maingrid,  0, 1, (0, 0, 0, 0), anchorLeft = 1)
        toplevel.add(bb, 0, 2, (0, 0, 0, 0), growx = 1, growy = 0)

        self.dhcpCb.isOn = (bootproto == 'dhcp')
        self.ipv4Cb.isOn = net.useIPv4
        self.ipv6Cb.isOn = net.useIPv6

        DHCPtoggled()
        IPV4toggled()
        IPV6toggled()

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if not self.ipv4Cb.selected() and not self.ipv6Cb.selected():
                ButtonChoiceWindow(screen, _("Missing Protocol"),
                    _("You must select at least IPv4 or IPv6 support."),
                    buttons = [_("OK")])
                continue

            if self.onbootCb.selected():
                dev.set(('onboot', 'yes'))
            else:
                dev.unset('onboot')

            if self.dhcpCb.selected():
                dev.set(('bootproto', 'dhcp'))
                dev.unset('ipaddr', 'netmask', 'network', 'broadcast', 'remip')
            else:
                dev.unset('bootproto')
                valsgood = 1
                tmpvals = {}

                for t in checkorder:
                    if not entrys.has_key(t):
                        continue

                    val = entrys[t].value()

                    if ((t == 'ipaddr' or t == 'netmask') and \
                        self.ipv4Cb.selected()) or \
                       (t == 'ipv6addr' and self.ipv6Cb.selected()) or \
                       (t == 'remip'):
                        if t == 'netmask' and val.find('.') == -1:
                            try:
                                if int(val) > 32 or int(val) < 0:
                                    ButtonChoiceWindow(screen,
                                        _("Invalid Prefix"),
                                        _("IPv4 prefix must be between "
                                          "0 and 32."), buttons = [_("OK")])
                                    valsgood = 0
                                    break
                                else:
                                    val = isys.prefix2netmask(int(val))
                            except:
                                handleIPMissing(screen, t)
                                valsgood = 0
                                break

                        try:
                            network.sanityCheckIPString(val)
                            tmpvals[t] = val
                        except network.IPMissing, msg:
                            handleIPMissing(screen, t)
                            valsgood = 0
                            break
                        except network.IPError, msg:
                            handleIPError(screen, t, msg)
                            valsgood = 0
                            break

                    elif t == 'ipv6prefix' and self.ipv6Cb.selected():
                        try:
                            if int(val) > 128 or int(val) < 0:
                                ButtonChoiceWindow(screen, _("Invalid Prefix"),
                                    _("IPv6 prefix must be between 0 and 128."),
                                    buttons = [_("OK")])
                                valsgood = 0
                                break
                        except:
                            ButtonChoiceWindow(screen, _("Invalid Prefix"),
                                _("Invalid or missing IPv6 prefix (must be "
                                  "between 0 and 128)."), buttons = [_("OK")])
                            valsgood = 0
                            break

                if valsgood == 0:
                    continue

                try:
                    (net, bc) = isys.inet_calcNetBroad (tmpvals['ipaddr'],
                                                        tmpvals['netmask'])
                except Exception, e:
                    print e
                    handleBroadCastError()
                    valsgood = 0

                if not valsgood:
                    continue

                for t in entrys.keys():
                    if tmpvals.has_key(t):
                        if t == 'ipv6addr':
                            if entrys['ipv6prefix'] is not None:
                                a = tmpvals[t]
                                if a.find('/') != -1:
                                    a = a[0:a.find('/')]
                                p = entrys['ipv6prefix'].value()
                                q = "%s/%s" % (a, p,)
                            else:
                                q = "%s" % (tmpvals[t],)

                            dev.set((t, q))
                        else:
                            dev.set((t, tmpvals[t]))
                    else:
                        dev.set((t, entrys[t].value()))

                dev.set(('network', net), ('broadcast', bc))

            break

        screen.popWindow()
        return INSTALL_OK

    def __call__(self, screen, anaconda, showonboot=1):
        self.devices = anaconda.id.network.available()
        if not self.devices:
            return INSTALL_NOOP

        list = self.devices.keys()
        list.sort(cmp=isys.compareNetDevices)
        devLen = len(list)
        if anaconda.dir == DISPATCH_FORWARD:
            currentDev = 0
        else:
            currentDev = devLen - 1

        while currentDev < devLen and currentDev >= 0:
            rc = self.runScreen(screen, anaconda.id.network,
                                self.devices[list[currentDev]],
                                showonboot)
            if rc == INSTALL_BACK:
                currentDev = currentDev - 1
            else:
                currentDev = currentDev + 1

        if currentDev < 0:
            return INSTALL_BACK
        else:
            return INSTALL_OK

class NetworkGlobalWindow:
    def __call__(self, screen, anaconda, showonboot = 1):
        devices = anaconda.id.network.available()
        if not devices:
            return INSTALL_NOOP

        # we don't let you set gateway/dns if you've got any interfaces
        # using dhcp (for better or worse)
        if network.anyUsingDHCP(devices):
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
                handleMissingOptionalIP(screen, 'gateway')
                pass
            except network.IPError, msg:
                handleIPError(screen, 'gateway', msg)
                continue

            try:
                network.sanityCheckIPString(ns1Entry.value())
                anaconda.id.network.primaryNS = ns1Entry.value()
            except network.IPMissing, msg:
                handleMissingOptionalIP(screen, 'primary DNS')
                pass
            except network.IPError, msg:
                handleIPError(screen, 'primary DNS', msg)
                continue

            try:
                network.sanityCheckIPString(ns2Entry.value())
                anaconda.id.network.secondaryNS = ns2Entry.value()
            except network.IPMissing, msg:
                pass
            except network.IPError, msg:
                handleIPError(screen, 'secondary DNS', msg)
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
        if network.anyUsingDHCP(devices):
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
        if network.anyUsingDHCP(devices):
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
                                 "select manually and enter in a hostname for "
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
