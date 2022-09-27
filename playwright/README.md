# Playwright
##### Frontend testing automation tool

- [Playwright Website](https://playwright.dev/)
- [Playwright Docs](https://playwright.dev/docs/intro)
- [Playwright API Reference](https://playwright.dev/docs/api/class-test)
- [Online Trace Viewer](https://trace.playwright.dev/)

## Install

Make sure you run all commands from the `/playwright` directory, not the project root.

```
npm install
npx playwright install --with-deps
```

## Usage

Running all tests headless:
```
npm test
```

Running all tests serially in visual mode (headed):
```
npm run test:visual
```

Running all tests in debug mode:
```
npm run test:debug
```

## Advanced Usage

> Refer to the [CLI Reference](https://playwright.dev/docs/test-cli#reference) for all possible options.

Running a single test file:
```
npx playwright test foo.spec.ts
```

Running test files that have `foo` or `bar` in the filename:
```
npx playwright test foo bar
```

Running tests in a specific browser *(e.g. chromium)*:
```
npx playwright test --project=chromium
```

Running tests in headed mode:
```
npx playwright test --headed
```
