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

import React from "react";
import cockpit from "cockpit";

import {
    Form, FormGroup,
    SelectGroup, SelectOption, Select, SelectVariant,
} from "@patternfly/react-core";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";

import { AddressContext } from "../Common.jsx";

import {
    getLanguages, getLanguageData,
    getLocales, getLocaleData,
    setLanguage,
} from "../../apis/localization.js";

import {
    convertToCockpitLang,
    getDefaultLang,
    setLangCookie
} from "../../helpers/language.js";

const _ = cockpit.gettext;

const getLanguageEnglishName = lang => lang["english-name"].v;
const getLanguageId = lang => lang["language-id"].v;
const getLanguageNativeName = lang => lang["native-name"].v;
const getLocaleId = locale => locale["locale-id"].v;
const getLocaleNativeName = locale => locale["native-name"].v;

class LanguageSelector extends React.Component {
    constructor (props) {
        super(props);
        this.state = {
            languages: [],
            locales: [],
            lang: getDefaultLang(),
        };
        this.updateDefaultSelection = this.updateDefaultSelection.bind(this);
    }

    componentDidMount () {
        // Set backend default language according to cockpit language cookies
        setLanguage({ lang: this.state.lang }).catch(this.props.onAddErrorNotification);

        getLanguages().then(ret => {
            const languages = ret;
            // Create the languages state object
            Promise.all(languages.map(lang => getLanguageData({ lang })))
                    .then(langs => this.setState({ languages: langs }));

            // Create the locales state object
            Promise.all(languages.map(lang => getLocales({ lang })))
                    .then(res => {
                        return Promise.all(
                            res.map(langLocales => {
                                return Promise.all(langLocales.map(locale =>
                                    getLocaleData({ locale })
                                ));
                            })
                        );
                    })
                    .then(res => this.setState({ locales: res }, this.updateDefaultSelection));
        });
    }

    updateDefaultSelection () {
        const languageId = this.state.lang.split("_")[0];
        const currentLangLocales = this.state.locales.find(langLocales => getLanguageId(langLocales[0]) === languageId);
        const currentLocale = currentLangLocales.find(locale => getLocaleId(locale) === this.state.lang);

        this.setState({ selectedItem: getLocaleNativeName(currentLocale) });
    }

    render () {
        const { isOpen, languages, locales, selectedItem } = this.state;
        const handleOnSelect = (_, lang) => {
            /*
             * When a language is selected from the list, update the backend language,
             * set the cookie and reload the browser for the new translation file to get loaded.
             * Since the component will re-mount, the `selectedItem` state attribute will be set
             * from the `updateDefaultSelection` method.
             *
             * FIXME: Anaconda API returns en_US, de_DE etc, cockpit expects en-us, de-de etc
             * Make sure to check if this is generalized enough to keep so.
             */
            setLangCookie({ cockpitLang: convertToCockpitLang({ lang: lang.localeId }) });
            setLanguage({ lang: lang.localeId }).catch(this.props.onAddErrorNotification);

            window.location.reload(true);
        };

        const isLoading = languages.length === 0 || languages.length !== locales.length;

        if (isLoading) {
            return <EmptyStatePanel loading />;
        }

        const options = (
            locales.map(langLocales => {
                const currentLang = languages.find(lang => getLanguageId(lang) === getLanguageId(langLocales[0]));

                return (
                    <SelectGroup
                      label={cockpit.format("$0 ($1)", getLanguageNativeName(currentLang), getLanguageEnglishName(currentLang))}
                      key={getLanguageId(currentLang)}>
                        {langLocales.map(locale => (
                            <SelectOption
                              id={getLocaleId(locale).split(".UTF-8")[0]}
                              key={getLocaleId(locale)}
                              value={{
                                  toString: () => getLocaleNativeName(locale),
                                  // Add a compareTo for custom filtering - filter also by english name
                                  localeId: getLocaleId(locale)
                              }}
                            />
                        ))}
                    </SelectGroup>
                );
            })
        );

        return (
            <Select
              className="language-menu"
              isGrouped
              isOpen={isOpen}
              maxHeight="30rem"
              onClear={() => this.setState({ selectedItem: null })}
              onSelect={handleOnSelect}
              onToggle={isOpen => this.setState({ isOpen })}
              selections={selectedItem}
              toggleId="language-menu-toggle"
              variant={SelectVariant.typeahead}
              width="30rem"
              {...(isLoading && { loadingVariant: "spinner" })}

            >
                {options}
            </Select>
        );
    }
}
LanguageSelector.contextType = AddressContext;

export const InstallationLanguage = ({ onAddErrorNotification }) => {
    return (
        <Form>
            <FormGroup label={_("Select the language you would like to use.")}>
                <LanguageSelector onAddErrorNotification={onAddErrorNotification} />
            </FormGroup>
        </Form>
    );
};
