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

import {
    PageSection,
    Flex,
    FlexItem
} from '@patternfly/react-core';

import { useObject } from 'hooks';
import { AddressContext, Header } from '../Common.jsx';
import { Hostname } from './Hostname.jsx';

export const NetworkHostname = () => {
    const address = useContext(AddressContext);
    const [hostname, setHostname] = useState('test.hostname');

    const hostnameProxy = useObject(() => {
        const client = cockpit.dbus('org.fedoraproject.Anaconda.Modules.Network', { superuser: 'try', bus: 'none', address });
        const proxy = client.proxy(
            'org.fedoraproject.Anaconda.Modules.Network',
            '/org/fedoraproject/Anaconda/Modules/Network',
        );
        return proxy;
    }, null, [address]);

    const onDoneClicked = () => {
        cockpit.location.go(['summary']);
        hostnameProxy.SetHostname(hostname);
    };

    return (
        <>
            <Header
              done={onDoneClicked}
              title='Network & Host Name'
            />
            <PageSection>
                <Flex direction={{ default: 'column' }}>
                    <FlexItem>Flex item</FlexItem>
                    <FlexItem><Hostname hostname={hostname} setHostname={setHostname} /></FlexItem>
                </Flex>
            </PageSection>
        </>
    );
};
