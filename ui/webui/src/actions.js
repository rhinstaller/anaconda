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

import {
    getAllDiskSelection,
    getDeviceData,
    getDevices,
    getDiskFreeSpace,
    getDiskTotalSpace,
    getFormatData,
    getUsableDisks,
} from "./apis/storage.js";
import {
    getCommonLocales,
    getLanguages,
    getLanguageData,
    getLocales,
    getLocaleData,
} from "./apis/localization.js";

export const getDevicesAction = () => {
    return async function fetchUserThunk (dispatch) {
        const devices = await getDevices();
        return devices[0].map(device => dispatch(getDeviceDataAction({ device })));
    };
};

export const getDeviceDataAction = ({ device }) => {
    return async function fetchUserThunk (dispatch) {
        let devData = {};
        const deviceData = await getDeviceData({ disk: device })
                .then(res => {
                    devData = res[0];
                    return getDiskFreeSpace({ diskNames: [device] });
                })
                .then(free => {
                    // Since the getDeviceData returns an object with variants as values,
                    // extend it with variants to keep the format consistent
                    devData.free = cockpit.variant(String, free[0]);
                    return getDiskTotalSpace({ diskNames: [device] });
                })
                .then(total => {
                    devData.total = cockpit.variant(String, total[0]);
                    return getFormatData({ diskName: device });
                })
                .then(formatData => {
                    devData.formatData = formatData[0];
                    return ({ [device]: devData });
                })
                .catch(console.error);

        return dispatch({
            type: "GET_DEVICE_DATA",
            payload: { deviceData }
        });
    };
};

export const getDiskSelectionAction = () => {
    return async function fetchUserThunk (dispatch) {
        const usableDisks = await getUsableDisks();
        const diskSelection = await getAllDiskSelection();

        return dispatch({
            type: "GET_DISK_SELECTION",
            payload: {
                diskSelection: {
                    ignoredDisks: diskSelection[0].IgnoredDisks.v,
                    selectedDisks: diskSelection[0].SelectedDisks.v,
                    usableDisks: usableDisks[0],
                }
            },
        });
    };
};

export const getLanguagesAction = () => {
    return async function fetchUserThunk (dispatch) {
        const languageIds = await getLanguages();

        dispatch(getCommonLocalesAction());
        return languageIds.map(language => dispatch(getLanguageDataAction({ language })));
    };
};

export const getLanguageDataAction = ({ language }) => {
    return async function fetchUserThunk (dispatch) {
        const localeIds = await getLocales({ lang: language });
        const languageData = await getLanguageData({ lang: language });
        const locales = await Promise.all(localeIds.map(async locale => await getLocaleData({ locale })));

        return dispatch({
            type: "GET_LANGUAGE_DATA",
            payload: { languageData: { [language]: { languageData, locales } } }
        });
    };
};

export const getCommonLocalesAction = () => {
    return async function fetchUserThunk (dispatch) {
        const commonLocales = await getCommonLocales();

        return dispatch({
            type: "GET_COMMON_LOCALES",
            payload: { commonLocales }
        });
    };
};
