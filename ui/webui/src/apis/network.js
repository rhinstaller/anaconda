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

import { getConnectedAction } from "../actions/network-actions.js";
import { debug } from "../helpers/log.js";
import { _getProperty } from "./helpers.js";

const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Network";
const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Network";

const getProperty = (...args) => {
    return _getProperty(NetworkClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class NetworkClient {
    constructor (address) {
        if (NetworkClient.instance && (!address || NetworkClient.instance.address === address)) {
            return NetworkClient.instance;
        }

        NetworkClient.instance?.client.close();

        NetworkClient.instance = this;

        this.client = cockpit.dbus(
            INTERFACE_NAME,
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener("close", () => console.error("Network client closed"));
    }
}

/**
 * @returns {Promise}           The bool state of the network connection
 */
export const getConnected = () => {
    return getProperty("Connected");
};

export const startEventMonitorNetwork = ({ dispatch }) => {
    return new NetworkClient().client.subscribe(
        { },
        (path, iface, signal, args) => {
            switch (signal) {
            case "PropertiesChanged":
                if (args[0] === INTERFACE_NAME && Object.hasOwn(args[1], "Connected")) {
                    dispatch(getConnectedAction());
                } else {
                    debug(`Unhandled signal on ${path}: ${iface}.${signal}`, JSON.stringify(args));
                }
                break;
            default:
                debug(`Unhandled signal on ${path}: ${iface}.${signal}`, JSON.stringify(args));
            }
        }
    );
};

export const initDataNetwork = ({ dispatch }) => {
    return Promise.all([
        dispatch(getConnectedAction())
    ]);
};
