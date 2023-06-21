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

import { useReducer, useCallback } from "react";

export const useReducerWithThunk = (reducer, initialState) => {
    const [state, dispatch] = useReducer(reducer, initialState);

    function customDispatch (action) {
        if (typeof action === "function") {
            return action(customDispatch);
        } else {
            dispatch(action);
        }
    }

    // Memoize so you can include it in the dependency array without causing infinite loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const stableDispatch = useCallback(customDispatch, [dispatch]);

    return [state, stableDispatch];
};

export const reducer = (state, action) => {
    if (action.type === "GET_DEVICE_DATA") {
        return { ...state, devices: { ...action.payload.deviceData, ...state.devices } };
    } else if (action.type === "GET_DISK_SELECTION") {
        return { ...state, diskSelection: action.payload.diskSelection };
    }

    if (action.type === "GET_LANGUAGE_DATA") {
        return { ...state, languages: { ...action.payload.languageData, ...state.languages } };
    }

    if (action.type === "GET_COMMON_LOCALES") {
        return { ...state, commonLocales: action.payload.commonLocales };
    }
};

export const initialState = {
    devices: {},
    diskSelection: {
        usableDisks: [],
        selectedDisks: [],
        ignoredDisks: []
    },

    languages: {},
    commonLocales: []
};
