#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

"""
A GeoIP and WiFi location module - location detection based on IP address

How to use the geolocation module

First call init_geolocation() - this creates the LocationInfo singleton and
you can also use it to set what geolocation provider should be used.
To actually look up current position, call refresh() - this will trigger
the actual online geolocation query, which runs in a thread.
After the look-up thread finishes, the results are stored in the singleton
and can be retrieved using the get_territory_code() and get_result() methods.
If you call these methods without calling refresh() first or if the look-up
is currently in progress, both return None.

Geolocation backends

This module currently supports three geolocation backends:
* Fedora GeoIP API
* Hostip GeoIP
* Google WiFi

Fedora GeoIP backend
This is the default backend. It queries the Fedora GeoIP API for location
data based on current public IP address. The reply is JSON formated and
contains the following fields:
postal_code, latitude, longitude, region, city, country_code, country_name,
time_zone, country_code3, area_code, metro_code, region_name and dma_code
Anaconda currently uses just time_zone and country_code.

Hostip backend
A GeoIP look-up backend that can be used to determine current country code
from current public IP address. The public IP address is determined
automatically when calling the API.
GeoIP results from Hostip contain the current public IP and an approximate
address. To get this detail location info, use the get_result() method
to get an instance of the LocationResult class, used to wrap the result.

Google WiFi backend
This backend is probably the most accurate one, at least as long as the
computer has a working WiFi hardware and there are some WiFi APs nearby.
It sends data about nearby APs (ssid, MAC address & signal strength)
acquired from Network Manager to a Google API to get approximate
geographic coordinates. If there are enough AP nearby (such as in a
normal city) it can be very accurate, even up to currently determining
which building is the computer currently in.
But this only returns current geographic coordinates, to get country code
the Nominatim reverse-geocoding API is called to convert the coordinates
to an address, which includes a country code.
While having many advantages, this backend also has some severe disadvantages:
* needs working WiFi hardware
* tells your public IP address & possibly quite precise geographic coordinates
  to two external entities (Google and Nominatim)
This could have severe privacy issues and should be carefully considered before
enabling it to be used by default.
* the Google WiFi geolocation API seems to lack official documentation
As a result its long-term stability might not be guarantied.



Possible issues with GeoIP

"I'm in Switzerland connected to corporate VPN and anaconda tells me
I'm in Netherlands."
The public IP address is not directly mapped to the physical location
of a computer. So while your world visible IP address is registered to
an IP block assigned to an ISP in Netherlands, it is just the external
address of the Internet gateway of  your corporate network.
As VPNs and proxies can connect two computers anywhere on Earth,
this issue is unfortunately probably unsolvable.


Backends that could possibly be used in the future
* GPS geolocation
+ doesn't leak your coordinates to a third party
(not entirely true for assisted GPS)
- unassisted cold GPS startup can take tens of minutes to acquire a GPS fix
+ assisted GPS startup (as used in most smartphones) can acquire a fix
in a couple seconds
* cell tower geolocation

"""

import urllib
import urllib2
import json
import dbus
import threading
import time
from pyanaconda import network

import logging
log = logging.getLogger("anaconda")
slog = logging.getLogger("sensitive-info")

from pyanaconda import constants
from pyanaconda.threads import AnacondaThread, threadMgr
from pyanaconda.timezone import get_preferred_timezone, is_valid_timezone

location_info_instance = None
refresh_condition = threading.Condition()
refresh_in_progress = False


def init_geolocation(provider_id=constants.GEOLOC_DEFAULT_PROVIDER):
    """Prepare the geolocation module for handling geolocation queries.
    This method sets-up the GeoLocation instance with the given
    geolocation_provider (or using the default one if no provider
    is given. Please note that calling this method doesn't actually
    execute any queries by itself, you need to call refresh()
    to do that.

    :param provider_id: specifies what geolocation backend to use
    """

    global location_info_instance
    location_info_instance = LocationInfo(provider_id=provider_id)


def refresh():
    """Refresh information about current location using the currently specified
    geolocation provider.
    """
    if location_info_instance:
        location_info_instance.refresh()
    else:
        log.debug("Geoloc: refresh() called before init_geolocation()")


def get_territory_code(wait=False):
    """This function returns the current country code
    or None, if:
    - no results were found
    - the lookup is still in progress
    - the geolocation module was not activated (init & refresh were not called)
     - this is for example the case during image and directory installs

    :param wait: wait for lookup in progress to finish
    False - don't wait
    True - wait for default period
    number - wait for up to number seconds
    :type wait:  bool or number
    :return: current country code or None if not known
    :rtype: string or None
    """
    if _get_location_info_instance(wait):
        return location_info_instance.get_territory_code()
    else:
        return None


def get_timezone(wait=False):
    """This function returns the current time zone
    or None, if:
    - no timezone was found
    - the lookup is still in progress
    - the geolocation module was not activated (init & refresh were not called)
     - this is for example the case during image and directory installs

    :param wait: wait for lookup in progress to finish
    False - don't wait
    True - wait for default period
    number - wait for up to number seconds
    :type wait:  bool or number
    :return: current timezone or None if not known
    :rtype: string or None
    """
    if _get_location_info_instance(wait):
        return location_info_instance.get_timezone()
    else:
        return None


def get_result(wait=False):
    """Returns the current geolocation result wrapper
    or None, if:
    - no results were found
    - the refresh is still in progress
    - the geolocation module was not activated (init & refresh were not called)
     - this is for example the case during image and directory installs

    :param wait: wait for lookup in progress to finish
    False - don't wait
    True - wait for default period
    number - wait for up to number seconds
    :type wait:  bool or number
    :return: LocationResult instance or None if location is unknown
    :rtype: LocationResult or None
    """
    if _get_location_info_instance(wait):
        return location_info_instance.get_result()
    else:
        return None


def get_provider_id_from_option(option_string):
    """Get a valid provider id from a string
    This function is used to parse command line
    arguments/boot options for the geolocation module.

    :param option_string: option specifying the provider
    :type option_string: string
    :return: provider id
    """

    providers = {
        constants.GEOLOC_PROVIDER_FEDORA_GEOIP,
        constants.GEOLOC_PROVIDER_HOSTIP
    }
    if option_string in providers:
        return option_string
    else:
        # fall back to the default provider
        return None


def _get_provider(provider_id):
    """Return GeoIP provider instance based on the provider id
    If the provider id is unknown, return the default provider.

    :return: GeolocationBackend subclass instance
    :rtype: GeolocationBackend subclass
    """

    providers = {
        constants.GEOLOC_PROVIDER_FEDORA_GEOIP: FedoraGeoIPProvider,
        constants.GEOLOC_PROVIDER_HOSTIP: HostipGeoIPProvider,
        constants.GEOLOC_PROVIDER_GOOGLE_WIFI: GoogleWiFiLocationProvider
    }
    # if unknown provider id is specified,
    # use the Fedora GeoIP provider
    default_provider = FedoraGeoIPProvider
    provider = providers.get(provider_id, default_provider)
    return provider()


def _get_location_info_instance(wait=False):
    """Return instance of the location info object
    and optionally wait for the Geolocation thread to finish

    If there is no lookup in progress (no Geolocation refresh thread
    is running), this function returns at once).

    Meaning of the wait parameter:
    - False or <=0: don't wait
    - True : wait for default number of seconds specified by
    the GEOLOC_TIMEOUT constant
    - >0 : wait for a given number of seconds

    :param wait: specifies if this function should wait
    for the lookup to finish before returning the instance
    :type wait: bool or integer or float
    """
    if not wait:
        # just returns the instance
        return location_info_instance

    # check if wait is a boolean or a number
    if wait is True:
        # use the default waiting period
        wait = constants.GEOLOC_TIMEOUT
    # check if there is a refresh in progress
    start_time = time.time()
    refresh_condition.acquire()
    if refresh_in_progress:
        # calling wait releases the lock and blocks,
        # after the thread is notified, it unblocks and
        # reacquires the lock
        refresh_condition.wait(timeout=wait)
        if refresh_in_progress:
            log.info("Waiting for Geolocation timed out after %d seconds.", wait)
            # please note that this does not mean that the actual
            # geolocation lookup was stopped in any way, it just
            # means the caller was unblocked after the waiting period
            # ended while the lookup thread is still running
        else:
            elapsed_time = time.time() - start_time
            log.info("Waited %1.2f seconds for Geolocation", elapsed_time)
    refresh_condition.release()
    return location_info_instance


class GeolocationError(Exception):
    """Exception class for geolocation related errors"""
    pass


class LocationInfo(object):
    """Determines current location based on IP address or
    nearby WiFi access points (depending on what backend is used)
    """

    def __init__(self,
                 provider_id=constants.GEOLOC_DEFAULT_PROVIDER,
                 refresh_now=False):
        """
        :param provider_id: GeoIP provider id specified by module constant
        :param refresh_now: if a GeoIP information refresh should be done
        once the class is initialized
        :type refresh_now: bool
        """
        self._provider = _get_provider(provider_id)
        if refresh_now:
            self.refresh()

    def refresh(self):
        """Refresh location info"""
        # first check if a provider is available
        if self._provider is None:
            log.error("Geoloc: can't refresh - no provider")
            return

        # then check if a refresh is already in progress
        if threadMgr.get(constants.THREAD_GEOLOCATION_REFRESH):
            log.debug("Geoloc: refresh already in progress")
        else:  # wait for Internet connectivity
            if network.wait_for_connectivity():
                threadMgr.add(AnacondaThread(
                    name=constants.THREAD_GEOLOCATION_REFRESH,
                    target=self._provider.refresh))
            else:
                log.error("Geolocation refresh failed"
                          " - no connectivity")

    def get_result(self):
        """Get result from the provider

        :return: the result object or return None if no results are available
        :rtype: LocationResult or None
        """
        return self._provider.get_result()

    def get_territory_code(self):
        """A convenience function for getting the current territory code

        :return: territory code or None if no results are available
        :rtype: string or None
        """
        result = self._provider.get_result()
        if result:
            return result.territory_code
        else:
            return None

    def get_timezone(self):
        """A convenience function for getting the current time zone

        :return: time zone or None if no results are available
        :rtype: string or None
        """
        result = self._provider.get_result()
        if result:
            return result.timezone
        else:
            return None

    def get_public_ip_address(self):
        """A convenience function for getting current public IP

        :return: current public IP or None if no results are available
        :rtype: string or None
        """
        result = self._provider.get_result()
        if result:
            return result.public_ip_address
        else:
            return None


class LocationResult(object):
    def __init__(self, territory_code=None, timezone=None,
                 timezone_source="unknown", public_ip_address=None, city=None):
        """Encapsulates the result from GeoIP lookup.

        :param territory_code: the territory code from GeoIP lookup
        :type territory_code: string
        :param timezone: the time zone from GeoIP lookup
        :type timezone: string
        :param timezone_source: specifies source of the time zone string
        :type timezone_source: string
        :param public_ip_address: current public IP address
        :type public_ip_address: string
        :param city: current city
        :type city: string
        """
        self._territory_code = territory_code
        self._timezone = timezone
        self._timezone_source = timezone_source
        self._public_ip_address = public_ip_address
        self._city = city

    @property
    def territory_code(self):
        return self._territory_code

    @property
    def timezone(self):
        return self._timezone

    @property
    def public_ip_address(self):
        return self._public_ip_address

    @property
    def city(self):
        return self._city

    def __str__(self):
        if self.territory_code:
            result_string = "territory: %s" % self.territory_code
            if self.timezone:
                result_string += "\ntime zone: %s (from %s)" % (
                    self.timezone, self._timezone_source
                )
            if self.public_ip_address:
                result_string += "\npublic IP address: "
                result_string += "%s" % self.public_ip_address
            if self.city:
                result_string += "\ncity: %s" % self.city
            return result_string
        else:
            return "Position unknown"


class GeolocationBackend(object):
    """Base class for GeoIP backends."""
    def __init__(self):
        self._result = None
        self._result_lock = threading.Lock()

    def get_name(self):
        """Get name of the backend

        :return: name of the backend
        :rtype: string
        """
        pass

    def refresh(self, force=False):
        """Refresh the geolocation data

        :param force: do a refresh even if there is a result already available
        :type force: bool
        """
        # check if refresh is needed
        if force is True or self._result is None:
            log.info("Starting geolocation lookup")
            log.info("Geolocation provider: %s", self.get_name())
            global refresh_in_progress
            with refresh_condition:
                refresh_in_progress = True

            start_time = time.time()
            self._refresh()
            log.info("Geolocation lookup finished in %1.1f seconds",
                     time.time() - start_time)

            with refresh_condition:
                refresh_in_progress = False
                refresh_condition.notify_all()
            # check if there were any results
            result = self.get_result()
            if result:
                log.info("got results from geolocation")
                slog.info("geolocation result:\n%s", result)
            else:
                log.info("no results from geolocation")

    def _refresh(self):
        pass

    def _set_result(self, result):
        """Set current location

        :param result: geolocation lookup result
        :type result: LocationResult
        """
        # As the value is set from a thread but read from
        # the main thread, use a lock when accessing it
        with self._result_lock:
            self._result = result

    def get_result(self):
        """Get current location

        :return: geolocation lookup result
        :rtype: LocationResult
        """
        with self._result_lock:
            return self._result

    def __str__(self):
        return self.get_name()


class FedoraGeoIPProvider(GeolocationBackend):
    """The Fedora GeoIP service provider"""

    API_URL = "https://geoip.fedoraproject.org/city"

    def __init__(self):
        GeolocationBackend.__init__(self)

    def get_name(self):
        return "Fedora GeoIP"

    def _refresh(self):
        try:
            reply = urllib2.urlopen(self.API_URL, timeout=
                                    constants.NETWORK_CONNECTION_TIMEOUT)
            if reply:
                json_reply = json.load(reply)
                territory = json_reply.get("country_code", None)
                timezone_source = "GeoIP"
                timezone_code = json_reply.get("time_zone", None)

                if timezone_code is not None:
                    # the timezone code is returned as Unicode,
                    # it needs to be converted to UTF-8 encoded string,
                    # otherwise some string processing in Anaconda might fail
                    timezone_code = timezone_code.encode("utf8")

                # check if the timezone returned by the API is valid
                if not is_valid_timezone(timezone_code):
                    # try to get a timezone from the territory code
                    timezone_code = get_preferred_timezone(territory)
                    timezone_source = "territory code"
                if territory or timezone_code:
                    self._set_result(LocationResult(
                        territory_code=territory,
                        timezone=timezone_code,
                        timezone_source=timezone_source))
        except urllib2.HTTPError as e:
            log.debug("Geoloc: HTTPError for Fedora GeoIP API lookup:\n%s", e)
        except urllib2.URLError as e:
            log.debug("Geoloc: URLError for Fedora GeoIP API lookup:\n%s", e)


class HostipGeoIPProvider(GeolocationBackend):
    """The Hostip GeoIP service provider"""

    API_URL = "http://api.hostip.info/get_json.php"

    def __init__(self):
        GeolocationBackend.__init__(self)

    def get_name(self):
        return "Hostip.info"

    def _refresh(self):
        try:
            reply = urllib2.urlopen(self.API_URL, timeout=
                                    constants.NETWORK_CONNECTION_TIMEOUT)
            if reply:
                reply_dict = json.load(reply)
                territory = reply_dict.get("country_code", None)

                # unless at least country_code is available,
                # we don't return any results
                if territory is not None:
                    self._set_result(LocationResult(
                        territory_code=territory,
                        public_ip_address=reply_dict.get("ip", None),
                        city=reply_dict.get("city", None)
                    ))
        except urllib2.URLError as e:
            log.debug("Geoloc: URLError during Hostip lookup:\n%s", e)


class GoogleWiFiLocationProvider(GeolocationBackend):
    """The Google WiFi location service provider"""

    API_URL = "https://maps.googleapis.com/" \
              "maps/api/browserlocation/json?browser=firefox&sensor=true"

    def __init__(self):
        GeolocationBackend.__init__(self)

    def get_name(self):
        return "Google WiFi"

    def _refresh(self):
        log.info("Scanning for WiFi access points.")
        scanner = WifiScanner(scan_now=True)
        access_points = scanner.get_results()
        if access_points:
            try:
                url = self._get_url(access_points)
                reply = urllib2.urlopen(url, timeout=
                                        constants.NETWORK_CONNECTION_TIMEOUT)
                result_dict = json.load(reply)
                status = result_dict.get('status', 'NOT OK')
                if status == 'OK':
                    lat = result_dict['location']['lat']
                    lon = result_dict['location']['lng']
                    log.info("Found current location.")
                    coords = Coordinates(lat=lat, lon=lon)
                    geocoder = Geocoder()
                    geocoding_result = geocoder.reverse_geocode_coords(coords)
                    # for compatibility, return GeoIP result instead
                    # of GeocodingResult
                    t_code = geocoding_result.territory_code
                    self._set_result(LocationResult(territory_code=t_code))
                else:
                    log.info("Service couldn't find current location.")
            except urllib2.URLError as e:
                log.debug("Geoloc: URLError during Google"
                          "  Wifi lookup:\n%s", e)
        else:
            log.info("No WiFi access points found - can't detect location.")

    def _get_url(self, access_points):
        """Generate Google API URL for the given access points

        :param access_points: a list of WiFiAccessPoint objects
        :return Google WiFi location API URL
        :rtype: string
        """
        url = self.API_URL
        for ap in access_points:
            url += self._describe_access_point(ap)
        return url

    def _describe_access_point(self, access_point):
        """Describe an access point in a format compatible with the API call

        :param access_point: a WiFiAccessPoint instance
        :return: API compatible AP description
        :rtype: string
        """
        quoted_ssid = urllib.quote_plus(access_point.ssid)
        return "&wifi=mac:%s|ssid:%s|ss:%d" % (access_point.bssid,
                                               quoted_ssid, access_point.rssi)


class Geocoder(object):
    """Provides online geocoding services
    (only reverse geocoding at the moment).
    """

    # MapQuest Nominatim instance without (?) rate limiting
    NOMINATIM_API_URL = "http://open.mapquestapi.com/" \
                        "nominatim/v1/reverse.php?format=json"
    # Alternative OSM hosted Nominatim instance (with rate limiting):
    # http://nominatim.openstreetmap.org/reverse?format=json

    def __init__(self, geocoder=constants.GEOLOC_DEFAULT_GEOCODER):
        """:param geocoder: a constant selecting what geocoder to use"""
        self._geocoder = geocoder

    def reverse_geocode_coords(self, coordinates):
        """Turn geographic coordinates to address

        :param coordinates: Coordinates (geographic coordinates)
        :type coordinates: Coordinates
        :return: GeocodingResult if the lookup succeeds or None if it fails
        """
        if self._geocoder == constants.GEOLOC_GEOCODER_NOMINATIM:
            return self._reverse_geocode_nominatim(coordinates)
        else:
            log.error("Wrong Geocoder specified!")
            return None  # unknown geocoder specified

    def _reverse_geocode_nominatim(self, coordinates):
        """Reverse geocoding using the Nominatim API
        Reverse geocoding tries to convert geographic coordinates
        to an accurate address.

        :param coordinates: input coordinates
        :type coordinates: Coordinates
        :return: an address or None if no address was found
        :rtype: GeocodingResult or None
        """
        url = "%s&addressdetails=1&lat=%f&lon=%f" % (
            self.NOMINATIM_API_URL,
            coordinates.latitude,
            coordinates.longitude)
        try:
            reply = urllib2.urlopen(url, timeout=
                                    constants.NETWORK_CONNECTION_TIMEOUT)
            if reply:
                reply_dict = json.load(reply)
                territory_code = reply_dict['address']['country_code'].upper()
                return GeocodingResult(coordinates=coordinates,
                                       territory_code=territory_code)
            else:
                return None
        except urllib2.URLError as e:
            log.debug("Geoloc: URLError during Nominatim reverse geocoding"
                      " :\n%s", e)


class GeocodingResult(object):
    """A result from geocoding lookup"""

    def __init__(self, coordinates=None, territory_code=None, address=None):
        """
        :param coordinates: geographic coordinates
        :type coordinates: Coordinates
        :param territory_code: territory code of the result
        :type territory_code: string
        :param address: a (street) address string
        :type address: string
        """
        self._coords = coordinates
        self._territory_code = territory_code
        self._address = address

    @property
    def coordinates(self):
        return self._coords

    @property
    def territory_code(self):
        return self._territory_code

    @property
    def address(self):
        return self._address


class Coordinates(object):
    """A set of geographic coordinates."""

    def __init__(self, lat=None, lon=None):
        """
        :param lat: WGS84 latitude
        :type lat: float
        :param lon: WGS84 longitude
        :type lon: float
        """
        self._lat = lat
        self._lon = lon

    @property
    def latitude(self):
        return self._lat

    @property
    def longitude(self):
        return self._lon

    def __str__(self):
        return "lat,lon: %f,%f" % (self.latitude, self.longitude)


class WifiScanner(object):
    """Uses the Network Manager DBUS API to provide information
    about nearby WiFi access points
    """

    NETWORK_MANAGER_DEVICE_TYPE_WIFI = 2

    def __init__(self, scan_now=True):
        """
        :param scan_now: if an initial scan should be done
        :type scan_now: bool
        """
        self._scan_results = []
        if scan_now:
            self.scan()

    def scan(self):
        """Scan for WiFi access points"""
        devices = ""
        access_points = []
        # connect to network manager
        try:
            bus = dbus.SystemBus()
            network_manager = bus.get_object('org.freedesktop.NetworkManager',
                                             '/org/freedesktop/NetworkManager')
            devices = network_manager.GetDevices()
        except dbus.DBusException as e:
            log.debug("Exception caught during WiFi AP scan: %s", e)

        # iterate over all devices
        for device_path in devices:
            device = bus.get_object('org.freedesktop.NetworkManager',
                                    device_path)
            # get type of the device
            device_type = device.Get("org.freedesktop.NetworkManager.Device",
                                     'DeviceType')
            # iterate over all APs
            if device_type == self.NETWORK_MANAGER_DEVICE_TYPE_WIFI:

                dbus_iface_id = 'org.freedesktop.DBus.Properties'
                ap_id = "org.freedesktop.NetworkManager.AccessPoint"

                for ap_path in device.GetAccessPoints():
                    # drill down to the DBUS object for the AP
                    net = bus.get_object('org.freedesktop.NetworkManager', ap_path)
                    network_properties = dbus.Interface(
                        net, dbus_interface=dbus_iface_id)

                    # get the MAC, name & signal strength
                    bssid = str(network_properties.Get(ap_id, "HwAddress"))
                    essid = str(network_properties.Get(
                        ap_id, "Ssid", byte_arrays=True))
                    rssi = int(network_properties.Get(ap_id, "Strength"))

                    # create a new AP object and add it to the
                    # list of discovered APs
                    ap = WiFiAccessPoint(bssid=bssid, ssid=essid, rssi=rssi)
                    access_points.append(ap)
        self._scan_results = access_points

    def get_results(self):
        """
        :return: a list of WiFiAccessPoint objects or
        an empty list if no APs were found or the scan failed
        """
        return self._scan_results


class WiFiAccessPoint(object):
    """Encapsulates information about WiFi access point"""

    def __init__(self, bssid, ssid=None, rssi=None):
        """
        :param bssid: MAC address of the access point
        :param ssid: name of the access point
        :param rssi: signal strength
        """
        self._bssid = bssid
        self._ssid = ssid
        self._rssi = rssi

    @property
    def bssid(self):
        return self._bssid

    @property
    def ssid(self):
        return self._ssid

    @property
    def rssi(self):
        return self._rssi

    def __str__(self):
        return "bssid (MAC): %s ssid: %s rssi " \
               "(signal strength): %d" % (self.bssid, self.ssid, self.rssi)

if __name__ == "__main__":
    print "GeoIP directly started"

    print "trying the default backend"
    location_info = LocationInfo()
    location_info.refresh()
    print "  provider used: %s" % location_info._provider
    print "  territory code: %s" % location_info.get_territory_code()

    print "trying the Fedora GeoIP backend"
    location_info = LocationInfo(provider_id=
                                 constants.GEOLOC_PROVIDER_FEDORA_GEOIP)
    location_info.refresh()
    print "  provider used: %s" % location_info._provider
    print "  territory code: %s" % location_info.get_territory_code()

    print "trying the Google WiFi location backend"
    location_info = LocationInfo(provider_id=
                                 constants.GEOLOC_PROVIDER_GOOGLE_WIFI)
    location_info.refresh()
    print "  provider used: %s" % location_info._provider
    print "  territory code: %s" % location_info.get_territory_code()

    print "trying the Hostip backend"
    location_info = LocationInfo(provider_id=constants.GEOLOC_PROVIDER_HOSTIP)
    location_info.refresh()
    print "  provider used: %s" % location_info._provider
    print "  territory code: %s" % location_info.get_territory_code()
