#!/usr/bin/env node

import Docker from 'dockerode'
import path from 'path'
import fs from 'fs-extra'
import tar from 'tar'
import yargs from 'yargs/yargs'
import { hideBin } from 'yargs/helpers'
import slugify from 'slugify'
import { nanoid } from 'nanoid'

async function main () {
  const basePath = process.cwd()
  const releasePath = path.join(basePath, 'release')
  const argv = yargs(hideBin(process.argv)).argv

  // Parse branch argument
  let branch = argv.branch
  if (!branch) {
    throw new Error('Missing --branch argument!')
  }
  if (branch.indexOf('/') >= 0) {
    branch = branch.split('/')[1]
  }
  branch = slugify(branch, { lower: true, strict: true })
  if (branch.length < 1) {
    throw new Error('Branch name is empty!')
  }
  console.info(`Will use branch name "${branch}"`)

  // Parse domain argument
  const domain = argv.domain
  if (!domain) {
    throw new Error('Missing --domain argument!')
  }
  const hostname = `dt-${branch}.${domain}`
  console.info(`Will use hostname "${hostname}"`)

  // Connect to Docker Engine API
  console.info('Connecting to Docker Engine API...')
  const dock = new Docker()
  await dock.ping()
  console.info('Connected to Docker Engine API.')

  // Extract release artifact
  console.info('Extracting release artifact...')
  if (!(await fs.pathExists(path.join(basePath, 'release.tar.gz')))) {
    throw new Error('Missing release.tar.gz file!')
  }
  await fs.emptyDir(releasePath)
  await tar.x({
    cwd: releasePath,
    file: 'release.tar.gz'
  })
  console.info('Extracted release artifact successfully.')

  // Update the settings_local.py file
  console.info('Setting configuration files...')
  const settingsPath = path.join(releasePath, 'ietf/settings_local.py')
  const cfgRaw = await fs.readFile(path.join(basePath, 'dev/deploy-to-container/settings_local.py'), 'utf8')
  await fs.outputFile(settingsPath, cfgRaw.replace('__DBHOST__', `dt-db-${branch}`).replace('__SECRETKEY__', nanoid(36)))
  await fs.copy(path.join(basePath, 'docker/scripts/app-create-dirs.sh'), path.join(releasePath, 'app-create-dirs.sh'))
  await fs.copy(path.join(basePath, 'dev/deploy-to-container/start.sh'), path.join(releasePath, 'start.sh'))
  await fs.copy(path.join(basePath, 'test/data'), path.join(releasePath, 'test/data'))
  console.info('Updated configuration files.')

  // Pull latest DB image
  console.info('Pulling latest DB docker image...')
  const dbImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-db:latest')
  await new Promise((resolve, reject) => {
    dock.modem.followProgress(dbImagePullStream, (err, res) => err ? reject(err) : resolve(res))
  })
  console.info('Pulled latest DB docker image successfully.')
  
  // Pull latest Datatracker Base image
  console.info('Pulling latest Datatracker base docker image...')
  const appImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-app-base:latest')
  await new Promise((resolve, reject) => {
    dock.modem.followProgress(appImagePullStream, (err, res) => err ? reject(err) : resolve(res))
  })
  console.info('Pulled latest Datatracker base docker image.')

  // Terminate existing containers
  console.info('Ensuring existing containers with same name are terminated...')
  const containers = await dock.listContainers({ all: true })
  for (const container of containers) {
    if (container.Names.includes(`/dt-db-${branch}`) || container.Names.includes(`/dt-app-${branch}`)) {
      const isDbContainer = container.Names.includes(`/dt-db-${branch}`)
      console.info(`Terminating old container ${container.Id}...`)
      const oldContainer = dock.getContainer(container.Id)
      if (container.State === 'running') {
        await oldContainer.stop({ t: 5 })
      }
      await oldContainer.remove({
        force: true,
        v: isDbContainer
      })
    }
  }
  console.info('Existing containers with same name have been terminated.')

  // Get shared docker network
  console.info('Querying shared docker network...')
  const networks = await dock.listNetworks()
  if (!networks.some(n => n.Name === 'shared')) {
    console.info('No shared docker network found, creating a new one...')
    await dock.createNetwork({
      Name: 'shared',
      CheckDuplicate: true
    })
    console.info('Created shared docker network successfully.')
  } else {
    console.info('Existing shared docker network found.')
  }

  // Create DB container
  console.info(`Creating DB docker container... [dt-db-${branch}]`)
  const dbContainer = await dock.createContainer({
    Image: 'ghcr.io/ietf-tools/datatracker-db:latest',
    name: `dt-db-${branch}`,
    Hostname: `dt-db-${branch}`,
    HostConfig: {
      NetworkMode: 'shared',
      RestartPolicy: {
        Name: 'unless-stopped'
      }
    }
  })
  await dbContainer.start()
  console.info('Created and started DB docker container successfully.')

  // Create Datatracker container
  console.info(`Creating Datatracker docker container... [dt-app-${branch}]`)
  const appContainer = await dock.createContainer({
    Image: 'ghcr.io/ietf-tools/datatracker-app-base:latest',
    name: `dt-app-${branch}`,
    Hostname: `dt-app-${branch}`,
    Env: [
      `LETSENCRYPT_HOST=${hostname}`,
      `VIRTUAL_HOST=${hostname}`,
      `VIRTUAL_PORT=8000`
    ],
    HostConfig: {
      Binds: [
        'dt-assets:/assets'
      ],
      NetworkMode: 'shared',
      RestartPolicy: {
        Name: 'unless-stopped'
      }
    },
    Entrypoint: ['bash', '-c', 'chmod +x ./start.sh && ./start.sh']
  })
  console.info(`Created Datatracker docker container successfully.`)

  // Inject updated release into container
  console.info('Building updated release tarball to inject into container...')
  const tgzPath = path.join(basePath, 'import.tgz')
  await tar.c({
    gzip: true,
    file: tgzPath,
    cwd: releasePath,
    filter (path) {
      if (path.includes('.git') || path.includes('node_modules')) { return false }
      return true
    }
  }, ['.'])
  console.info('Injecting archive into Datatracker docker container...')
  await appContainer.putArchive(tgzPath, {
    path: '/workspace'
  })
  await fs.remove(tgzPath)
  console.info(`Imported working files into Datatracker docker container successfully.`)

  console.info('Starting Datatracker container...')
  await appContainer.start()
  console.info('Datatracker container started successfully.')

  process.exit(0)
}

main()
