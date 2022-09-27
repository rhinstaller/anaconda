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

import React from "react";

import {
    Button,
    Flex, FlexItem,
    Label,
    PageSection, PageSectionVariants,
    Popover, PopoverPosition,
    TextContent, Text, TextVariants
} from "@patternfly/react-core";
import { InfoCircleIcon } from "@patternfly/react-icons";

const _ = cockpit.gettext;

const prerelease = _("Pre-release");

export const AnacondaHeader = ({ beta, title, setShowLogViewer }) => {
    const betanag = beta
        ? (
            <Popover
              headerContent={_("This is unstable, pre-release software")}
              minWidth="30rem"
              position={PopoverPosition.auto}
              bodyContent={
                  <TextContent>
                      <Text component={TextVariants.p}>
                          {_("Notice: This is pre-released software that is intended for development and testing purposes only. Do NOT use this software for any critical work or for production environments.")}
                      </Text>
                      <Text component={TextVariants.p}>
                          {_("By continuing to use this software, you understand and accept the risks associated with pre-released software, that you intend to use this for testing and development purposes only and are willing to report any bugs or issues in order to enhance this work.")}
                      </Text>
                      <Text component={TextVariants.p}>
                          {_("If you do not understand or accept the risks, then please exit this program.")}
                      </Text>
                  </TextContent>
              }
            >
                <Label color="orange" icon={<InfoCircleIcon />} id="betanag-icon"> {prerelease} </Label>
            </Popover>
        )
        : null;

    return (
        <PageSection variant={PageSectionVariants.light}>
            <Flex spaceItems={{ default: "spaceItemsSm" }} alignItems={{ default: "alignItemsCenter" }}>
                <TextContent>
                    <Text component="h1">{title}</Text>
                </TextContent>
                {betanag}
                <FlexItem align={{ default: "alignRight" }}>
                    <Button
                      aria-label={_("Show log")}
                      id="global-show-log-btn"
                      variant="tertiary"
                      onClick={() => {
                          setShowLogViewer(true);
                      }}
                    >
                        {_("Show log")}
                    </Button>
                </FlexItem>
            </Flex>
        </PageSection>
    );
};
