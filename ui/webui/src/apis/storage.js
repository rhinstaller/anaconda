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

import {
    getDevicesAction,
    getDiskSelectionAction,
    getPartitioningDataAction
} from "../actions/storage-actions.js";

import { debug } from "../helpers/log.js";
import { _callClient, _getProperty } from "./helpers.js";

const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Storage";
const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Storage";

const callClient = (...args) => {
    return _callClient(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};
const getProperty = (...args) => {
    return _getProperty(StorageClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class StorageClient {
    constructor (address) {
        if (StorageClient.instance && (!address || StorageClient.instance.address === address)) {
            return StorageClient.instance;
        }

        StorageClient.instance?.client.close();

        StorageClient.instance = this;

        this.client = cockpit.dbus(
            INTERFACE_NAME,
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener("close", () => console.error("Storage client closed"));
    }
}

/**
 * @param {string} task         DBus path to a task
 * @param {string} onSuccess    Callback to run after Succeeded signal is received
 * @param {string} onFail       Callback to run as an error handler
 * @param {Boolean} getResult   True if the result should be fetched, False otherwise
 *
 * @returns {Promise}           Resolves a DBus path to a task
 */
export const runStorageTask = ({ task, onSuccess, onFail, getResult = false }) => {
    // FIXME: This is a workaround for 'Succeeded' signal being emited twice
    let succeededEmitted = false;
    const taskProxy = new StorageClient().client.proxy(
        "org.fedoraproject.Anaconda.Task",
        task
    );
    const addEventListeners = () => {
        taskProxy.addEventListener("Stopped", () => taskProxy.Finish().catch(onFail));
        taskProxy.addEventListener("Succeeded", () => {
            if (succeededEmitted) {
                return;
            }
            succeededEmitted = true;

            const promise = getResult ? taskProxy.GetResult() : Promise.resolve();

            return promise
                    .then(res => onSuccess(res?.v))
                    .catch(onFail);
        });
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
    return callClient("ScanDevicesWithTask", []);
};

export const startEventMonitorStorage = ({ dispatch }) => {
    return new StorageClient().client.subscribe(
        { },
        (path, iface, signal, args) => {
            switch (signal) {
            case "PropertiesChanged":
                if (args[0] === "org.fedoraproject.Anaconda.Modules.Storage.DiskSelection") {
                    dispatch(getDiskSelectionAction());
                } else if (args[0] === "org.fedoraproject.Anaconda.Modules.Storage.Partitioning.Manual" && Object.hasOwn(args[1], "Requests")) {
                    dispatch(getPartitioningDataAction({ requests: args[1].Requests.v, partitioning: path }));
                } else if (args[0] === INTERFACE_NAME && Object.hasOwn(args[1], "CreatedPartitioning")) {
                    const last = args[1].CreatedPartitioning.v.length - 1;
                    dispatch(getPartitioningDataAction({ partitioning: args[1].CreatedPartitioning.v[last] }));
                } else {
                    debug(`Unhandled signal on ${path}: ${iface}.${signal} ${JSON.stringify(args)}`);
                }
                break;
            default:
                debug(`Unhandled signal on ${path}: ${iface}.${signal} ${JSON.stringify(args)}`);
            }
        });
};

export const initDataStorage = ({ dispatch }) => {
    return getProperty("CreatedPartitioning")
            .then(res => {
                if (res.length !== 0) {
                    return Promise.all(res.map(path => dispatch(getPartitioningDataAction({ partitioning: path }))));
                }
            })
            .then(() => dispatch(getDevicesAction()))
            .then(() => dispatch(getDiskSelectionAction()));
};
