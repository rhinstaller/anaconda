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

import { getPasswordPoliciesAction } from "../actions/runtime-actions.js";
import { debug } from "../helpers/log.js";
import { _getProperty } from "./helpers.js";

const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Runtime/UserInterface";
const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Runtime.UserInterface";

const getProperty = (...args) => {
    return _getProperty(RuntimeClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class RuntimeClient {
    constructor (address) {
        if (RuntimeClient.instance && (!address || RuntimeClient.instance.address === address)) {
            return RuntimeClient.instance;
        }

        RuntimeClient.instance?.client.close();

        RuntimeClient.instance = this;

        this.client = cockpit.dbus(
            "org.fedoraproject.Anaconda.Modules.Runtime",
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener(
            "close", () => console.error("Runtime client closed")
        );
    }
}

/**
 *
 * @returns {Promise}           Reports if the given OS release is considered final
 */
export const getIsFinal = () => {
    return getProperty("IsFinal");
};

/**
 *
 * @returns {Promise}           Returns the password policies
 */
export const getPasswordPolicies = () => {
    return getProperty("PasswordPolicies");
};

export const startEventMonitorRuntime = ({ dispatch }) => {
    return new RuntimeClient().client.subscribe(
        { },
        (path, iface, signal, args) => {
            switch (signal) {
            case "PropertiesChanged":
                if (args[0] === INTERFACE_NAME && Object.hasOwn(args[1], "PasswordPolicies")) {
                    dispatch(getPasswordPoliciesAction());
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

export const initDataRuntime = ({ dispatch }) => {
    return Promise.all([
        dispatch(getPasswordPoliciesAction())
    ]);
};
