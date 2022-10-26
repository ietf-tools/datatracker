# Datatracker Diff Tool

This tool facilitates testing 2 different datatracker instances (with their own database) and look for changes using the diff tool. Everything runs in docker containers.

The source instance will use the code from where it is run. The target instance can be a remote tag / branch / commmit or another local folder.

## Requirements

- Node `16.x` or later
- Docker

## Usage

1. From the `dev/diff` directory, run the command:
```sh
npm install
```
2. Then run the command:
```sh
node cli
```
3. Follow the on-screen instructions.
