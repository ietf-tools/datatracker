#!/usr/bin/env node

import Docker from 'dockerode'
import ora from 'ora'
import chalk from 'chalk'
import path from 'path'
import os from 'os'
import fs from 'fs-extra'
import got from 'got'
import { pipeline } from 'stream/promises'
import { PassThrough } from 'stream'
import prettyBytes from 'pretty-bytes'
import extract from 'extract-zip'
import tar from 'tar'
import { kebabCase } from 'lodash-es'
import { Listr } from 'listr2'

let dock = null
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
const containers = {
  net: null,
  dbSource: null,
  dbTarget: null,
  appSource: null,
  appTarget: null
}

/**
 * Prompt the user for a path
 * 
 * @param {Task} task Listr task instance
 * @param {String} msg Prompt message
 * @param {Boolean} mustExist Whether the path must already exist
 * @returns path
 */
async function promptForPath (task, msg, mustExist = true) {
  return task.prompt([
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
}

/**
 * Download and Extract a zip archive
 * 
 * @param {Task} task Listr task instance
 * @param {Object} param1 Options
 */
async function downloadExtractZip (task, { msg, url, ext = 'zip', branch }) {
  const archivePath = path.join(config.target.path, `archive.${ext}`)
  await fs.emptyDir(config.target.path)
  // Download zip
  try {
    task.title = msg
    const downloadBranchStream = got.stream(url)
    downloadBranchStream.on('downloadProgress', progress => {
      task.output = `${prettyBytes(progress.transferred)} downloaded.`
    })
    await pipeline(
      downloadBranchStream,
      fs.createWriteStream(archivePath)
    )
    task.title = `Downloaded ${ext} archive successfully.`
  } catch (err) {
    throw new Error(`Failed to download ${ext} archive from GitHub. ${err.message}`)
  }

  // Extract zip
  try {
    task.title = `Extracting ${ext} archive contents...`
    if (ext === 'zip') {
      const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'dt-'))
      await fs.ensureDir(tmpDir)
      await extract(archivePath, {
        dir: tmpDir,
        onEntry (entry) {
          task.output = entry.fileName
        }
      })
      task.title = 'Moving extracted files to final location...'
      task.output = config.target.path
      await fs.move(path.join(tmpDir, kebabCase(`datatracker-${branch}`)), config.target.path, { overwrite: true })
      await fs.remove(tmpDir)
    } else if (ext === 'tgz') {
      await tar.x({
        strip: 1,
        file: archivePath,
        cwd: config.target.path,
        filter (path) {
          task.output = path
          return true
        }
      })
    }
    task.title = `Extracted ${ext} archive successfully.`
    await fs.remove(archivePath)
  } catch (err) {
    throw new Error(`Failed to extract ${ext} archive contents. ${err.message}`)
  }
}

/**
 * Run a command on a running container
 * 
 * @param {Task} task Listr task instance
 * @param {Docker.Container} container Docker container instance
 * @param {Array<String>} cmd Command to execute
 * @param {Boolean} collectOutput Whether to collect and return the command output
 */
async function executeCommand (task, container, cmd, collectOutput = false) {
  const logStack = []
  const errStack = []
  await new Promise(async (resolve, reject) => {
    const logStream = new PassThrough()
    logStream.on('data', chunk => {
      task.output = chunk.toString('utf8')
      if (collectOutput) {
        logStack.push(chunk.toString('utf8'))
      }
    })
    logStream.on('error', chunk => {
      task.output = chunk.toString('utf8')
      errStack.push(chunk.toString('utf8'))
    })
    const execChmod = await container.exec({
      Cmd: cmd,
      AttachStdout: true,
      AttachStderr: true
    })
    const execChmodStream = await execChmod.start()
    execChmodStream.on('close', () => {
      if (errStack.length > 0) {
        reject(errStack)
      } else {
        resolve()
      }
    })
    container.modem.demuxStream(execChmodStream, logStream, logStream)
  })
}

async function main () {
  console.clear()
  console.info('╔════════════════════════════╗')
  console.info('║ IETF DATATRACKER DIFF TOOL ║')
  console.info('╚════════════════════════════╝\n')

  try {
    const tasks = new Listr([
      // ----------------------------
      // Connect to Docker Engine API
      // ----------------------------
      {
        title: 'Connect to Docker Engine API',
        task: async (ctx, task) => {
          dock = new Docker()
          await dock.ping()
          task.title = 'Connected to Docker Engine API.'
        }
      },
      // ---------------------------------------------------------------
      // Find base path so that it works from both / and /dev/diff paths
      // ---------------------------------------------------------------
      {
        title: 'Find base datatracker instance base path',
        task: async (ctx, task) => {
          let parentIdx = 0
          while(!(await fs.pathExists(path.join(config.source.path, 'requirements.txt')))) {
            config.source.path = path.resolve(config.source.path, '..')
            parentIdx++
            if (parentIdx > 2) {
              throw new Error('Start the CLI from a valid datatracker project path.')
            }
          }
          task.title = `Using path ${config.source.path} for source datatracker instance.`
        }
      },
      // --------------------------------------
      // Select comparison datatracker instance
      // --------------------------------------
      {
        title: 'Select diff target',
        task: async (ctx, task) => {
          ctx.targetMode = await task.prompt({
            type: 'select',
            message: 'What do you want to compare against?',
            choices: [
              { name: 'local', message: 'Local folder path...' },
              { name: 'remote', message: 'Remote GitHub branch...' },
              { name: 'release', message: 'Latest release' }
            ]
          })
          task.title = `Selected diff target: ${ctx.targetMode}`
        }
      },
      // ---------------------------------
      // Fetch target datatracker instance
      // ---------------------------------
      {
        title: 'Fetch diff target',
        task: async (ctx, task) => {
          switch (ctx.targetMode) {
            // MODE: LOCAL
            case 'local': {
              task.title = 'Waiting for diff target path input'
              config.target.path = await promptForPath(task, 'Enter the path to the datatracker project to compare against:')
              task.title = `Using path ${config.target.path} for target datatracker instance.`
              break
            }
            // MODE: REMOTE BRANCH
            case 'remote': {
              // Prompt for branch
              const branches = []
              let branch = 'main'
              try {
                task.title = 'Fetching available remote branches...'
                const branchesResp = await got('https://api.github.com/repos/ietf-tools/datatracker/branches').json()
                if (branchesResp?.length < 1) {
                  throw new Error('No remote branches available.')
                }
                branches.push(...branchesResp.map(b => b.name))
                task.output = `Fetched ${branches.length} remote branches.`
              } catch (err) {
                throw new Error(`Failed to fetch branches! ${err.message}`)
              }
              
              branch = await task.prompt([
                {
                  type: 'select',
                  message: 'Select the remote branch to compare against:',
                  choices: branches
                }
              ])
        
              // Prompt for local path where to download branch contents
              config.target.path = await promptForPath(task, 'Enter a local path where the branch contents will be downloaded to:', false)
              await fs.ensureDir(config.target.path)
        
              // Download / Extract branch zip
              await downloadExtractZip(task, {
                msg: `Downloading ${branch} branch contents...`,
                url: `https://github.com/ietf-tools/datatracker/archive/refs/heads/${branch}.zip`,
                ext: 'zip',
                branch
              })

              task.title = `Fetched branch ${branch} to ${config.target.path}`
              break
            }
            // MODE: LATEST RELEASE
            case 'release': {
              task.title = 'Waiting for diff target download location'
              // Prompt for local path where to download release
              config.target.path = await promptForPath(task, 'Enter a local path where the latest release will be downloaded to:', false)
              await fs.ensureDir(config.target.path)
        
              // Download / extract latest release
              await downloadExtractZip(task, {
                msg: 'Downloading latest release...',
                url: 'https://github.com/ietf-tools/datatracker/releases/latest/download/release.tar.gz',
                ext: 'tgz'
              })

              // Add missing files not present in release tarball
              task.title = `Add missing diff tool files...`
              await fs.ensureDir(path.join(config.target.path, 'dev/diff'))
              await fs.copy(path.join(config.source.path, 'dev/diff/prepare.sh'), path.join(config.target.path, 'dev/diff/prepare.sh'))
              await fs.copy(path.join(config.source.path, 'dev/diff/settings_local.py'), path.join(config.target.path, 'dev/diff/settings_local.py'))

              task.title = `Fetched latest release to ${config.target.path}`
              break
            }
            default: {
              throw new Error('Invalid selection. Exiting...')
            }
          }
        }
      },
      // ----------------------------
      // Set datatracker config files
      // ----------------------------
      {
        title: 'Set datatracker config files',
        task: async (ctx, task) => {
          // Source
          const sourceSettingsPath = path.join(config.source.path, 'ietf/settings_local.py')
          if (await fs.pathExists(sourceSettingsPath)) {
            await fs.move(sourceSettingsPath, `${sourceSettingsPath}.bak`, { overwrite: true })
          }
          const cfgSourceRaw = await fs.readFile(path.join(config.source.path, 'dev/diff/settings_local.py'), 'utf8')
          await fs.outputFile(sourceSettingsPath, cfgSourceRaw.replace('__DBHOST__', 'dt-diff-db-source'))
          // Target
          const targetSettingsPath = path.join(config.target.path, 'ietf/settings_local.py')
          if (await fs.pathExists(targetSettingsPath)) {
            await fs.move(targetSettingsPath, `${targetSettingsPath}.bak`, { overwrite: true })
          }
          const cfgTargetRaw = await fs.readFile(path.join(config.target.path, 'dev/diff/settings_local.py'), 'utf8')
          await fs.outputFile(targetSettingsPath, cfgTargetRaw.replace('__DBHOST__', 'dt-diff-db-target'))
        }
      },
      // ------------------
      // Pull latest images
      // ------------------
      {
        title: 'Pull latest docker images',
        task: (ctx, task) => task.newListr([
          {
            title: 'Pull latest DB docker image...',
            task: async (subctx, subtask) => {
              const dbImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-db:latest')
              await new Promise((resolve, reject) => {
                dock.modem.followProgress(dbImagePullStream, (err, res) => err ? reject(err) : resolve(res))
              })
              subtask.title = `Pulled latest DB docker image successfully.`
            }
          },
          {
            title: 'Pull latest Datatracker base docker image...',
            task: async (subctx, subtask) => {
              const appImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-app-base:latest')
              await new Promise((resolve, reject) => {
                dock.modem.followProgress(appImagePullStream, (err, res) => err ? reject(err) : resolve(res))
              })
              subtask.title = `Pulled latest Datatracker base docker image successfully.`
            }
          }
        ], {
          concurrent: true,
          rendererOptions: {
            collapse: false
          }
        })
      },
      // --------------
      // Create network
      // --------------
      {
        title: 'Create docker network',
        task: async (ctx, task) => {
          containers.net = await dock.createNetwork({
            Name: 'dt-diff-net',
            CheckDuplicate: true
          })
          task.title = 'Created docker network (dt-diff-net).'
        }
      },
      // ----------------------------
      // Create + Start DB containers
      // ----------------------------
      {
        title: 'Create DB docker containers',
        task: (ctx, task) => task.newListr([
          {
            title: 'Creating source DB docker container...',
            task: async (subctx, subtask) => {
              containers.dbSource = await dock.createContainer({
                Image: 'ghcr.io/ietf-tools/datatracker-db:latest',
                name: 'dt-diff-db-source',
                Hostname: 'dbsource',
                HostConfig: {
                  NetworkMode: 'dt-diff-net'
                }
              })
              await containers.dbSource.start()
              subtask.title = `Created source DB docker container (dt-diff-db-source) successfully.`
            }
          },
          {
            title: 'Creating target DB docker container...',
            task: async (subctx, subtask) => {
              containers.dbTarget = await dock.createContainer({
                Image: 'ghcr.io/ietf-tools/datatracker-db:latest',
                name: 'dt-diff-db-target',
                Hostname: 'dbtarget',
                HostConfig: {
                  NetworkMode: 'dt-diff-net'
                }
              })
              await containers.dbTarget.start()
              subtask.title = `Created target DB docker container (dt-diff-db-target) successfully.`
            }
          }
        ], {
          concurrent: true,
          rendererOptions: {
            collapse: false
          }
        })
      },
      // -------------------------------------
      // Create + Start Datatracker containers
      // -------------------------------------
      {
        title: 'Create Datatracker docker containers',
        task: (ctx, task) => task.newListr([
          {
            title: 'Creating source Datatracker docker container...',
            task: async (subctx, subtask) => {
              containers.appSource = await dock.createContainer({
                Image: 'ghcr.io/ietf-tools/datatracker-app-base:latest',
                name: 'dt-diff-app-source',
                Tty: true,
                Hostname: 'appsource',
                HostConfig: {
                  Binds: [
                    `${config.source.path}:/workspace`
                  ],
                  NetworkMode: 'dt-diff-net'
                }
              })
              await containers.appSource.start()
              subtask.title = `Created source Datatracker docker container (dt-diff-app-source) successfully.`
            }
          },
          {
            title: 'Creating target Datatracker docker container...',
            task: async (subctx, subtask) => {
              containers.appTarget = await dock.createContainer({
                Image: 'ghcr.io/ietf-tools/datatracker-app-base:latest',
                name: 'dt-diff-app-target',
                Tty: true,
                Hostname: 'apptarget',
                HostConfig: {
                  Binds: [
                    `${config.target.path}:/workspace`
                  ],
                  NetworkMode: 'dt-diff-net'
                }
              })
              await containers.appTarget.start()
              subtask.title = `Created target Datatracker docker container (dt-diff-app-target) successfully.`
            }
          }
        ], {
          concurrent: true,
          rendererOptions: {
            collapse: false
          }
        })
      },
      // -------------------
      // Run prepare scripts
      // -------------------
      {
        title: 'Prepare Datatracker instances',
        task: (ctx, task) => task.newListr([
          {
            title: 'Preparing source Datatracker instance...',
            task: async (subctx, subtask) => {
              await executeCommand (subtask, containers.appSource, ['bash', '-c', 'chmod +x ./dev/diff/prepare.sh'])
              await executeCommand (subtask, containers.appSource, ['bash', './dev/diff/prepare.sh'])
              subtask.title = `Source Datatracker instance is now ready.`
            }
          },
          {
            title: 'Preparing target Datatracker instance...',
            task: async (subctx, subtask) => {
              await executeCommand (subtask, containers.appTarget, ['bash', '-c', 'chmod +x ./dev/diff/prepare.sh'])
              await executeCommand (subtask, containers.appTarget, ['bash', './dev/diff/prepare.sh'])
              subtask.title = `Target Datatracker instance is now ready.`
            }
          }
        ], {
          concurrent: true,
          rendererOptions: {
            collapse: false
          }
        })
      },
      // ----------------------
      // Run target datatracker
      // ----------------------
      {
        title: 'Run target Datatracker instance',
        task: async (ctx, task) => {
          task.title = `Run target Datatracker instance - Applying migrations...`
          await executeCommand (task, containers.appTarget, ['./ietf/manage.py', 'check'])
          task.title = `Run target Datatracker instance - Applying migrations...`
          await executeCommand (task, containers.appTarget, ['./ietf/manage.py', 'migrate'])
          task.title = `Run target Datatracker instance - Starting server...`
          executeCommand (task, containers.appTarget, ['./ietf/manage.py', 'runserver', '0.0.0.0:8000', '--settings=settings_local'])
          task.title = `Run target Datatracker instance - Waiting for server to accept connections...`
          await executeCommand (task, containers.appSource, ['/usr/local/bin/wait-for', 'localhost:8000', '-t', '120'])
          task.title = `Target Datatracker instance is running and accepting connections.`
        },
        options: {
          bottomBar: Infinity,
          persistentOutput: true
        }
      }
    ])

    await tasks.run()

  } catch (err) {
    console.error(chalk.redBright(err.message))
  }

  // ------------------------
  // Stop + Remove Containers
  // ------------------------
  const cliStatus = ora('Stopping containers...').start()
  try {
    await Promise.allSettled([
      containers.dbSource && containers.dbSource.stop(),
      containers.dbTarget && containers.dbTarget.stop(),
      containers.appSource && containers.appSource.stop(),
      containers.appTarget && containers.appTarget.stop()
    ])
  } catch (err) { }
  cliStatus.text = 'Removing resources...'
  try {
    await Promise.allSettled([
      containers.dbSource && containers.dbSource.remove(),
      containers.dbTarget && containers.dbTarget.remove(),
      containers.appSource && containers.appSource.remove(),
      containers.appTarget && containers.appTarget.remove()
    ])
  } catch (err) { }
  cliStatus.text = 'Removing network...'
  try {
    await containers.net.remove()
  } catch (err) {}
  cliStatus.succeed('Removed docker resources.')

  // ------------------------
  // Restore config files
  // ------------------------
  try {
    const sourceSettingsPath = path.join(config.source.path, 'ietf/settings_local.py')
    if (await fs.pathExists(`${sourceSettingsPath}.bak`)) {
      await fs.move(`${sourceSettingsPath}.bak`, sourceSettingsPath, { overwrite: true })
      ora('Restored source config settings file.').succeed()
    }
    // Target
    const targetSettingsPath = path.join(config.target.path, 'ietf/settings_local.py')
    if (await fs.pathExists(`${targetSettingsPath}.bak`)) {
      await fs.move(`${targetSettingsPath}.bak`, targetSettingsPath, { overwrite: true })
      ora('Restored target config settings file.').succeed()
    }
  } catch (err) { }
}

main()
