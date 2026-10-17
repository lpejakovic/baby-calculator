// ESLint for static/js. templates/sw.js is a Jinja template, so it is not linted.
const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
    { ignores: ["bc-env/**", ".venv/**", "node_modules/**"] },
    js.configs.recommended,
    {
        files: ["static/js/**/*.js"],
        languageOptions: {
            ecmaVersion: "latest",
            sourceType: "script",
            globals: {
                ...globals.browser,
                module: "readonly", // tests load app.js in QuickJS through module.exports
            },
        },
        rules: {
            "no-unused-vars": ["error", { caughtErrors: "none", ignoreRestSiblings: true }],
            eqeqeq: "error",
            "prefer-const": "error",
            "no-var": "error",
        },
    },
    {
        files: ["eslint.config.js"],
        languageOptions: { sourceType: "commonjs", globals: globals.node },
    },
];
