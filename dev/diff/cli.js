#!/usr/bin/env node

import Docker from 'dockerode'
import inquirer from 'inquirer'
import ora from 'ora'
import chalk from 'chalk'
import path from 'path'
import fs from 'fs-extra'

async function main () {
  console.clear()
  console.info('╔════════════════════════════╗')
  console.info('║ IETF DATATRACKER DIFF TOOL ║')
  console.info('╚════════════════════════════╝\n')

  const cliStatus = {}

  // Connect to Docker Engine API
  let dock = null
  try {
    cliStatus.dockerConnect = ora('Connecting to Docker Engine API...').start()
    dock = new Docker()
    await dock.ping()
    cliStatus.dockerConnect.succeed('Connected to Docker Engine API.')
  } catch (err) {
    cliStatus.dockerConnect.fail('Failed to connect to Docker Engine API!')
    console.error(chalk.redBright(err.message))
    return process.exit(1)
  }

  // Find base path so that it works from both / and /dev/diff paths
  let basepath = process.cwd()
  try {
    cliStatus.findBasePath = ora('Finding base datatracker instance base path...').start()
    let parentIdx = 0
    while(!(await fs.pathExists(path.join(basepath, 'requirements.txt')))) {
      basepath = path.resolve(basepath, '..')
      parentIdx++
      if (parentIdx > 2) {
        throw new Error('Start the CLI from a valid datatracker project path.')
      }
    }
    cliStatus.findBasePath.info(`Using path ${basepath} for base datatracker instance. [SOURCE]`)
  } catch (err) {
    cliStatus.dockerConnect.fail('Could not find base path of the datatracker project!')
    console.error(chalk.redBright(err.message))
    return process.exit(1)
  }

  // Select comparison datatracker instance
  let compareAgainstPrompt = await inquirer.prompt([
    {
      type: 'list',
      name: 'ans',
      message: 'What do you want to compare against?',
      choices: [
        { value: 'local', name: 'Local path' },
        { value: 'remote', name: 'Remote GitHub branch...' },
        { value: 'release', name: 'Latest release' },
      ]
    }
  ])

  // const containers = await dock.listContainers()
  // console.info(containers)
}

main()
