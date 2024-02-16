#!/usr/bin/env node

import Docker from 'dockerode'

async function main () {
  // Connect to Docker Engine API
  console.info('Connecting to Docker Engine API...')
  const dock = new Docker()
  await dock.ping()
  console.info('Connected to Docker Engine API.')

  // Pull latest DB image
  console.info('Pulling latest DB docker image...')
  const dbImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-db:latest')
  await new Promise((resolve, reject) => {
    dock.modem.followProgress(dbImagePullStream, (err, res) => err ? reject(err) : resolve(res))
  })
  console.info('Pulled latest DB docker image successfully.')

  // Terminate existing containers
  console.info('Terminating DB containers and stopping app containers...')
  const containers = await dock.listContainers({ all: true })
  const dbContainersToCreate = []
  const containersToRestart = []
  for (const container of containers) {
    if (
      container.Names.some(n => n.startsWith('/dt-db-')) &&
      container.Labels?.nodbrefresh !== '1'
      ) {
      console.info(`Terminating DB container ${container.Id}...`)
      dbContainersToCreate.push(container.Names.find(n => n.startsWith('/dt-db-')).substring(1))
      const oldContainer = dock.getContainer(container.Id)
      if (container.State === 'running') {
        await oldContainer.stop({ t: 5 })
      }
      await oldContainer.remove({
        force: true,
        v: true
      })
    } else if (
      (
        container.Names.some(n => n.startsWith('/dt-app-')) ||
        container.Names.some(n => n.startsWith('/dt-celery-')) ||
        container.Names.some(n => n.startsWith('/dt-beat-'))
      ) && container.Labels?.nodbrefresh !== '1'
    ) {
      if (container.State === 'running') {
        const appContainer = dock.getContainer(container.Id)
        containersToRestart.push(appContainer)
        console.info(`Stopping app / celery container ${container.Id}...`)
        await appContainer.stop({ t: 5 })
      }
    }
  }
  console.info('DB containers have been terminated.')

  // Create DB containers
  for (const dbContainerName of dbContainersToCreate) {
    console.info(`Recreating DB docker container... [${dbContainerName}]`)
    const dbContainer = await dock.createContainer({
      Image: 'ghcr.io/ietf-tools/datatracker-db:latest',
      name: dbContainerName,
      Hostname: dbContainerName,
      HostConfig: {
        NetworkMode: 'shared',
        RestartPolicy: {
          Name: 'unless-stopped'
        }
      }
    })
    await dbContainer.start()
  }
  console.info('Recreated and started DB docker containers successfully.')

  console.info('Restarting app / celery containers...')
  for (const appContainer of containersToRestart) {
    await appContainer.start()
  }
  console.info('Done.')

  process.exit(0)
}

main()
