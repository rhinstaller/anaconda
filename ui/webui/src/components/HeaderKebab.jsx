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

import React, { useState, useEffect } from "react";
import {
    AboutModal,
    Button,
    DescriptionList,
    DescriptionListDescription,
    DescriptionListGroup,
    DescriptionListTerm,
    Flex,
    Stack,
    StackItem,
    Dropdown,
    DropdownItem,
    MenuToggle,
    DropdownList
} from "@patternfly/react-core";
import {
    ExternalLinkAltIcon,
    EllipsisVIcon
} from "@patternfly/react-icons";

import { read_os_release as readOsRelease } from "os-release.js";
import { getAnacondaVersion } from "../helpers/product.js";
import { UserIssue } from "./Error.jsx";

import "./HeaderKebab.scss";

const _ = cockpit.gettext;

const AboutModalVersions = () => {
    const [anacondaVersion, setAnacondaVersion] = useState("");

    useEffect(() => {
        getAnacondaVersion().then(content => setAnacondaVersion(content));
    }, []);

    return (
        <DescriptionList isHorizontal id="about-modal-versions">
            <DescriptionListGroup>
                <DescriptionListTerm>Anaconda</DescriptionListTerm>
                <DescriptionListDescription>{anacondaVersion}</DescriptionListDescription>
            </DescriptionListGroup>
        </DescriptionList>
    );
};

const ProductName = () => {
    const [osRelease, setOsRelease] = useState();

    useEffect(() => {
        readOsRelease().then(setOsRelease);
    }, []);

    if (!osRelease) {
        return null;
    }

    return (
        <Stack hasGutter>
            <StackItem id="about-modal-title" className="title">{cockpit.format(_("$0 installer"), osRelease.PRETTY_NAME)}</StackItem>
            <StackItem id="about-modal-subtitle" className="subtitle">{_("Powered by Anaconda")}</StackItem>
        </Stack>
    );
};

const AnacondaAboutModal = ({ isModalOpen, setIsAboutModalOpen }) => {
    const toggleModal = () => {
        setIsAboutModalOpen(!isModalOpen);
    };

    return (
        <AboutModal
          id="about-modal"
          isOpen={isModalOpen}
          noAboutModalBoxContentContainer
          onClose={toggleModal}
          productName={<ProductName />}
        >
            <Flex direction={{ default: "column" }} justifyContent={{ default: "justifyContentSpaceBetween" }}>
                <AboutModalVersions />
                <Button
                  isInline
                  id="anaconda-page-button"
                  variant="link"
                  icon={<ExternalLinkAltIcon />}
                  href="https://github.com/rhinstaller/anaconda"
                  target="_blank"
                  component="a">
                    {_("Anaconda project page")}
                </Button>
            </Flex>
        </AboutModal>
    );
};

export const HeaderKebab = ({ reportLinkURL, isConnected }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [isAboutModalOpen, setIsAboutModalOpen] = useState(false);
    const [isReportIssueOpen, setIsReportIssueOpen] = useState(false);

    const onToggle = () => {
        setIsOpen(!isOpen);
    };
    const onSelect = () => {
        setIsOpen(false);
    };

    const handleAboutModal = () => {
        setIsAboutModalOpen(true);
    };

    const handleReportIssue = () => {
        setIsReportIssueOpen(true);
    };

    const dropdownItems = [
        <DropdownItem id="about-modal-dropdown-item-about" key="about" onClick={handleAboutModal}>
            {_("About")}
        </DropdownItem>,
        <DropdownItem id="about-modal-dropdown-item-report" key="report issue" onClick={handleReportIssue}>
            {_("Report Issue")}
        </DropdownItem>,
    ];

    return (
        <>
            <Dropdown
              isOpen={isOpen}
              onSelect={onSelect}
              popperProps={{ position: "right" }}
              toggle={toggleRef =>
                  <MenuToggle
                    className="pf-m-align-right"
                    id="toggle-kebab"
                    isExpanded={isOpen}
                    onClick={onToggle}
                    ref={toggleRef}
                    variant="plain">
                      <EllipsisVIcon />
                  </MenuToggle>}
              shouldFocusToggleOnSelect>
                <DropdownList>
                    {dropdownItems}
                </DropdownList>
            </Dropdown>
            {isAboutModalOpen &&
                <AnacondaAboutModal
                  isModalOpen={isAboutModalOpen}
                  setIsAboutModalOpen={setIsAboutModalOpen}
                />}
            {isReportIssueOpen &&
                <UserIssue
                  reportLinkURL={reportLinkURL}
                  setIsReportIssueOpen={setIsReportIssueOpen}
                  isConnected={isConnected}
                />}
        </>
    );
};
