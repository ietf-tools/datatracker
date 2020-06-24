module.exports = {
    rules: {
        indent: [2, 4],
        camelcase: 0,
        "require-jsdoc": 0,
        quotes: [2, "double"],
        "no-multiple-empty-lines": [2, {max: 2}],
        "quote-props": [2, "as-needed"],
        "brace-style": [2, "1tbs", {allowSingleLine: true}]
    },
    env: {
        browser: true,
        jquery: true
    },
    globals: {
        d3: true
    },
    extends: "google"
};
