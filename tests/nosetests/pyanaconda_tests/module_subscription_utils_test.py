#
# Copyright (C) 2022  Red Hat, Inc.
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

import json
import unittest

from pyanaconda.modules.subscription.utils import detect_sca_from_registration_data


class DetectSCATestCase(unittest.TestCase):

    def test_registration_data_json_parsing(self):
        """Test the detect_sca_from_registration_data() method."""
        parse_method = detect_sca_from_registration_data
        # the parsing method should be able to survive also getting an empty string
        # or even None, returning False
        self.assertFalse(parse_method(""))
        self.assertFalse(parse_method(None))

        # registration data without owner key
        no_owner_data = {
            "foo": "123",
            "bar": "456",
            "baz": "789"
        }
        self.assertFalse(parse_method(json.dumps(no_owner_data)))

        # registration data with owner key but without the necessary
        # contentAccessMode key
        no_access_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner"
            },
            "bar": "456",
            "baz": "789"
        }
        self.assertFalse(parse_method(json.dumps(no_access_mode_data)))

        # registration data with owner key but without the necessary
        # contentAccessMode key
        no_access_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner"
            },
            "bar": "456",
            "baz": "789"
        }
        self.assertFalse(parse_method(json.dumps(no_access_mode_data)))

        # registration data for SCA mode
        sca_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "org_environment"
            },
            "bar": "456",
            "baz": "789"
        }
        self.assertTrue(parse_method(json.dumps(sca_mode_data)))

        # registration data for entitlement mode
        entitlement_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "entitlement"
            },
            "bar": "456",
            "baz": "789"
        }
        self.assertFalse(parse_method(json.dumps(entitlement_mode_data)))

        # registration data for unknown mode
        unknown_mode_data = {
            "foo": "123",
            "owner": {
                "id": "abc",
                "key": "admin",
                "displayName": "Admin Owner",
                "contentAccessMode": "something_else"
            },
            "bar": "456",
            "baz": "789"
        }
        self.assertFalse(parse_method(json.dumps(unknown_mode_data)))
