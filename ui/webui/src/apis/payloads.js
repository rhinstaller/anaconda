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
import { _callClient } from "./helpers.js";

const OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Payloads";
const INTERFACE_NAME = "org.fedoraproject.Anaconda.Modules.Payloads";

const callClient = (...args) => {
    return _callClient(PayloadsClient, OBJECT_PATH, INTERFACE_NAME, ...args);
};

export class PayloadsClient {
    constructor (address) {
        if (PayloadsClient.instance && (!address || PayloadsClient.instance.address === address)) {
            return PayloadsClient.instance;
        }

        PayloadsClient.instance?.client.close();

        PayloadsClient.instance = this;

        this.client = cockpit.dbus(
            INTERFACE_NAME,
            { superuser: "try", bus: "none", address }
        );
        this.address = address;
    }

    init () {
        this.client.addEventListener(
            "close", () => console.error("Payloads client closed")
        );
    }
}

/**
 *
 * @returns {Promise}           Resolves the total space required by the payload
 */
export const getRequiredSpace = () => {
    return callClient("CalculateRequiredSpace", []);
};
