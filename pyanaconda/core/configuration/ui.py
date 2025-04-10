#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from pyanaconda.core.configuration.base import Section
from pyanaconda.core.configuration.utils import split_name_and_attributes


class UserInterfaceSection(Section):
    """The User Interface section."""

    @property
    def custom_stylesheet(self):
        """The path to a custom stylesheet."""
        return self._get_option("custom_stylesheet", str)

    @property
    def hidden_spokes(self):
        """A list of spokes to hide in UI.

        :return: a list of strings
        """
        return self._get_option("hidden_spokes", str).split()

    @property
    def can_change_root(self):
        """Should the UI allow to change the configured root account?

        If the root account is already set up by a kickstart file or
        via the DBus API, should we allow to change it via the user
        interface?

        :return: True or False
        """
        return self._get_option("can_change_root", bool)

    @property
    def can_change_users(self):
        """Should the UI allow to change the configured user accounts?

        If the user accounts are already set up by a kickstart file or
        via the DBus API, should we allow to change them via the user
        interface?

        :return: True or False
        """
        return self._get_option("can_change_users", bool)

    @property
    def password_policies(self):
        """The password policies.

        Returns a list of dictionaries with password policy attributes.
        The name of the policy is represented by the attribute 'name'
        in the dictionary representation.

        Valid attributes:

            name        The name of the policy.
            quality     The minimum quality score (see libpwquality).
            length      The minimum length of the password.
            empty       Allow an empty password.
            strict      Require the minimum quality.

        :return: a list of dictionaries with policy attributes
        """
        return self._get_option("password_policies", self._convert_policies)

    def _convert_policies(self, value):
        """Convert a policies string into a list of dictionaries."""
        return list(map(self._convert_policy_line, value.strip().split("\n")))

    @classmethod
    def _convert_policy_line(cls, line):
        """Convert a policy line into a dictionary."""
        # Parse the line.
        name, raw_attrs = split_name_and_attributes(line)

        # Generate the dictionary.
        attrs = {"name": name}

        for name, value in raw_attrs.items():
            if not value and name in ("strict", "empty"):
                # Handle a boolean attribute.
                attrs[name] = True
            elif value and name in ("length", "quality"):
                # Handle an integer attribute.
                attrs[name] = int(value)
            else:
                # Handle an invalid attribute.
                raise ValueError("Invalid attribute: " + name)

        # Validate the dictionary.
        cls._validate_policy_attributes(attrs)

        return attrs

    @staticmethod
    def _validate_policy_attributes(attrs):
        """Validate the dictionary with policy attributes."""
        if not attrs.get("name"):
            raise ValueError("The name of the policy is not specified.")

        if "length" not in attrs:
            raise ValueError("The minimal length is not specified.")

        if "quality" not in attrs:
            raise ValueError("The minimal quality is not specified.")

    @property
    def show_kernel_options(self):
        return self._get_option("show_kernel_options", bool)
