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
    StorageClient,
    runStorageTask,
} from "./storage.js";
import {
    setBootloaderDrive,
} from "./storage_bootloader.js";
import {
    setInitializeLabelsEnabled,
} from "./storage_disk_initialization.js";

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
 *
 * @returns {Promise}               The partitioning method
 */
export const getPartitioningMethod = ({ partitioning }) => {
    return (
        new StorageClient().client.call(
            partitioning,
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage.Partitioning",
                "PartitioningMethod",
            ]
        )
                .then(res => res[0].v)
    );
};

/**
 * @returns {Promise}           The applied partitioning
 */
export const getAppliedPartitioning = () => {
    return (
        new StorageClient().client.call(
            "/org/fedoraproject/Anaconda/Modules/Storage",
            "org.freedesktop.DBus.Properties",
            "Get",
            [
                "org.fedoraproject.Anaconda.Modules.Storage",
                "AppliedPartitioning",
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

/*
 * @param {string} partitioning DBus path to a partitioning
 * @param {Array.<Object>} requests An array of request objects
 */
export const setManualPartitioningRequests = ({ partitioning, requests }) => {
    return new StorageClient().client.call(
        partitioning,
        "org.freedesktop.DBus.Properties",
        "Set",
        [
            "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Manual",
            "Requests",
            cockpit.variant("aa{sv}", requests)
        ]
    );
};

/**
 * @param {string} partitioning DBus path to a partitioning
 *
 * @returns {Promise}           The gathered requests for manual partitioning
 */
export const gatherRequests = ({ partitioning }) => {
    return new StorageClient().client.call(
        partitioning,
        "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Manual",
        "GatherRequests",
        []
    );
};

export const applyStorage = async ({ partitioning, encrypt, encryptPassword, onFail, onSuccess }) => {
    await setInitializeLabelsEnabled({ enabled: true });
    await setBootloaderDrive({ drive: "" });

    const [part] = partitioning ? [partitioning] : await createPartitioning({ method: "AUTOMATIC" });

    if (encrypt) {
        await partitioningSetEncrypt({ partitioning: part, encrypt });
    }
    if (encryptPassword) {
        await partitioningSetPassphrase({ partitioning: part, passphrase: encryptPassword });
    }

    const tasks = await partitioningConfigureWithTask({ partitioning: part });

    runStorageTask({
        task: tasks[0],
        onFail,
        onSuccess: () => applyPartitioning({ partitioning: part })
                .then(onSuccess)
                .catch(onFail)
    });
};
