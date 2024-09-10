const path = require("path");
const glob = require("glob");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const { PurgeCSSPlugin } = require('purgecss-webpack-plugin');

const PATHS = {
    templates: path.join(__dirname, "core/templates")
}

module.exports = {
    entry: "./core/static/js/index.js",
    mode: "development",
    devtool: "source-map",
    watch: true,
    output: {
        filename: "main.js",
        library: "lib",
        path: path.resolve(__dirname, "dist"),
    },
    plugins: [
        new MiniCssExtractPlugin(),
        // new PurgeCSSPlugin({
        //     paths: glob.sync(path.resolve(__dirname, "core/**/*.{html,js}"), { nodir: true }),
        //     sourceMap: true,
        //     whitelist: ["message", "self-message", "other-message"],
        //     whitelistPatterns: [/thead/, /tbody/],
        // whitelistPatternsChildren: [/table/],
        // })
    ],

    module: {
        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules/,
                use: ["babel-loader"]
            },
            {
                test: /\.scss$/,
                //they load in reverse order for whatever reason..
                use: [
                    {
                        loader: MiniCssExtractPlugin.loader
                        // loader: "style-loader"
                    },
                    "css-loader",  // 3. turn css into commonJS
                    , {
                        // Run postcss actions
                        loader: "postcss-loader",
                        options: {
                            // `postcssOptions` is needed for postcss 8.x;
                            // if you use postcss 7.x skip the key
                            postcssOptions: {
                                // postcss plugins, can be exported to postcss.config.js
                                plugins: function () {
                                    return [
                                        require("autoprefixer")
                                    ];
                                }
                            }
                        }
                    }
                    , {
                        // 1. compiles Sass to CSS
                        loader: "sass-loader",
                        options: {
                            sassOptions: {
                                quietDeps: true // Suppress deprecation warnings from dependencies
                            }

                        }
                    }]
            },
            {
                test: /\.(woff|woff2|eot|ttf|otf)$/i,
                type: "asset/resource",
            },
            {
                mimetype: "image/svg+xml",
                scheme: "data",
                type: "asset/resource",
                generator: {
                    filename: "icons/[hash].svg"
                }
            },
            {
                test: /\.svg$/,
                use: [
                    {
                        loader: require.resolve("@svgr/webpack"),
                        options: {
                            prettier: false,
                            svgo: false,
                            svgoConfig: {
                                plugins: [{ removeViewBox: false }],
                            },
                            titleProp: true,
                            ref: true,
                        },
                    },
                    {
                        loader: require.resolve("file-loader"),
                        options: {
                            name: "static/media/[name].[hash].[ext]",
                        },
                    },
                ],
                issuer: {
                    and: [/\.(ts|tsx|js|jsx|md|mdx)$/],
                },
            },
        ]
    },
    resolve: {
        alias: {
            "./fonts/bootstrap-icons.woff": path.resolve(__dirname, "./node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff"),
            "./fonts/bootstrap-icons.woff2": path.resolve(__dirname, "./node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff2"),
        }
    },
};
