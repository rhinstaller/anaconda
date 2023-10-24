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
import { StorageClient } from "./storage.js";

/**
 * @param {string} deviceName   A device name
 * @param {string} password     A password
 *
 * @returns {Promise}           Resolves true if success otherwise false
 */
export const unlockDevice = ({ deviceName, passphrase }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Handler",
        "UnlockDevice", [deviceName, passphrase]
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
    )
            .then(res => res[0]);
};

/**
 * @param {string} disk         Name A disk name
 *
 * @returns {Promise}           Resolves the device format data
 */
export const getFormatData = ({ diskName }) => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetFormatData", [diskName]
    )
            .then(res => res[0]);
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
 * @returns {Promise}           List of all mount points required on the platform
 */
export const getRequiredMountPoints = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetRequiredMountPoints", []
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
    )
            .then(res => res[0]);
};

/**
 * @returns {Promise}           Resolves all devices in a device tree
 */
export const getDevices = () => {
    return new StorageClient().client.call(
        "/org/fedoraproject/Anaconda/Modules/Storage/DeviceTree",
        "org.fedoraproject.Anaconda.Modules.Storage.DeviceTree.Viewer",
        "GetDevices", []
    );
};
