import fs from "fs";
import crypto from "crypto";

import copy from "copy-webpack-plugin";
import extract from "mini-css-extract-plugin";
import TerserJSPlugin from 'terser-webpack-plugin';
import CssMinimizerPlugin from 'css-minimizer-webpack-plugin';
import CompressionPlugin from "compression-webpack-plugin";
import ESLintPlugin from 'eslint-webpack-plugin';

import { CockpitPoWebpackPlugin } from "./pkg/lib/cockpit-po-plugin.js";
import { CockpitRsyncWebpackPlugin } from "./pkg/lib/cockpit-rsync-plugin.js";

// HACK: OpenSSL 3 does not support md4 any more, but webpack hardcodes it all over the place: https://github.com/webpack/webpack/issues/13572
const crypto_orig_createHash = crypto.createHash;
crypto.createHash = algorithm => crypto_orig_createHash(algorithm == "md4" ? "sha256" : algorithm);

// Obtain package name from package.json
const packageJson = JSON.parse(fs.readFileSync('package.json'));

/* A standard nodejs and webpack pattern */
const production = process.env.NODE_ENV === 'production';

/* Default to disable eslint for faster production builds */
const eslint = process.env.ESLINT ? (process.env.ESLINT !== '0') : !production;

// Non-JS files which are copied verbatim to dist/
const copy_files = [
    "./src/index.html",
    "./src/manifest.json",
];

const plugins = [
    new copy({ patterns: copy_files }),
    new extract({filename: "[name].css"}),
    new CockpitPoWebpackPlugin({ src_directory: "ui/webui/src/" }),
    new CockpitRsyncWebpackPlugin({ dest: packageJson.name }),
];

if (eslint) {
    plugins.push(new ESLintPlugin({ extensions: ["js", "jsx"] }));
}

/* Only minimize when in production mode */
if (production) {
    plugins.unshift(new CompressionPlugin({
        test: /\.(js|html|css)$/,
        deleteOriginalAssets: true,
        // Compress all assets
        minRatio: Infinity
    }));
}

const config = {
    mode: production ? 'production' : 'development',
    resolve: {
        modules: [ "node_modules", "pkg/lib" ],
        alias: { 'font-awesome': 'font-awesome-sass/assets/stylesheets' },
    },
    resolveLoader: {
        modules: [ "node_modules", "pkg/lib" ],
    },
    watchOptions: {
        ignored: /node_modules/,
    },
    entry: {
        index: "./src/index.js",
    },
    // cockpit.js gets included via <script>, everything else should be bundled
    externals: { "cockpit": "cockpit" },
    devtool: "source-map",
    stats: "errors-warnings",

    optimization: {
        minimize: production,
        minimizer: [
            new TerserJSPlugin({
                extractComments: {
                    condition: true,
                    filename: `[file].LICENSE.txt?query=[query]&filebase=[base]`,
                    banner(licenseFile) {
                        return `License information can be found in ${licenseFile}`;
                    },
                },
            }),
            new CssMinimizerPlugin()
        ],
    },

    module: {
        rules: [
            {
                exclude: /node_modules/,
                use: "babel-loader",
                test: /\.(js|jsx)$/
            },
            /* HACK: remove unwanted fonts from PatternFly's css */
            {
                test: /patternfly-4-cockpit.scss$/,
                use: [
                    extract.loader,
                    {
                        loader: 'css-loader',
                        options: {
                            sourceMap: true,
                            url: false,
                        },
                    },
                    {
                        loader: 'string-replace-loader',
                        options: {
                            multiple: [
                                {
                                    search: /src:url\("patternfly-icons-fake-path\/pficon[^}]*/g,
                                    replace: 'src:url("../base1/fonts/patternfly.woff") format("woff");',
                                },
                                {
                                    search: /@font-face[^}]*patternfly-fonts-fake-path[^}]*}/g,
                                    replace: '',
                                },
                            ]
                        },
                    },
                    {
                        loader: 'sass-loader',
                        options: {
                            sourceMap: !production,
                            sassOptions: {
                                outputStyle: production ? 'compressed' : undefined,
                            },
                        },
                    },
                ]
            },
            {
                test: /\.s?css$/,
                exclude: /patternfly-4-cockpit.scss/,
                use: [
                    extract.loader,
                    {
                        loader: 'css-loader',
                        options: {
                            sourceMap: true,
                            url: false
                        }
                    },
                    {
                        loader: 'sass-loader',
                        options: {
                            sourceMap: !production,
                            sassOptions: {
                                outputStyle: production ? 'compressed' : undefined,
                            },
                        },
                    },
                ]
            },
        ]
    },
    plugins: plugins
};

export default config;
