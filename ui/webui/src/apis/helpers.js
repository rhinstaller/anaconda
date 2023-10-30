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

export const _callClient = (Client, OBJECT_PATH, INTERFACE_NAME, ...args) => {
    return new Client().client.call(OBJECT_PATH, INTERFACE_NAME, ...args).then(res => res[0]);
};

export const _setProperty = (Client, OBJECT_PATH, INTERFACE_NAME, ...args) => {
    return new Client().client.call(
        OBJECT_PATH, "org.freedesktop.DBus.Properties", "Set", [INTERFACE_NAME, ...args]
    );
};

export const _getProperty = (Client, OBJECT_PATH, INTERFACE_NAME, ...args) => {
    return new Client().client.call(
        OBJECT_PATH, "org.freedesktop.DBus.Properties", "Get", [INTERFACE_NAME, ...args]
    ).then(res => res[0].v);
};
