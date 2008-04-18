#
# minihal.py: Simple wrapper around HAL
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
# Author(s): Bill Nottingham <notting@redhat.com>
#

"""Simple wrapper around HAL"""

import dbus

def get_device(udi):
    """Retrieve all properties of a particular device (by UDI)"""
    try:
        bus = dbus.SystemBus()
        haldev = dbus.Interface(bus.get_object("org.freedesktop.Hal", udi), "org.freedesktop.Hal.Device")
        props = haldev.GetAllProperties()
    except dbus.exceptions.DBusException:
        return None

    if props.has_key('block.device'):
        props['device'] = props['block.device'].encode("utf-8")
    elif props.has_key('linux.device_file'):
        props['device'] = props['linux.device_file'].encode("utf-8")
    elif props.has_key('net.interface'):
        props['device'] = props['net.interface'].encode("utf-8")
    else:
        props['device'] = None

    props['description'] = ''
    if props.has_key('info.product'):
        if props.has_key('info.vendor'):
            props['description'] = '%s %s' % (props['info.vendor'],props['info.product'])
        else:
            props['description'] = props['info.product']
    else:
        props['description'] = props['info.udi']
    if props.has_key('net.originating_device'):
        pdev = get_device(props['net.originating_device'])
        props['description'] = pdev['description']

    return props

def get_devices_by_type(type):
    """Retrieve all devices of a particular type"""
    ret = []
    try:
        bus = dbus.SystemBus()
        hal = dbus.Interface(bus.get_object("org.freedesktop.Hal","/org/freedesktop/Hal/Manager"),"org.freedesktop.Hal.Manager")
    except:
        return ret
    for udi in hal.FindDeviceByCapability(type):
        dev = get_device(udi)
        if dev:
            ret.append(dev)
    return ret
