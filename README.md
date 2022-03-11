<div align="center">
  
<img src="https://raw.githubusercontent.com/ietf-tools/common/main/assets/logos/datatracker.svg" alt="IETF Datatracker" height="125" />

[![Release](https://img.shields.io/github/release/ietf-tools/datatracker.svg?style=flat&maxAge=300)](https://github.com/ietf-tools/datatracker/releases)
[![License](https://img.shields.io/github/license/ietf-tools/datatracker)](https://github.com/ietf-tools/datatracker/blob/main/LICENSE)
[![Nightly Dev DB Image](https://github.com/ietf-tools/datatracker/actions/workflows/dev-db-nightly.yml/badge.svg)](https://github.com/ietf-tools/datatracker/pkgs/container/datatracker-db)  
[![Python Version](https://img.shields.io/badge/python-3.6-blue?logo=python&logoColor=white)](#prerequisites)
[![Django Version](https://img.shields.io/badge/django-2.x-51be95?logo=django&logoColor=white)](#prerequisites)
[![Node Version](https://img.shields.io/badge/node.js-16.x-green?logo=node.js&logoColor=white)](#prerequisites)
[![MariaDB Version](https://img.shields.io/badge/mariadb-10-blue?logo=mariadb&logoColor=white)](#prerequisites)

##### The day-to-day front-end to the IETF database for people who work on IETF standards.

</div>

- [**Production Website**](https://datatracker.ietf.org)
- [Changelog](https://github.com/ietf-tools/datatracker/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md)
- [Getting Started](#getting-started)
    - [Git Cloning Tips](#git-cloning-tips)
    - [Docker Dev Environment](docker/README.md)
- [Database & Assets](#database--assets)
- [Old Datatracker Branches](https://github.com/ietf-tools/old-datatracker-branches/branches/all)

---

### Getting Started

This project is following the standard **Git Feature Workflow** development model. Learn about all the various steps of the development workflow, from creating a fork to submitting a pull request, in the [Contributing](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md) guide.

> Make sure to read the [Styleguides](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md#styleguides) section to ensure a cohesive code format across the project.

You can submit bug reports, enhancement and new feature requests in the [discussions](https://github.com/ietf-tools/datatracker/discussions) area. Accepted tickets will be converted to issues.

#### Git Cloning Tips

As outlined in the [Contributing](https://github.com/ietf-tools/.github/blob/main/CONTRIBUTING.md) guide, you will first want to create a fork of the datatracker project in your personal GitHub account before cloning it.

Because of the extensive history of this project, cloning the datatracker project locally can take a long time / disk space. You can speed up the cloning process by limiting the history depth, for example:

- To fetch only up to the 10 latest commits:
    ```sh
    git clone --depth=10 https://github.com/jdoe/datatracker.git
    ```
- To fetch only up to a specific date:
    ```sh
    git clone --shallow-since=DATE https://github.com/jdoe/datatracker.git
    ```

But substitute your GitHub username in place of *jdoe*.

#### Overview of the datatracker models

A beginning of a [walkthrough of the datatracker models](https://notes.ietf.org/iab-aid-datatracker-database-overview) was prepared for the IAB AID workshop.

#### Docker Dev Environment

In order to simplify and reduce the time required for setup, a preconfigured docker environment is available.

Read the [Docker Dev Environment](docker/README.md) guide to get started.

### Database & Assets

Nightly database dumps of the datatracker are available at  
https://www.ietf.org/lib/dt/sprint/ietf_utf8.sql.gz

> Note that this link is provided as reference only. To update the database in your dev environment to the latest version, you should instead run the `docker/cleandb` script!

