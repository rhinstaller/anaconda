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

import { StorageClient } from "./storage.js";
import { _callClient, _setProperty, _getProperty } from "./helpers.js";

const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection";
const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection";

const callClient = (...args) => {
    return _callClient(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const setProperty = (...args) => {
    return _setProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const getProperty = (...args) => {
    return _getProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
/**
 * @returns {Promise}           Resolves all properties of DiskSelection interface
 */
export const getAllDiskSelection = () => {
    return new StorageClient().client.call(OBJECT_PATH, "org.freedesktop.DBus.Properties", "GetAll", [INTERFACE_NAME]);
};

/**
 * @returns {Promise}           Resolves a list with disk names
 */
export const getUsableDisks = () => {
    return callClient("GetUsableDisks", []);
};

/**
 * @returns {Promise}           The list of selected disks
 */
export const getSelectedDisks = () => {
    return getProperty("SelectedDisks");
};

/**
 * @param {Array.<string>} drives A list of drives names
 */
export const setSelectedDisks = ({ drives }) => {
    return setProperty("SelectedDisks", cockpit.variant("as", drives));
};
