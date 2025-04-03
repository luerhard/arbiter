const path = require("path");
const glob = require("glob");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const { PurgeCSSPlugin } = require('purgecss-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');

const PATHS = {
    templates: path.join(__dirname, "core/templates")
};

module.exports = (env, argv) => {
    const isProduction = argv.mode === 'production';
    const doWatch = argv.mode === 'watch'

    return {
        entry: "./core/static/js/index.js",
        mode: isProduction ? "production" : "development",
        devtool: isProduction ? false : "source-map",
        watch: doWatch,
        output: {
            filename: "main.js",
            library: "lib",
            path: path.resolve(__dirname, "dist"),
        },
        plugins: [
            // new CleanWebpackPlugin(),
            new MiniCssExtractPlugin({
                filename: isProduction ? '[name].[contenthash].css' : '[name].css',
            }),
            // new PurgeCSSPlugin({
            //     paths: glob.sync(path.resolve(__dirname, "core/**/*.{html,js}"), { nodir: true }),
            //     safelist: ["message", "self-message", "other-message"],
            //     safelistPatterns: [/thead/, /tbody/],
            //     safelistPatternsChildren: [/table/],
            // }),
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
                    use: [
                        {
                            loader: MiniCssExtractPlugin.loader,
                        },
                        "css-loader",
                        {
                            loader: "postcss-loader",
                            options: {
                                postcssOptions: {
                                    plugins: [
                                        require("autoprefixer")
                                    ],
                                },
                            },
                        },
                        {
                            loader: "sass-loader",
                            options: {
                                sassOptions: {
                                    quietDeps: true
                                }
                            }
                        }
                    ]
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
        optimization: {
            minimize: isProduction,
            minimizer: [
                new TerserPlugin({
                    terserOptions: {
                        compress: {
                            drop_console: true,
                        },
                    },
                }),
                new CssMinimizerPlugin(),
            ],
        },
        resolve: {
            alias: {
                "./fonts/bootstrap-icons.woff": path.resolve(__dirname, "./node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff"),
                "./fonts/bootstrap-icons.woff2": path.resolve(__dirname, "./node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff2"),
            }
        },
    };
};
