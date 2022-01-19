/*
 * Copyright (C) 2022 Red Hat, Inc.
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

export class LocalizationClient {
    constructor (address) {
        if (LocalizationClient.instance) {
            return LocalizationClient.instance;
        }
        LocalizationClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Modules.Localization",
            { superuser: "try", bus: "none", address }
        );
    }

    init () {
        this.client.addEventListener("close", () => console.error("Localization client closed"));
    }
}

/**
 * @returns {Promise}           Resolves a list of language ids
 */
export const getLanguages = () => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "GetLanguages", []
        )
                .then(res => res[0], console.info)
    );
};

/**
 * @returns {Promise}           The language the system will use
 */
export const getLanguage = () => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.freedesktop.DBus.Properties",
            "Get",
            ["org.fedoraproject.Anaconda.Modules.Localization", "Language"]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {string} lang         Language id
 *
 * @returns {Promise}           Resolves a language data object
 */
export const getLanguageData = ({ lang }) => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "GetLanguageData", [lang]
        )
                .then(res => res[0])
    );
};

/**
 * @param {string} lang         Language id
 *
 * @returns {Promise}           Resolves a list of locales ids
 */
export const getLocales = ({ lang }) => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "GetLocales", [lang]
        )
                .then(res => res[0])
    );
};

/**
 * @param {string} lang         Locale id
 *
 * @returns {Promise}           Resolves a locale data object
 */
export const getLocaleData = ({ locale }) => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.fedoraproject.Anaconda.Modules.Localization",
            "GetLocaleData", [locale]
        )
                .then(res => res[0])
    );
};

/**
 * @param {string} lang         Language id
 */
export const setLanguage = ({ lang }) => {
    return (
        new LocalizationClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Localization",
            "org.freedesktop.DBus.Properties",
            "Set",
            [
                "org.fedoraproject.Anaconda.Modules.Localization",
                "Language",
                cockpit.variant("s", lang)
            ]
        )
    );
};
