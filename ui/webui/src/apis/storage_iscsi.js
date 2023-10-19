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
import { StorageClient, runStorageTask } from "./storage.js";
import { objectToDBus } from "../helpers/utils.js";
import { _callClient, _getProperty, _setProperty } from "./helpers.js";

const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Storage.iSCSI";
const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage/iSCSI";

const callClient = (...args) => {
    return _callClient(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const getProperty = (...args) => {
    return _getProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const setProperty = (...args) => {
    return _setProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

/**
 * @returns {Promise}               Module supported
 */
export const getIsSupported = () => {
    return callClient("IsSupported", []);
};

/**
 * @returns {Promise}               Can set initiator
 */
export const getCanSetInitiator = () => {
    return callClient("CanSetInitiator", []);
};

/**
 * @returns {Promise}               iSCSI initiator name
 */
export const getInitiator = () => {
    return getProperty("Initiator");
};

/**
 * @param {string} initiator        iSCSI initiator name
 */
export const setInitiator = ({ initiator }) => {
    return setProperty("Initiator", cockpit.variant("s", initiator));
};

/**
 * @param {object} portal           The portal information
 * @param {object} credentials      The iSCSI credentials
 * @param {object} interfacesMode
 */
export const runDiscover = async ({ portal, credentials, interfacesMode = "default", onSuccess, onFail }) => {
    const args = [
        { ...objectToDBus(portal) },
        { ...objectToDBus(credentials) },
        interfacesMode,
    ];
    try {
        const discoverWithTask = () => callClient("DiscoverWithTask", args);
        const task = await discoverWithTask();

        return runStorageTask({ task, onFail, onSuccess, getResult: true });
    } catch (error) {
        onFail(error);
    }
};

/**
 * @param {object} portal           The portal information
 * @param {object} credentials      The iSCSI credentials
 * @param {object} node             The iSCSI node
 */
export const runLogin = async ({ portal, credentials, node, onSuccess, onFail }) => {
    const args = [
        { ...objectToDBus(portal) },
        { ...objectToDBus(credentials) },
        { ...objectToDBus(node) },
    ];
    try {
        const loginWithTask = () => callClient("LoginWithTask", args);
        const task = await loginWithTask();

        return runStorageTask({ task, onFail, onSuccess });
    } catch (error) {
        onFail(error);
    }
};
