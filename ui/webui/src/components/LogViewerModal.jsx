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

import React, { useEffect, useState } from "react";

import { LogViewer, LogViewerSearch } from "@patternfly/react-log-viewer";

import { watchLogFile } from "../helpers/logs.js";

import {
    Button,
    Modal, ModalVariant,
    Toolbar, ToolbarContent, ToolbarItem,
    Text, TextContent, TextVariants,
    Flex,
} from "@patternfly/react-core";

const _ = cockpit.gettext;

const AnacondaLogViewer = () => {
    const [logData, setLogData] = useState("");

    useEffect(() => {
        const appendLogData = (newLogData, dataTag, error) => {
            setLogData(l => l + newLogData);
            if (error) {
                console.log("Log file read failed.");
                console.log(error);
            }
        };
        watchLogFile("/tmp/anaconda.log", appendLogData);
    }, []);

    return (
        <LogViewer
          // see CSS file for a PF workaround needed
          // for line numbers to work correctly
          hasLineNumbers
          isTextWrapped={false}
          height={450}
          data={logData}
          id="log-viewer-element"
          toolbar={
              <Toolbar>
                  <ToolbarContent>
                      <ToolbarItem>
                          <LogViewerSearch placeholder={_("Search value")} />
                      </ToolbarItem>
                  </ToolbarContent>
              </Toolbar>
          }
        />
    );
};

export const LogViewerModal = ({ setShowLogViewer }) => {
    return (
        <Modal
          id="log-viewer-modal"
          actions={[
              <Button
                id="log-viewer-exit-btn"
                key="cancel"
                onClick={() => setShowLogViewer(false)}
                variant="primary">
                  {_("Close")}
              </Button>
          ]}
          isOpen
          onClose={() => setShowLogViewer(false)}
          title={_("Installer log")}
          variant={ModalVariant.medium}
        >
            <Flex direction={{ default: "column" }}>
                <TextContent
                  id="anaconda-version-label"
                >
                    <Text component={TextVariants.p}>
                        {_("Installer version") + " 38.5"}
                    </Text>
                </TextContent>
                <AnacondaLogViewer />
            </Flex>
        </Modal>
    );
};
