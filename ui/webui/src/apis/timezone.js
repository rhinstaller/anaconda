/*
 * Copyright (C) 2023 Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with This program; If not, see <http://www.gnu.org/licenses/>.
 */

import cockpit from "cockpit";

export class TimezoneClient {
    constructor (address) {
        if (TimezoneClient.instance) {
            return TimezoneClient.instance;
        }
        TimezoneClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Modules.Timezone",
            { superuser: "try", bus: "none", address }
        );
    }

    init () {
        this.client.addEventListener("close", () => console.error("Timezone client closed"));
    }
}

/**
 * @returns {Promise}           The current system Timezone
 */
export const getTimezone = () => {
    return (
        new TimezoneClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Timezone",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Timezone",
                "Timezone"
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {string} timezone         Timezone id
 */
export const setTimezone = ({ timezone }) => {
    return new TimezoneClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Timezone",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Timezone",
            "Timezone",
            cockpit.variant("s", timezone)
        ]
    );
};

/**
 * @returns {Promise}           Resolves a list of timezones
 */
export const getTimezones = () => {
    return new TimezoneClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Timezone",
        "org.fedoraproject.Anaconda.Modules.Timezone",
        "GetTimezones", []
    );
};

/**
 * @returns {Promise}           NTP enabled
 */
export const getNtpEnabled = () => {
    return (
        new TimezoneClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Timezone",
            "org.freedesktop.DBus.Properties",
            "Get",
            ["org.fedoraproject.Anaconda.Modules.Timezone", "NTPEnabled"]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {bool} enabled - enable/disable NTP
 *
 * @returns {Promise}           FIXME: what does it return in this case ??
 */

export const setNtpEnabled = ({ enabled }) => {
    return (
        new TimezoneClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Timezone",
            "org.freedesktop.DBus.Properties",
            "Set",
            [
                "org.fedoraproject.Anaconda.Modules.Timezone",
                "NTPEnabled",
                cockpit.variant("b", enabled)
            ]
        )
    );
};

/**
 * @returns {Promise}           Resolves the DBus path to the partitioning
 */
export const getSystemDateTime = () => {
    return new TimezoneClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Timezone",
        "org.fedoraproject.Anaconda.Modules.Timezone",
        "GetSystemDateTime", []
    );
};

/**
 * @param {string} datetimespec date time specification in ISO 8601 format
 *
 * @returns {Promise}           FIXME: what does it ret
 */
export const setSystemDateTime = ({ datetimespec }) => {
    return new TimezoneClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Timezone",
        "org.fedoraproject.Anaconda.Modules.Timezone",
        "SetSystemDateTime", [datetimespec]
    );
};
