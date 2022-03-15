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

const storageClient = address => {
    return cockpit.dbus(
        "org.fedoraproject.Anaconda.Modules.Storage",
        { superuser: "try", bus: "none", address }
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {string} partitioning DBus path to a partitioning
 *
 * @returns {Promise}           Resolves the DBus path to the partitioning
 */
export const applyPartitioning = ({ address, partitioning }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "ApplyPartitioning", [partitioning]
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {string} method       A partitioning method
 *
 * @returns {Promise}           Resolves the DBus path to the partitioning
 */
export const createPartitioning = ({ address, method }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "CreatePartitioning", [method]
    );
};

/**
 * @param {string} address      Anaconda bus address
 *
 * @returns {Promise}           Resolves all properties of DiskSelection interface
 */
export const getAllDiskSelection = ({ address }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.freedesktop.DBus.Properties",
        "GetAll",
        ["org.fedoraproject.Anaconda.Modules.Storage.DiskSelection"],
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {string} disk         A device name
 *
 * @returns {Promise}           Resolves an object with the device data
 */
export const getDeviceData = ({ address, disk }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetDeviceData", [disk]
    );
};

/**
 * @param {string} address      Anaconda bus address
 *
 * @returns {Promise}           Resolves a list with disk names
 */
export const getUsableDisks = ({ address }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
        "GetUsableDisks", []
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {string} partitioning DBus path to a partitioning
 *
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const partitioningConfigureWithTask = ({ address, partitioning }) => {
    return storageClient(address).call(
        partitioning,
        "org.fedoraproject.Anaconda.Modules.Storage.Partitioning",
        "ConfigureWithTask", []
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {string} task         DBus path to a task
 * @param {string} onSuccess    Callback to run after Succeeded signal is received
 * @param {string} onFail       Callback to run as an error handler
 *
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const runStorageTask = ({ address, task, onSuccess, onFail }) => {
    const taskProxy = storageClient(address).proxy(
        "org.fedoraproject.Anaconda.Task",
        task
    );
    const addEventListeners = () => {
        taskProxy.addEventListener("Stopped", () => taskProxy.Finish().catch(onFail));
        taskProxy.addEventListener("Succeeded", onSuccess);
    };
    taskProxy.wait(() => {
        addEventListeners();
        taskProxy.Start().catch(onFail);
    });
};

/**
 * @param {string} address      Anaconda bus address
 * @param {int} mode            The number of the mode
 */
export const setInitializationMode = ({ address, mode }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization",
        "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization",
        "SetInitializationMode", [mode]
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {boolean} enabled     True if allowed, otherwise False
 */
export const setInitializeLabelsEnabled = ({ address, enabled }) => {
    return (
        storageClient(address).call(
            "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization",
            "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization",
            "SetInitializeLabelsEnabled", [enabled]
        )
    );
};

/**
 * @param {string} address      Anaconda bus address
 * @param {Array.<string>} drives A list of drives names
 */
export const setSelectedDisks = ({ address, drives }) => {
    return storageClient(address).call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
        "SetSelectedDisks", [drives]
    );
};
