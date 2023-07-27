// Let us use userChrome.css
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);

// We want to use :has()
user_pref("layout.css.has-selector.enabled", true);

// New windows, not tabs
user_pref("browser.link.open_newwindow", 2);
user_pref("browser.link.open_newwindow.restriction", 1);
user_pref("browser.link.open_newwindow.override.external", 2);

// Dev stuff (for easier UI adusting with ctrl+shift+alt+i)
user_pref("browser.aboutConfig.showWarning", false);
user_pref("devtools.chrome.enabled", true);
user_pref("devtools.debugger.remote-enabled", true);
user_pref("devtools.inspector.showUserAgentStyles", true);

// Don't have any startup page
user_pref("browser.startup.page", 0);
user_pref("browser.startup.homepage", "about:blank");
user_pref("browser.startup.homepage_override.once", {});

// Use a window manager titlebar
user_pref("browser.tabs.inTitlebar", 0);

// Hide the bookmarks
user_pref("browser.toolbars.bookmarks.visibility", "never");

// Don't show anything special in the new tab page'
user_pref("browser.newtabpage.activity-stream.default.sites", "");
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);

// Remove UI stuff
user_pref("browser.uiCustomization.state", "{\"placements\":{\"widget-overflow-fixed-list\":[],\"unified-extensions-area\":[],\"nav-bar\":[\"back-button\",\"forward-button\",\"stop-reload-button\",\"urlbar-container\",\"downloads-button\",\"unified-extensions-button\"],\"toolbar-menubar\":[\"menubar-items\"],\"TabsToolbar\":[\"tabbrowser-tabs\",\"alltabs-button\"],\"PersonalToolbar\":[\"personal-bookmarks\"]},\"seen\":[\"save-to-pocket-button\",\"developer-button\"],\"dirtyAreaCache\":[\"nav-bar\",\"TabsToolbar\",\"toolbar-menubar\",\"PersonalToolbar\"],\"currentVersion\":19,\"newElementCount\":3}");

// Don't set a placeholder for the tab before the page loads and sets title
user_pref("browser.urlbar.placeholderName", "");

// Turn off calling home
user_pref("app.normandy.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.unified", false);
user_pref("trailhead.firstrun.didSeeAboutWelcome", true);

