# Datatracker Deploy to Container Tool

This tool takes a release.tar.gz build file and deploys it as a container, along with its own database container.

## Requirements

- Node `16.x` or later
- Docker

## Usage

1. From the `dev/deploy-to-container` directory, run the command:
```sh
npm install
```
2. Make sure you have a `release.tar.gz` tarball in the project root directory.
3. From the project root directory (back up 2 levels), run the command: (replacing the `branch` and `domain` arguments)
```sh
node ./dev/deploy-to-container/cli.js --branch main --domain something.com
```

A container named `dt-app-BRANCH` and `dt-db-BRANCH` (where BRANCH is the argument provided above) will be created.
