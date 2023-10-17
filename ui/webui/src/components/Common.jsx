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
import { HelpIcon } from "@patternfly/react-icons";
import { Popover, PopoverPosition } from "@patternfly/react-core";

export const AddressContext = createContext("");
export const ConfContext = createContext();
export const LanguageContext = createContext("");
export const SystemTypeContext = createContext(null);
export const OsReleaseContext = createContext(null);

export const FormGroupHelpPopover = ({ helpContent }) => {
    return (
        <Popover
          bodyContent={helpContent}
          position={PopoverPosition.auto}
        >
            <button
              type="button"
              onClick={e => e.preventDefault()}
              className="pf-v5-c-form__group-label-help"
            >
                <HelpIcon />
            </button>
        </Popover>
    );
};
