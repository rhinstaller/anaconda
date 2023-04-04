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

export class StorageClient {
    constructor (address) {
        if (StorageClient.instance) {
            return StorageClient.instance;
        }
        StorageClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Modules.Storage",
            { superuser: "try", bus: "none", address }
        );
    }

    init () {
        this.client.addEventListener("close", () => console.error("Storage client closed"));
    }
}

/**
 * @param {string} partitioning DBus path to a partitioning
 *
 * @returns {Promise}           Resolves the DBus path to the partitioning
 */
export const applyPartitioning = ({ partitioning }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "ApplyPartitioning", [partitioning]
    );
};

/**
 * @param {string} method       A partitioning method
 *
 * @returns {Promise}           Resolves the DBus path to the partitioning
 */
export const createPartitioning = ({ method }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "CreatePartitioning", [method]
    );
};

/**
 * @returns {Promise}           Resolves all properties of DiskSelection interface
 */
export const getAllDiskSelection = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.freedesktop.DBus.Properties",
        "GetAll",
        ["org.fedoraproject.Anaconda.Modules.Storage.DiskSelection"],
    );
};

/**
 * @param {string} disk         A device name
 *
 * @returns {Promise}           Resolves an object with the device data
 */
export const getDeviceData = ({ disk }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetDeviceData", [disk]
    );
};

/**
 * @param {Array[string]} diskNames A list of disk names
 *
 * @returns {Promise}           Resolves the total free space on the given disks
 */
export const getDiskFreeSpace = ({ diskNames }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetDiskFreeSpace", [diskNames]
    );
};

/**
 * @param {int} requiredSpace A required space in bytes
 *
 * @returns {Promise}           Resolves the total free space on the given disks
 */
export const getRequiredDeviceSize = ({ requiredSpace }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetRequiredDeviceSize", [requiredSpace]
    )
            .then(res => res[0]);
};

/**
 * @param {Array[string]} diskNames A list of disk names
 *
 * @returns {Promise}           Resolves the total space on the given disks
 */
export const getDiskTotalSpace = ({ diskNames }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetDiskTotalSpace", [diskNames]
    );
};

/**
 * @returns {Promise}           Resolves a list with disk names
 */
export const getUsableDisks = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
        "GetUsableDisks", []
    );
};

/**
 * @returns {Promise}           The list of selected disks
 */
export const getSelectedDisks = () => {
    return (
        new StorageClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
                "SelectedDisks"
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {string} partitioning    DBus path to a partitioning
 * @param {string} passphrase      passphrase for disk encryption
 */
export const partitioningSetPassphrase = ({ partitioning, passphrase }) => {
    return new StorageClient().client.call(
        partitioning,
        "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Automatic",
        "SetPassphrase", [passphrase]
    );
};

/**
 * @param {string} partitioning     DBus path to a partitioning
 * @param {boolean} encrypt         True if partitions should be encrypted, False otherwise
 */
export const partitioningSetEncrypt = ({ partitioning, encrypt }) => {
    return getPartitioningRequest({ partitioning })
            .then(request => {
                request.encrypted = cockpit.variant("b", encrypt);
                return setPartitioningRequest({ partitioning, request });
            });
};

/**
 * @returns {Promise}           The request of automatic partitioning
 */
export const getPartitioningRequest = ({ partitioning }) => {
    return (
        new StorageClient().client.call(
            partitioning,
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Automatic",
                "Request",
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {string} partitioning     DBus path to a partitioning
 * @param {Object} request          A data object with the request
 */
export const setPartitioningRequest = ({ partitioning, request }) => {
    return new StorageClient().client.call(
        partitioning,
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Automatic",
            "Request",
            cockpit.variant("a{sv}", request)
        ]
    );
};

/**
 * @param {string} partitioning DBus path to a partitioning
 *
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const partitioningConfigureWithTask = ({ partitioning }) => {
    return new StorageClient().client.call(
        partitioning,
        "org.fedoraproject.Anaconda.Modules.Storage.Partitioning",
        "ConfigureWithTask", []
    );
};

export const resetPartitioning = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "ResetPartitioning", []
    );
};

/**
 * @param {string} task         DBus path to a task
 * @param {string} onSuccess    Callback to run after Succeeded signal is received
 * @param {string} onFail       Callback to run as an error handler
 *
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const runStorageTask = ({ task, onSuccess, onFail }) => {
    const taskProxy = new StorageClient().client.proxy(
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
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const scanDevicesWithTask = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage",
        "org.fedoraproject.Anaconda.Modules.Storage",
        "ScanDevicesWithTask", []
    );
};

/**
 * @returns {Promise}           The number of the mode
 */
export const getInitializationMode = () => {
    return (
        new StorageClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization",
                "InitializationMode",
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @param {int} mode            The number of the mode
 */
export const setInitializationMode = ({ mode }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization",
            "InitializationMode",
            cockpit.variant("i", mode)
        ]
    );
};

/**
 * @param {boolean} enabled     True if allowed, otherwise False
 */
export const setInitializeLabelsEnabled = ({ enabled }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskInitialization",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.DiskInitialization",
            "InitializeLabelsEnabled",
            cockpit.variant("b", enabled)
        ]
    );
};

/**
 * @param {string} drive     A drive name
 */
export const setBootloaderDrive = ({ drive }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/Bootloader",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.Bootloader",
            "Drive",
            cockpit.variant("s", drive)
        ]
    );
};

/**
 * @param {Array.<string>} drives A list of drives names
 */
export const setSelectedDisks = ({ drives }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DiskSelection",
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection",
            "SelectedDisks",
            cockpit.variant("as", drives)
        ]
    );
};
