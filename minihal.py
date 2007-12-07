#
# minihal.py: Simple wrapper around HAL
#
# Bill Nottingham <notting@redhat.com>
#
# Copyright 2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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
        props['device'] = props['block.device']
    elif props.has_key('linux.device_file'):
        props['device'] = props['linux.device_file']
    elif props.has_key('net.interface'):
        props['device'] = props['net.interface']
    else:
        props['device'] = None

    if props.has_key('info.product'):
        if props.has_key('info.vendor'):
            props['description'] = '%s %s' % (props['info.vendor'],props['info.product'])
        else:
            props['description'] = props['info.product']
    else:
        props['description'] = props['info.udi']
    if props.has_key('net.physical_device'):
        pdev = get_device(props['net.physical_device'])
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
