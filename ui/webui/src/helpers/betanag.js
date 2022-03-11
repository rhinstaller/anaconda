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

import { parseIni } from "./conf.js";

export const readBuildstamp = () => {
    const file = cockpit.file("/.buildstamp", { superuser: "try", });
    return file.read()
            .then(parseIni)
            .finally(file.close);
};

export const getIsFinal = (buildstamp) => {
    let isFinal = buildstamp.Main.IsFinal;
    // If the value is not present, we get undefined which fails the test below and results
    // the intended fallback default of false.
    if ((isFinal === "true") || (isFinal === "True")) isFinal = true; else isFinal = false;
    return isFinal;
};
