#
# Constants for the Flatpak
#
# Copyright (C) 2025 Red Hat, Inc.
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

FLATPAK_SCHEMA_V2 = 2
FLATPAK_IMAGE_LAYOUT_VERSION = "1.0.0"
FLATPAK_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"

FLATPAK_REGISTRY_URL_PATTERN = "{}/index/static?label:org.flatpak.ref:exists=1&architecture={}&tag={}"
