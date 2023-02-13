## Tool to delete old versions in GitHub Packages container registry

This tool will fetch all versions for packages `datatracker-db` and `datatracker-db-pg` and delete all versions that are not latest and older than 7 days.

### Requirements

- Node 18.x or later
- Must provide a valid token in ENV variable `GITHUB_TOKEN` with read and delete packages permissions.

### Usage

```sh
npm install
node index
```