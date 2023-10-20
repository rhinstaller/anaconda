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

/* Initial state for the storeage store substate */
export const storageInitialState = {
    devices: {},
    diskSelection: {
        usableDisks: [],
        selectedDisks: [],
        ignoredDisks: []
    },
    partitioning: {}
};

/* Initial state for the localization store substate */
export const localizationInitialState = {
    language: "",
    languages: {},
    commonLocales: []
};

/* Intial state for the network store substate */
export const networkInitialState = {
    connected: null
};

/* Initial state for the error store substate */
export const errorInitialState = {
    criticalError: null
};

/* Intial state for the runtime store substate */
export const runtimeInitialState = {
    connected: null
};

/* Initial state for the global store */
export const initialState = {
    localization: localizationInitialState,
    storage: storageInitialState,
    network: networkInitialState,
    error: errorInitialState,
    runtime: runtimeInitialState,
};

/* Custom hook to use the reducer with async actions */
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
    return ({
        localization: localizationReducer(state.localization, action),
        storage: storageReducer(state.storage, action),
        network: networkReducer(state.network, action),
        error: errorReducer(state.error, action),
        runtime: runtimeReducer(state.runtime, action),
    });
};

export const storageReducer = (state = storageInitialState, action) => {
    if (action.type === "GET_DEVICES_DATA") {
        return { ...state, devices: action.payload.devices };
    } else if (action.type === "GET_DISK_SELECTION") {
        return { ...state, diskSelection: action.payload.diskSelection };
    } else if (action.type === "GET_PARTITIONING_DATA") {
        return { ...state, partitioning: { ...state.partitioning, ...action.payload.partitioningData } };
    } else {
        return state;
    }
};

export const localizationReducer = (state = localizationInitialState, action) => {
    if (action.type === "GET_LANGUAGE_DATA") {
        return { ...state, languages: { ...state.languages, ...action.payload.languageData } };
    } else if (action.type === "GET_COMMON_LOCALES") {
        return { ...state, commonLocales: action.payload.commonLocales };
    } else if (action.type === "GET_LANGUAGE") {
        return { ...state, language: action.payload.language };
    } else {
        return state;
    }
};

export const networkReducer = (state = networkInitialState, action) => {
    if (action.type === "GET_NETWORK_CONNECTED") {
        return { ...state, connected: action.payload.connected };
    } else {
        return state;
    }
};

const errorReducer = (state = errorInitialState, action) => {
    if (action.type === "SET_CRITICAL_ERROR") {
        return { ...state, criticalError: action.payload.criticalError };
    } else {
        return state;
    }
};

export const runtimeReducer = (state = runtimeInitialState, action) => {
    if (action.type === "GET_RUNTIME_PASSWORD_POLICIES") {
        return { ...state, passwordPolicies: action.payload.passwordPolicies };
    } else {
        return state;
    }
};
