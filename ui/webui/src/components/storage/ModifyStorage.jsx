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
import React, { useContext, useState } from "react";

import {
    Button,
    Modal,
    Text,
    TextContent,
    TextVariants,
} from "@patternfly/react-core";
import { WrenchIcon, ExternalLinkAltIcon } from "@patternfly/react-icons";

import { SystemTypeContext } from "../Common.jsx";

const _ = cockpit.gettext;
const N_ = cockpit.noop;

const startBlivetGUI = (onStart, onStarted, errorHandler) => {
    console.log("Spawning blivet-gui.");
    // We don't have an event informing that blivet-gui started so just wait a bit.
    const timeoutId = window.setTimeout(onStarted, 3000);
    cockpit.spawn(["blivet-gui", "--keep-above", "--auto-dev-updates"], { err: "message" })
            .then(() => {
                console.log("blivet-gui exited.");
                // If the blivet-gui exits earlier cancel the delay
                window.clearTimeout(timeoutId);
                return onStarted();
            })
            .catch((error) => { window.clearTimeout(timeoutId); errorHandler(error) });
    onStart();
};

const StorageModifiedModal = ({ onClose, onRescan }) => {
    return (
        <Modal
          id="storage-modified-modal"
          title={_("Modified storage")}
          isOpen
          variant="small"
          showClose={false}
          footer={
              <>
                  <Button
                    onClick={() => { onClose(); onRescan() }}
                    variant="primary"
                    id="storage-modified-modal-rescan-btn"
                    key="rescan"
                  >
                      {_("Rescan storage")}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => onClose()}
                    id="storage-modified-modal-ignore-btn"
                    key="ignore"
                  >
                      {_("Ignore")}
                  </Button>
              </>
          }>
            {_("If you have made changes on partitions or disks, please rescan storage.")}
        </Modal>
    );
};

const ModifyStorageModal = ({ onClose, onToolStarted, errorHandler }) => {
    const [toolIsStarting, setToolIsStarting] = useState(false);
    const onStart = () => setToolIsStarting(true);
    const onStarted = () => { setToolIsStarting(false); onToolStarted() };
    return (
        <Modal
          id="modify-storage-modal"
          title={_("Modify storage")}
          isOpen
          variant="small"
          titleIconVariant="warning"
          showClose={false}
          footer={
              <>
                  <Button
                    onClick={() => startBlivetGUI(
                        onStart,
                        onStarted,
                        errorHandler
                    )}
                    id="modify-storage-modal-modify-btn"
                    icon={toolIsStarting ? null : <ExternalLinkAltIcon />}
                    isLoading={toolIsStarting}
                    isDisabled={toolIsStarting}
                    variant="primary"
                  >
                      {_("Launch Blivet-gui storage editor")}
                  </Button>
                  <Button
                    variant="link"
                    onClick={() => onClose()}
                    id="modify-storage-modal-cancel-btn"
                    key="cancel"
                    isDisabled={toolIsStarting}
                  >
                      {_("Cancel")}
                  </Button>
              </>
          }>
            <TextContent>
                <Text component={TextVariants.p}>
                    {_("Blivet-gui is an advanced storage editor that lets you resize, delete, and create partitions. It can set up LVM and much more.")}
                </Text>
                <Text component={TextVariants.p}>
                    {_("Changes made in Blivet-gui will directly affect your storage.")}
                </Text>
            </TextContent>
        </Modal>
    );
};

export const ModifyStorage = ({ idPrefix, onCritFail, onRescan }) => {
    const [openedDialog, setOpenedDialog] = useState("");
    const isBootIso = useContext(SystemTypeContext) === "BOOT_ISO";

    if (isBootIso) {
        return null;
    }

    return (
        <>
            <Button
              id={idPrefix + "-modify-storage"}
              variant="link"
              icon={<WrenchIcon />}
              onClick={() => setOpenedDialog("modify")}>
                {_("Modify storage")}
            </Button>
            {openedDialog === "modify" &&
            <ModifyStorageModal
              onClose={() => setOpenedDialog("")}
              onToolStarted={() => setOpenedDialog("rescan")}
              errorHandler={onCritFail({ context: N_("Modifying the storage failed.") })}
            />}
            {openedDialog === "rescan" &&
            <StorageModifiedModal
              onClose={() => setOpenedDialog("")}
              onRescan={onRescan}
            />}
        </>
    );
};
