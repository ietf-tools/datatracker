# Datatracker Get Deploy Name

This tool process and slugify a git branch into an appropriate subdomain name.

## Usage

1. From the `dev/k8s-get-deploy-name` directory, install the dependencies:
```sh
npm install
```
2. Run the command: (replacing the `branch` argument)
```sh
node /cli.js --branch feat/fooBar-123
```

The subdomain name will be output. It can then be used in a workflow as a namespace name and subdomain value.
