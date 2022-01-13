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
import cockpit from 'cockpit';
import React, { useState, useContext } from 'react';
import { TextInput } from '@patternfly/react-core';

import { useEvent, useObject } from 'hooks';
import { AddressContext } from '../Common.jsx';

export const Hostname = () => {
    const [hostname, setHostname] = useState('test.hostname');
    const address = useContext(AddressContext);

    const hostnameProxy = useObject(() => {
        const client = cockpit.dbus('org.fedoraproject.Anaconda.Modules.Network', { superuser: 'try', bus: 'none', address });
        const proxy = client.proxy(
            'org.fedoraproject.Anaconda.Modules.Network',
            '/org/fedoraproject/Anaconda/Modules/Network',
        );
        setHostname(proxy.Hostname);

        return proxy;
    }, null, [address]);

    useEvent(hostnameProxy, 'changed', (event, data) => {
        setHostname(hostnameProxy.Hostname);
    });

    console.info(hostnameProxy);

    const onHostnameChange = (value) => {
        hostnameProxy.SetHostname(value);
        setHostname(value);
    };

    // FIXME: Add validation of the hostname
    return <TextInput
      value={hostname}
      onChange={onHostnameChange}
      aria-label='hostname text input' />;
};
