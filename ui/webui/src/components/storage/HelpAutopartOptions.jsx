import React from "react";
import cockpit from "cockpit";

import {
    Text,
    TextContent,
    TextVariants,
} from "@patternfly/react-core";

const _ = cockpit.gettext;

export const helpEraseAll = (
    <TextContent>
        <Text component={TextVariants.p}>
            {_("Removes all partitions on the selected devices. " +
            "This includes partitions created by other operating systems.")}
        </Text>

        <Text component={TextVariants.p}>
            {_("This option will remove data from the selected devices. " +
            "Make sure you have backups.")}
        </Text>
    </TextContent>
);

export const helpUseFreeSpace = (
    <TextContent>
        <Text component={TextVariants.p}>
            {_("Retains your current data and partitions and uses " +
            "only the unpartitioned space on the selected devices, " +
            "assuming you have enough free space available.")}
        </Text>
    </TextContent>
);
