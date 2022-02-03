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
import React, { createContext } from "react";
import cockpit from "cockpit";

import {
    Button,
    Level,
    PageSection, PageSectionVariants,
    Title,
} from "@patternfly/react-core";

import { usePageLocation } from "hooks";

const _ = cockpit.gettext;

export const AddressContext = createContext("");

export const Header = ({ done, doneDisabled, title }) => {
    const { path } = usePageLocation();
    const pageId = path[0];

    return (
        <PageSection variant={pageId === "summary" ? PageSectionVariants.light : PageSectionVariants.darker}>
            <Level hasGutter>
                {pageId !== "summary" &&
                <Button
                  id="header-done-btn"
                  isDisabled={!!doneDisabled}
                  variant="primary"
                  onClick={done}>
                    {_("Done")}
                </Button>}
                <Title headingLevel="h1" size="2xl">
                    {title || "Subpage description"}
                </Title>
                <Button
                  id={"help-btn-" + pageId}
                  variant="secondary"
                  onClick={() => console.log("I am on pageId " + (pageId || "summary"))}>
                    Help
                </Button>
            </Level>
        </PageSection>
    );
};
