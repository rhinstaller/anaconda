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

import {
    getCommonLocales,
    getLanguage,
    getLanguages,
    getLanguageData,
    getLocales,
    getLocaleData,
} from "../apis/localization.js";

export const getLanguagesAction = () => {
    return async function fetchUserThunk (dispatch) {
        const languageIds = await getLanguages();

        return Promise.all([
            dispatch(getCommonLocalesAction()),
            ...languageIds.map(language => dispatch(getLanguageDataAction({ language })))
        ]);
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

export const getLanguageAction = () => {
    return async function fetchUserThunk (dispatch) {
        const language = await getLanguage();

        return dispatch({
            type: "GET_LANGUAGE",
            payload: { language }
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
