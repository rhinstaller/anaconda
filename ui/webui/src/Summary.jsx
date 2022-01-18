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
import React from 'react';

import {
    ActionGroup,
    Alert,
    Button,
    Form,
    Gallery,
    HelperText, HelperTextItem,
    PageSection,
    Stack,
    Tile,
    Title,
} from '@patternfly/react-core';
import {
    BellIcon,
    BookIcon,
    ClockIcon,
    FlavorIcon,
    KeyIcon,
    KeyboardIcon,
    NetworkIcon,
    UserIcon,
} from '@patternfly/react-icons';

import { Header } from './Common.jsx';
import { InstallationDestination } from './storage/InstallationDestination.jsx';
import { InstallationSource } from './payloads/InstallationSource.jsx';
import { Keyboard } from './localization/Keyboard.jsx';
import { Language } from './localization/Language.jsx';
import { NetworkHostname } from './network/NetworkHostname.jsx';
import { RootAccount } from './users/RootAccount.jsx';
import { SoftwareSelection } from './payloads/SoftwareSelection.jsx';
import { TimeDate } from './timezone/TimeDate.jsx';
import { UserAccount } from './users/UserAccount.jsx';
import { usePageLocation } from 'hooks';

import './Summary.scss';

const _ = cockpit.gettext;

export const Summary = () => {
    const { path } = usePageLocation();
    const onSelect = event => {
        cockpit.location.go([event.currentTarget.id]);
    };

    let subpage;
    if (path[0] === 'keyboard') {
        subpage = <Keyboard />;
    } else if (path[0] === 'language') {
        subpage = <Language />;
    } else if (path[0] === 'timedate') {
        subpage = <TimeDate />;
    } else if (path[0] === 'installation-source') {
        subpage = <InstallationSource />;
    } else if (path[0] === 'software-selection') {
        subpage = <SoftwareSelection />;
    } else if (path[0] === 'installation-destination') {
        subpage = <InstallationDestination />;
    } else if (path[0] === 'network-hostname') {
        subpage = <NetworkHostname />;
    } else if (path[0] === 'root-account') {
        subpage = <RootAccount />;
    } else if (path[0] === 'user-account') {
        subpage = <UserAccount />;
    }

    return (
        <>
            {path[0] === 'summary' && <Header title={_("Installation summary")} />}
            {path[0] === 'summary' &&
            <PageSection className='summary'>
                <Form>
                    <Gallery hasGutter>
                        <Stack hasGutter>
                            <Title headingLevel='h1' size='2xl'>
                                {_("Localization")}
                            </Title>
                            <Tile onClick={onSelect} id='keyboard' title={_("Keyboard")} icon={<KeyboardIcon />} isStacked>
                                FILLME
                            </Tile>
                            <Tile onClick={onSelect} id='language' title={_("Language support")} icon={<BookIcon />} isStacked>
                                FILLME
                            </Tile>
                            <Tile onClick={onSelect} id='timedate' title={_("Time & Date")} icon={<ClockIcon />} isStacked>
                                FILLME
                            </Tile>
                        </Stack>
                        <Stack hasGutter>
                            <Title headingLevel='h1' size='2xl'>
                                Software
                            </Title>
                            <Tile onClick={onSelect} id='installation-source' title={_("Installation source")} icon={<BellIcon />} isStacked>
                                FILLME
                            </Tile>
                            <Tile onClick={onSelect} id='software-selection' title={_("Software Selection")} icon={<FlavorIcon />} isStacked>
                                FILLME
                            </Tile>
                        </Stack>
                        <Stack hasGutter>
                            <Title headingLevel='h1' size='2xl'>
                                System
                            </Title>
                            <Tile onClick={onSelect} id='installation-destination' title={_("Installation destination")} icon={<BellIcon />} isStacked>
                                FILLME
                            </Tile>
                            <Tile onClick={onSelect} id='network-hostname' title={_("Network & Host name")} icon={<NetworkIcon />} isStacked>
                                FILLME
                            </Tile>
                        </Stack>
                        <Stack hasGutter>
                            <Title headingLevel='h1' size='2xl'>
                                User settings
                            </Title>
                            <Tile onClick={onSelect} id='root-account' title={_("Root password")} icon={<KeyIcon />} isStacked>
                                <HelperText>
                                    <HelperTextItem variant='warning' hasIcon>{_("Root account is disabled")}</HelperTextItem>
                                </HelperText>
                            </Tile>
                            <Tile onClick={onSelect} id='user-account' title={_("User creation")} icon={<UserIcon />} isStacked>
                                <HelperText>
                                    <HelperTextItem variant='warning' hasIcon>{_("No user will be created")}</HelperTextItem>
                                </HelperText>
                            </Tile>
                        </Stack>
                    </Gallery>
                    <Alert variant='warning' isInline title={_("Please complete items marked with this icon before continuing to the next step")} />
                    <ActionGroup>
                        <Button id='begin-installation-btn' variant='primary' isDisabled>{_("Begin installation")}</Button>
                        <Button variant='link'>{_("Quit")}</Button>
                        <HelperText className='action-hint'>
                            <HelperTextItem variant='indeterminate'>{_("We won't touch your disks until you click 'Begin installation'")}</HelperTextItem>
                        </HelperText>
                    </ActionGroup>
                </Form>
            </PageSection>}
            {path[0] !== 'summary' && subpage}
        </>
    );
};
