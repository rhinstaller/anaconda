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
    Form,
    FormGroup,
    SelectGroup,
    SelectOption,
    Select,
    SelectVariant,
    Text,
    TextVariants,
    TextContent,
} from "@patternfly/react-core";

import { EmptyStatePanel } from "cockpit-components-empty-state.jsx";
import { AddressContext } from "../Common.jsx";
import { setLocale } from "../../apis/boss.js";

import {
    getLanguage,
    getLanguages,
    getLanguageData,
    getLocales,
    getLocaleData,
    setLanguage,
} from "../../apis/localization.js";

import {
    convertToCockpitLang,
    getLangCookie,
    setLangCookie
} from "../../helpers/language.js";
import { AnacondaPage } from "../AnacondaPage.jsx";

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
        };
        this.updateDefaultSelection = this.updateDefaultSelection.bind(this);
        this.renderOptions = this.renderOptions.bind(this);
    }

    componentDidMount () {
        getLanguage().then(lang => {
            this.setState({ lang });
            const cockpitLang = convertToCockpitLang({ lang });
            if (getLangCookie() !== cockpitLang) {
                setLangCookie({ cockpitLang });
                window.location.reload(true);
            }
            return setLocale({ locale: lang });
        })
                .catch(this.props.onAddErrorNotification);

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

    renderOptions (filter) {
        const { languages, locales } = this.state;
        const idPrefix = this.props.idPrefix;
        const filterLow = filter.toLowerCase();

        return locales.reduce((filtered, langLocales) => {
            const currentLang = languages.find(lang => getLanguageId(lang) === getLanguageId(langLocales[0]));

            const label = cockpit.format("$0 ($1)", getLanguageNativeName(currentLang), getLanguageEnglishName(currentLang));

            if (!filter || label.toLowerCase().indexOf(filterLow) !== -1) {
                filtered.push(
                    <SelectGroup
                      label={label}
                      key={getLanguageId(currentLang)}>
                        {langLocales.map(locale => (
                            <SelectOption
                              id={idPrefix + "-option-" + getLocaleId(locale).split(".UTF-8")[0]}
                              key={getLocaleId(locale)}
                              value={{
                                  toString: () => getLocaleNativeName(locale),
                                  localeId: getLocaleId(locale)
                              }}
                            />
                        ))}
                    </SelectGroup>
                );
            }
            return filtered;
        }, []);
    }

    render () {
        const { isOpen, languages, locales, selectedItem } = this.state;
        const idPrefix = this.props.idPrefix;
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
            setLanguage({ lang: lang.localeId })
                    .then(() => setLocale({ locale: lang.localeId }))
                    .catch(this.props.onAddErrorNotification);

            window.location.reload(true);
        };

        const isLoading = languages.length === 0 || languages.length !== locales.length;

        if (isLoading) {
            return <EmptyStatePanel loading />;
        }

        const options = this.renderOptions("");

        return (
            <Select
              aria-invalid={!selectedItem}
              className={idPrefix + "-menu"}
              isGrouped
              isOpen={isOpen}
              maxHeight="30rem"
              noResultsFoundText={_("No results found")}
              onClear={() => {
                  this.props.setIsFormValid(false);
                  this.setState({ selectedItem: null });
              }}
              onSelect={handleOnSelect}
              onToggle={isOpen => this.setState({ isOpen })}
              onFilter={(_, filter) => this.renderOptions(filter)}
              selections={selectedItem}
              toggleId={idPrefix + "-menu-toggle"}
              validated={selectedItem ? "default" : "error"}
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

export const InstallationLanguage = ({ idPrefix, setIsFormValid, onAddErrorNotification }) => {
    return (
        <AnacondaPage title={_("Welcome to the Anaconda installer")}>
            <TextContent>
                <Text component={TextVariants.p}>{_(
                    "Select the language you would like to use. This language " +
                    "will also be selected for your installed system."
                )}
                </Text>
            </TextContent>
            <Form>
                <FormGroup
                  label={_("Language")}
                  isRequired
                >
                    <LanguageSelector
                      idPrefix={idPrefix}
                      setIsFormValid={setIsFormValid}
                      onAddErrorNotification={onAddErrorNotification}
                    />
                </FormGroup>
            </Form>
        </AnacondaPage>
    );
};
