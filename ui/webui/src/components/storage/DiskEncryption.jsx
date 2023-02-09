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
import React from "react";

import {
    Bullseye,
    EmptyState,
    EmptyStateIcon,
    Spinner,
    TextContent,
    TextVariants,
    Text,
    Title,
} from "@patternfly/react-core";

import { AnacondaPage } from "../AnacondaPage.jsx";

const _ = cockpit.gettext;

export const DiskEncryption = ({ isInProgress }) => {
    if (isInProgress) {
        return (
            <Bullseye>
                <EmptyState id="installation-destination-next-spinner">
                    <EmptyStateIcon variant="container" component={Spinner} />
                    <Title size="lg" headingLevel="h4">
                        {_("Checking storage configuration")}
                    </Title>
                    <TextContent>
                        <Text component={TextVariants.p}>
                            {_("This may take a moment")}
                        </Text>
                    </TextContent>
                </EmptyState>
            </Bullseye>
        );
    }

    return (
        <AnacondaPage title={_("Encrypt the selected devices?")}>
            <p>TODO</p>
        </AnacondaPage>

    );
};
