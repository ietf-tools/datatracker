#!/usr/bin/env node

import Docker from 'dockerode'
import inquirer from 'inquirer'
import ora from 'ora'
import chalk from 'chalk'
import path from 'path'
import os from 'os'
import fs from 'fs-extra'
import got from 'got'
import { pipeline } from 'stream/promises'
import prettyBytes from 'pretty-bytes'
import extract from 'extract-zip'
import tar from 'tar'
import { kebabCase } from 'lodash-es'

const cliStatus = {}
const config = {
  source: {
    path: process.cwd(),
    port: 8081
  },
  target: {
    path: null,
    port: 8080
  }
}

/**
 * Prompt the user for a path
 * 
 * @param {String} msg Prompt message
 * @param {Boolean} mustExist Whether the path must already exist
 * @returns path
 */
async function promptForPath (msg, mustExist = true) {
  const localPathPrompt = await inquirer.prompt([
    {
      type: 'input',
      name: 'path',
      message: msg,
      async validate (input) {
        if (!input) {
          return 'You must provide a valid path!'
        }
        const proposedPath = path.resolve('.', input)
        if (proposedPath.includes(config.source.path)) {
          return 'Path must be different than the current datatracker project path!'
        } else if (mustExist && !(await fs.pathExists(proposedPath))) {
          return 'Path is invalid or doesn\'t exist!'
        } else {
          return true
        }
      }
    }
  ])
  return localPathPrompt.path
}

/**
 * Download and Extract a zip archive
 * 
 * @param {Object} param0 Options
 */
async function downloadExtractZip ({ msg, url, ext = 'zip', branch }) {
  const archivePath = path.join(config.target.path, `archive.${ext}`)
  await fs.emptyDir(config.target.path)
  // Download zip
  try {
    cliStatus.downloadZip = ora(msg).start()
    const downloadBranchStream = got.stream(url)
    downloadBranchStream.on('downloadProgress', progress => {
      cliStatus.downloadZip.text = `${msg} ${prettyBytes(progress.transferred)}`
    })
    await pipeline(
      downloadBranchStream,
      fs.createWriteStream(archivePath)
    )
    cliStatus.downloadZip.succeed(`Downloaded ${ext} archive successfully.`)
  } catch (err) {
    cliStatus.downloadZip.fail(`Failed to download ${ext} archive from GitHub.`)
    console.error(chalk.redBright(err.message))
    process.exit(1)
  }

  // Extract zip
  try {
    cliStatus.extractZip = ora(`Extracting ${ext} archive contents...`).start()
    if (ext === 'zip') {
      const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'dt-'))
      await fs.ensureDir(tmpDir)
      await extract(archivePath, {
        dir: tmpDir,
        onEntry (entry) {
          cliStatus.extractZip.text = `Extracting ${ext} archive contents... ${entry.fileName}`
        }
      })
      cliStatus.extractZip.text = 'Moving extracted files to final location...'
      await fs.move(path.join(tmpDir, kebabCase(`datatracker-${branch}`)), config.target.path, { overwrite: true })
      await fs.remove(tmpDir)
    } else if (ext === 'tgz') {
      await tar.x({
        strip: 1,
        file: archivePath,
        cwd: config.target.path,
        filter (path) {
          cliStatus.extractZip.text = `Extracting ${ext} archive contents... ${path}`
          return true
        }
      })
    }
    cliStatus.extractZip.succeed(`Extracted ${ext} archive successfully.`)
    await fs.remove(archivePath)
  } catch (err) {
    cliStatus.extractZip.fail(`Failed to extract ${ext} archive contents.`)
    console.error(chalk.redBright(err.message))
    process.exit(1)
  }
}

async function main () {
  console.clear()
  console.info('╔════════════════════════════╗')
  console.info('║ IETF DATATRACKER DIFF TOOL ║')
  console.info('╚════════════════════════════╝\n')

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
  try {
    cliStatus.findBasePath = ora('Finding base datatracker instance base path...').start()
    let parentIdx = 0
    while(!(await fs.pathExists(path.join(config.source.path, 'requirements.txt')))) {
      config.source.path = path.resolve(config.source.path, '..')
      parentIdx++
      if (parentIdx > 2) {
        throw new Error('Start the CLI from a valid datatracker project path.')
      }
    }
    cliStatus.findBasePath.info(`Using path ${config.source.path} for base datatracker instance. [SOURCE]`)
  } catch (err) {
    cliStatus.dockerConnect.fail('Could not find base path of the datatracker project!')
    console.error(chalk.redBright(err.message))
    return process.exit(1)
  }

  // Select comparison datatracker instance
  const compareAgainstPrompt = await inquirer.prompt([
    {
      type: 'list',
      name: 'ans',
      message: 'What do you want to compare against?',
      choices: [
        { value: 'local', name: 'Local path...' },
        { value: 'remote', name: 'Remote GitHub branch...' },
        { value: 'release', name: 'Latest release' },
      ]
    }
  ])
  switch (compareAgainstPrompt.ans) {
    // MODE: LOCAL
    case 'local': {
      config.target.path = await promptForPath('Enter the path to the datatracker project to compare against:')
      break
    }
    // MODE: REMOTE BRANCH
    case 'remote': {
      // Prompt for branch
      const branches = []
      let branch = 'main'
      try {
        cliStatus.fetchBranches = ora('Fetching available remote branches...').start()
        const branchesResp = await got('https://api.github.com/repos/ietf-tools/datatracker/branches').json()
        if (branchesResp?.length < 1) {
          throw new Error('No remote branches available.')
        }
        branches.push(...branchesResp.map(b => b.name))
        cliStatus.fetchBranches.succeed(`Fetched ${branches.length} remote branches.`)
      } catch (err) {
        cliStatus.fetchBranches.fail('Failed to fetch branches!')
        console.error(chalk.redBright(err.message))
        return process.exit(1)
      }
      
      const remoteBranchPrompt = await inquirer.prompt([
        {
          type: 'list',
          name: 'branch',
          message: 'Select the remote branch to compare against:',
          choices: branches
        }
      ])
      branch = remoteBranchPrompt.branch

      // Prompt for local path where to download branch contents
      config.target.path = await promptForPath('Enter a local path where the branch contents will be downloaded to:', false)
      await fs.ensureDir(config.target.path)

      // Download / Extract branch zip
      await downloadExtractZip({
        msg: `Downloading ${remoteBranchPrompt.branch} branch contents...`,
        url: `https://github.com/ietf-tools/datatracker/archive/refs/heads/${branch}.zip`,
        ext: 'zip',
        branch
      })
      break
    }
    // MODE: LATEST RELEASE
    case 'release': {
      // Prompt for local path where to download release
      config.target.path = await promptForPath('Enter a local path where the latest release will be downloaded to:', false)
      await fs.ensureDir(config.target.path)

      // Download / extract latest release
      await downloadExtractZip({
        msg: 'Downloading latest release...',
        url: 'https://github.com/ietf-tools/datatracker/releases/latest/download/release.tar.gz',
        ext: 'tgz'
      })
      break
    }
    default: {
      console.error(chalk.redBright('Invalid selection. Exiting...'))
      return process.exit(1)
    }
  }


  // const containers = await dock.listContainers()
  // console.info(containers)
}

main()
