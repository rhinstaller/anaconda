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

import { getLanguageAction, getLanguagesAction } from "../actions/localization-actions.js";
import { debug } from "../helpers/log.js";
import { _callClient, _setProperty, _getProperty } from "./helpers.js";

const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Localization";
const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Localization";

const callClient = (...args) => {
    return _callClient(LocalizationClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const setProperty = (...args) => {
    return _setProperty(LocalizationClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const getProperty = (...args) => {
    return _getProperty(LocalizationClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class LocalizationClient {
    constructor (address) {
        if (LocalizationClient.instance && (!address || LocalizationClient.instance.address === address)) {
            return LocalizationClient.instance;
        }

        LocalizationClient.instance?.client.close();

        LocalizationClient.instance = this;

        this.client = cockpit.dbus(
            INTERFACE_NAME,
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener("close", () => console.error("Localization client closed"));
    }
}

/**
 * @returns {Promise}           Resolves a list of language ids
 */
export const getLanguages = () => {
    return callClient("GetLanguages", []);
};

/**
 * @returns {Promise}           The language the system will use
 */
export const getLanguage = () => {
    return getProperty("Language");
};

/**
 * @param {string} lang         Language id
 *
 * @returns {Promise}           Resolves a language data object
 */
export const getLanguageData = ({ lang }) => {
    return callClient("GetLanguageData", [lang]);
};

/**
 * @param {string} lang         Language id
 *
 * @returns {Promise}           Resolves a list of locales ids
 */
export const getLocales = ({ lang }) => {
    return callClient("GetLocales", [lang]);
};

/**
 * @returns {Promise}           Resolves a list of common locales id's.
 */
export const getCommonLocales = () => {
    return callClient("GetCommonLocales");
};

/**
 * @param {string} lang         Locale id
 *
 * @returns {Promise}           Resolves a locale data object
 */
export const getLocaleData = ({ locale }) => {
    return callClient("GetLocaleData", [locale]);
};

/**
 * @param {string} lang         Language id
 */
export const setLanguage = ({ lang }) => {
    return setProperty("Language", cockpit.variant("s", lang));
};

export const startEventMonitorLocalization = ({ dispatch }) => {
    return new LocalizationClient().client.subscribe(
        { },
        (path, iface, signal, args) => {
            switch (signal) {
            case "PropertiesChanged":
                if (args[0] === INTERFACE_NAME && Object.hasOwn(args[1], "Language")) {
                    dispatch(getLanguageAction());
                } else {
                    debug(`Unhandled signal on ${path}: ${iface}.${signal}`, JSON.stringify(args));
                }
                break;
            default:
                debug(`Unhandled signal on ${path}: ${iface}.${signal}`, JSON.stringify(args));
            }
        });
};

export const initDataLocalization = ({ dispatch }) => {
    return Promise.all([
        dispatch(getLanguageAction()),
        dispatch(getLanguagesAction())
    ]);
};
