#!/usr/bin/env node

import Docker from 'dockerode'
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
import { performance } from 'perf_hooks'
import { Duration } from 'luxon'
import keypress from 'keypress'

let dock = null
let diffOutput = []
const diffStack = []
const config = {  
  options: [],
  source: process.cwd(),
  target: null,
  tmpDir: null,
  savePath: null,
  shouldCleanup: false
}
const containers = {
  net: null,
  dbSource: null,
  dbTarget: null,
  appSource: null,
  appTarget: null
}
const sha1reg = /^[0-9a-f]{5,40}$/

/**
 * Prompt the user for a path
 * 
 * @param {Task} task Listr task instance
 * @param {String} msg Prompt message
 * @param {Boolean} mustExist Whether the path must already exist
 * @returns path
 */
async function promptForPath (task, msg, mustExist = true, initial) {
  return task.prompt([
    {
      type: 'input',
      name: 'path',
      message: msg,
      initial,
      async validate (input) {
        if (!input) {
          return 'You must provide a valid path!'
        }
        const proposedPath = path.resolve('.', input)
        if (proposedPath.includes(config.source)) {
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
  const archivePath = path.join(config.target, `archive.${ext}`)
  await fs.emptyDir(config.target)
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
      task.output = config.target
      await fs.move(path.join(tmpDir, kebabCase(`datatracker-${branch}`)), config.target, { overwrite: true })
      await fs.remove(tmpDir)
    } else if (ext === 'tgz') {
      await tar.x({
        strip: 1,
        file: archivePath,
        cwd: config.target,
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
async function executeCommand (task, container, cmd, collectOutput = false, silent = false) {
  const logStack = []
  const errStack = []
  let logFStream = null
  return new Promise(async (resolve, reject) => {
    // Handle stream output
    const logStream = new PassThrough()
    logStream.on('data', chunk => {
      const logLine = chunk.toString('utf8').trim()
      if (logLine && !silent) {
        task.output = logLine
        if (collectOutput) {
          logStack.push(...logLine.split('\n').filter(l => l))
        }
      }
    })
    logStream.on('error', chunk => {
      task.output = chunk.toString('utf8')
      errStack.push(chunk.toString('utf8'))
    })
    if (collectOutput) {
      logFStream = fs.createWriteStream(path.join(config.savePath))
      logStream.pipe(logFStream)
    }
    // Execute command in container
    const execChmod = await container.exec({
      Cmd: cmd,
      AttachStdout: true,
      AttachStderr: true
    })
    const execChmodStream = await execChmod.start()
    // Handle stream close
    execChmodStream.on('close', () => {
      if (collectOutput) {
        logFStream.close()
      }
      if (errStack.length > 0) {
        reject(new Error(errStack))
      } else {
        if (!silent) {
          
        }
        task.output = ''
        resolve(logStack)
      }
    })
    // Pipe container stream to log stream
    container.modem.demuxStream(execChmodStream, logStream, logStream)
  })
}

/**
 * Run cleanup tasks (e.g. stop/remove docker resources)
 * 
 * @param {Boolean} exitAfter Whether to exit the process at the end
 */
async function cleanup (exitAfter = false) {
  try {
    const cleanupTasks = new Listr([
      // ------------------------
      // Stop + Remove Containers
      // ------------------------
      {
        title: 'Stop + remove docker containers',
        task: async (ctx, task) => {
          task.output = 'Stopping containers...'
          try {
            await Promise.allSettled([
              containers.dbSource && containers.dbSource.stop(),
              containers.dbTarget && containers.dbTarget.stop(),
              containers.appSource && containers.appSource.stop(),
              containers.appTarget && containers.appTarget.stop()
            ])
          } catch (err) { }
          task.output = 'Removing containers...'
          try {
            await Promise.allSettled([
              containers.dbSource && containers.dbSource.remove({ v: true }),
              containers.dbTarget && containers.dbTarget.remove({ v: true }),
              containers.appSource && containers.appSource.remove({ v: true }),
              containers.appTarget && containers.appTarget.remove({ v: true })
            ])
          } catch (err) { }
          task.output = 'Removing network...'
          try {
            await containers.net.remove()
          } catch (err) {}
        }
      },
      // --------------------
      // Restore config files
      // --------------------
      {
        title: 'Restore original source settings file',
        task: async (ctx, task) => {
          const sourceSettingsPath = path.join(config.source, 'ietf/settings_local.py')
          if (await fs.pathExists(`${sourceSettingsPath}.bak`)) {
            await fs.move(`${sourceSettingsPath}.bak`, sourceSettingsPath, { overwrite: true })
            task.title = 'Restored original source settings file.'
          } else {
            task.skip('Nothing to restore.')
          }
        }
      },
      {
        title: 'Restore original target settings file',
        task: async (ctx, task) => {
          const targetSettingsPath = path.join(config.target, 'ietf/settings_local.py')
          if (await fs.pathExists(`${targetSettingsPath}.bak`)) {
            await fs.move(`${targetSettingsPath}.bak`, targetSettingsPath, { overwrite: true })
            task.title = 'Restored original target settings file.'
          } else {
            task.skip('Nothing to restore.')
          }
        }
      }
    ], {
      registerSignalListeners: false
    })
  
    await cleanupTasks.run()

    // Cleanup
    if (config.tmpDir) {
      await fs.remove(config.tmpDir)
    }

  } catch (err) {
    console.error(chalk.redBright(err.message))
    process.exit(1)
  }

  if (exitAfter) {
    process.exit(0)
  }
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
          while(!(await fs.pathExists(path.join(config.source, 'requirements.txt')))) {
            config.source = path.resolve(config.source, '..')
            parentIdx++
            if (parentIdx > 2) {
              throw new Error('Start the CLI from a valid datatracker project path.')
            }
          }
          task.title = `Using path ${config.source} for source datatracker instance.`
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
              { name: 'branch', message: 'Remote GitHub branch...' },
              { name: 'tag', message: 'Remote GitHub tag...' },
              { name: 'commit', message: 'Remote GitHub commit hash...' }
              // { name: 'release', message: 'Latest GitHub release', disabled: true }
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
            // ------------------------------------------------
            case 'local': {
              task.title = 'Waiting for diff target path input'
              config.target = await promptForPath(task, 'Enter the local path to the datatracker project to compare against:')
              task.title = `Using path ${config.target} for target datatracker instance.`
              break
            }
            // MODE: REMOTE BRANCH
            // ------------------------------------------------
            case 'branch': {
              // Prompt for branch
              const branches = []
              let branch = 'main'
              try {
                task.title = 'Fetching available remote branches...'
                const branchesResp = await got('https://api.github.com/repos/ietf-tools/datatracker/branches?per_page=100').json()
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
              config.target = await promptForPath(task, 'Enter a local path where the branch contents will be downloaded to:', false)
              await fs.ensureDir(config.target)
        
              // Download / Extract branch zip
              await downloadExtractZip(task, {
                msg: `Downloading ${branch} branch contents...`,
                url: `https://github.com/ietf-tools/datatracker/archive/refs/heads/${branch}.tar.gz`,
                ext: 'tgz'
              })

              task.title = `Fetched branch ${branch} to ${config.target}`
              break
            }
            // MODE: REMOTE TAG
            // ------------------------------------------------
            case 'tag': {
              // Prompt for tag             
              const tag = await task.prompt([
                {
                  type: 'input',
                  message: 'Enter the remote repository tag to compare against:'
                }
              ])
        
              // Prompt for local path where to download tag contents
              config.target = await promptForPath(task, 'Enter a local path where the tag contents will be downloaded to:', false)
              await fs.ensureDir(config.target)
        
              // Download / Extract tag tarball
              await downloadExtractZip(task, {
                msg: `Downloading tag ${tag} contents...`,
                url: `https://github.com/ietf-tools/datatracker/archive/refs/tags/${tag}.tar.gz`,
                ext: 'tgz'
              })

              task.title = `Fetched tag ${tag} to ${config.target}`
              break
            }
            // MODE: REMOTE COMMIT
            // ------------------------------------------------
            case 'commit': {
              // Prompt for commit hash             
              const commit = await task.prompt([
                {
                  type: 'input',
                  message: 'Enter the FULL commit hash to compare against:',
                  async validate (input) {
                    if (!input) {
                      return 'You must provide a hash!'
                    } else if (!sha1reg.test(input)) {
                      return 'Invalid hash!'
                    }
                    return true
                  }
                }
              ])
        
              // Prompt for local path where to download commit contents
              config.target = await promptForPath(task, 'Enter a local path where the commit contents will be downloaded to:', false)
              await fs.ensureDir(config.target)
        
              // Download / Extract commit tarball
              await downloadExtractZip(task, {
                msg: `Downloading commit ${commit} contents...`,
                url: `https://github.com/ietf-tools/datatracker/archive/${commit}.tar.gz`,
                ext: 'tgz'
              })

              task.title = `Fetched commit ${commit} to ${config.target}`
              break
            }
            // MODE: LATEST RELEASE
            // ------------------------------------------------
            case 'release': {
              task.title = 'Waiting for diff target download location'
              // Prompt for local path where to download release
              config.target = await promptForPath(task, 'Enter a local path where the latest release will be downloaded to:', false)
              await fs.ensureDir(config.target)
        
              // Download / extract latest release
              await downloadExtractZip(task, {
                msg: 'Downloading latest release...',
                url: 'https://github.com/ietf-tools/datatracker/releases/latest/download/release.tar.gz',
                ext: 'tgz'
              })

              task.title = `Fetched latest release to ${config.target}`
              break
            }
            default: {
              throw new Error('Invalid selection. Exiting...')
            }
          }

          // Add missing files not present in branch
          if (!(await fs.pathExists(path.join(config.target, 'dev/diff')))) {
            task.output = `Add missing diff tool files...`
            await fs.ensureDir(path.join(config.target, 'dev/diff'))
            await fs.copy(path.join(config.source, 'dev/diff/prepare.sh'), path.join(config.target, 'dev/diff/prepare.sh'))
            await fs.copy(path.join(config.source, 'dev/diff/settings_local.py'), path.join(config.target, 'dev/diff/settings_local.py'))
          }
        }
      },
      // ------------------------
      // Prompt for crawl options
      // ------------------------
      {
        title: 'Select additional crawl options',
        task: async (ctx, task) => {
          const toggleIndicatorFn = (state, choice) => {
            return choice.enabled ? chalk.greenBright('✔') : chalk.gray('o')
          }
          config.options = await task.prompt([
            {
              type: 'multiselect',
              message: 'Select additional options to enable:',
              hint: '(use <SPACE> to toggle, <ENTER> to confirm)',
              choices: [
                { message: 'Skip HTML Validation', name: '--skip-html-validation', hint: 'Skip HTML Validation', indicator: toggleIndicatorFn },
                { message: 'Fail-fast', name: '--failfast', hint: 'Stop the crawl on the first page failure', indicator: toggleIndicatorFn },
                { message: 'No-Follow', name: '--no-follow', hint: 'Do not follow URLs found in fetched pages, just check the given URLs', indicator: toggleIndicatorFn },
                { message: 'No-Revisit', name: '--no-revisit', hint: 'Don\'t revisit already visited URLs', indicator: toggleIndicatorFn },
                { message: 'Pedantic', name: '--pedantic', hint: 'Stop the crawl on the first error or warning', indicator: toggleIndicatorFn },
                { message: 'Random', name: '--random', hint: 'Crawl URLs randomly', indicator: toggleIndicatorFn },
                { message: 'Validate All', name: '--validate-all', hint: 'Run html 5 validation on all pages, without skipping similar urls', indicator: toggleIndicatorFn },
                { message: 'Verbose', name: '--verbose', hint: 'Be more verbose', indicator: toggleIndicatorFn }
              ]
            }
          ])
          if (config.options.length > 0) {
            task.title = `Selected additional crawl options: ${config.options.join(' ')}`
          }
        }
      },
      // ---------------------------
      // Prompt to save crawl output
      // ---------------------------
      {
        title: 'Save crawl output',
        task: async (ctx, task) => {
          const saveToDisk = await task.prompt({
            type: 'confirm',
            message: 'Save the crawl output to file?'
          })

          if (saveToDisk) {
            config.savePath = await promptForPath(task, 'Enter the path where the crawl output will be saved:', false, path.join(os.homedir(), 'Desktop/crawl-out.txt'))
            task.title = `Crawl output will be saved to ${config.savePath}`
          } else {
            config.tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'dt-'))
            config.savePath = path.join(config.tmpDir, 'out.txt')
            task.title = 'Crawl output will not be saved.'
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
          const sourceSettingsPath = path.join(config.source, 'ietf/settings_local.py')
          if (await fs.pathExists(sourceSettingsPath)) {
            await fs.move(sourceSettingsPath, `${sourceSettingsPath}.bak`, { overwrite: true })
          }
          const cfgSourceRaw = await fs.readFile(path.join(config.source, 'dev/diff/settings_local.py'), 'utf8')
          await fs.outputFile(sourceSettingsPath, cfgSourceRaw.replace('__DBHOST__', 'dt-diff-db-source'))
          // Target
          const targetSettingsPath = path.join(config.target, 'ietf/settings_local.py')
          if (await fs.pathExists(targetSettingsPath)) {
            await fs.move(targetSettingsPath, `${targetSettingsPath}.bak`, { overwrite: true })
          }
          const cfgTargetRaw = await fs.readFile(path.join(config.target, 'dev/diff/settings_local.py'), 'utf8')
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
            title: 'Pulling latest DB docker image...',
            task: async (subctx, subtask) => {
              const dbImagePullStream = await dock.pull('ghcr.io/ietf-tools/datatracker-db:latest')
              await new Promise((resolve, reject) => {
                dock.modem.followProgress(dbImagePullStream, (err, res) => err ? reject(err) : resolve(res))
              })
              subtask.title = `Pulled latest DB docker image successfully.`
            }
          },
          {
            title: 'Pulling latest Datatracker base docker image...',
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
          config.shouldCleanup = true
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
                    `${config.source}:/workspace`
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
                    `${config.target}:/workspace`
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
              await executeCommand(subtask, containers.appSource, ['bash', '-c', 'chmod +x ./dev/diff/prepare.sh'])
              await executeCommand(subtask, containers.appSource, ['bash', './dev/diff/prepare.sh'])
              subtask.title = `Preparing source Datatracker instance - Running checks...`
              await executeCommand(subtask, containers.appSource, ['bash', '-c', './ietf/manage.py check'])
              subtask.title = `Preparing source Datatracker instance - Applying migrations...`
              await executeCommand(subtask, containers.appSource, ['bash', '-c', './ietf/manage.py migrate'])
              subtask.title = `Source Datatracker instance is now ready.`
            }
          },
          {
            title: 'Preparing target Datatracker instance...',
            task: async (subctx, subtask) => {
              await executeCommand(subtask, containers.appTarget, ['bash', '-c', 'chmod +x ./dev/diff/prepare.sh'])
              await executeCommand(subtask, containers.appTarget, ['bash', './dev/diff/prepare.sh'])
              subtask.title = `Run target Datatracker instance - Running checks...`
              await executeCommand(subtask, containers.appTarget, ['bash', '-c', './ietf/manage.py check'])
              subtask.title = `Run target Datatracker instance - Applying migrations...`
              await executeCommand(subtask, containers.appTarget, ['bash', '-c', './ietf/manage.py migrate'])
              subtask.title = `Run target Datatracker instance - Starting server...`
              executeCommand(subtask, containers.appTarget, ['bash', '-c', './ietf/manage.py runserver 0.0.0.0:8000 --settings=settings_local'])
              subtask.title = `Run target Datatracker instance - Waiting for server to accept connections...`
              await executeCommand(subtask, containers.appTarget, ['bash', '-c', '/usr/local/bin/wait-for localhost:8000 -t 300'])
              subtask.title = `Target Datatracker instance is now ready and accepting connections.`
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
      // Run crawl tool
      // --------------
      {
        title: 'Run crawl',
        task: async (ctx, task) => {
          task.title = 'Running crawl... (Press F10 to cancel)'
          task.output = 'Starting ./bin/test-crawl... (Results will start appearing soon)'
          
          const startMs = performance.now()

          config.options.push('--settings=ietf.settings_testcrawl')
          config.options.push('--diff http://dt-diff-app-target:8000/')

          // Run crawl
          const errStack = []
          let execChmodStream = null
          let linesScanned = 0
          const execPromise = new Promise(async (resolve, reject) => {
            // Handle stream output
            const logStream = new PassThrough()
            logStream.on('data', chunk => {
              const logLines = chunk.toString('utf8').trim().split('\n').filter(l => l.trim())
              // Check for DIFF mentions
              if (logLines.length > 0) {
                linesScanned += logLines.length
                for (const logLine of logLines) {
                  if (logLine.includes('DIFF')) {
                    diffStack.push(logLine)
                  }
                }
                const currentDur = Duration.fromMillis(performance.now() - startMs)
                task.output = `[${currentDur.toFormat('hh:mm:ss')}] Scanned ${linesScanned} lines. Found ${diffStack.length} DIFF mentions.`
              }
            })
            // Handle error stream
            logStream.on('error', chunk => {
              task.output = chunk.toString('utf8')
              errStack.push(chunk.toString('utf8'))
            })
            // Pipe to file stream
            const logFStream = fs.createWriteStream(path.join(config.savePath))
            logStream.pipe(logFStream)
            // Execute command in container
            const execChmod = await containers.appSource.exec({
              Cmd: ['bash', '-c', `./bin/test-crawl ${config.options.join(' ')}`],
              AttachStdout: true,
              AttachStderr: true
            })
            execChmodStream = await execChmod.start()
            // Handle stream close
            execChmodStream.on('close', () => {
              logFStream.close()
              process.stdin.setRawMode(false)
              process.stdin.resume()
              if (errStack.length > 0) {
                reject(new Error(errStack))
              } else {
                resolve()
              }
            })
            // Pipe container stream to log stream
            containers.appSource.modem.demuxStream(execChmodStream, logStream, logStream)
          })

          // Handle F10 Exit
          keypress(process.stdin)
          process.stdin.on('keypress', (ch, key) => {
            if (key && key.name === 'f10') {
              task.title = 'Run crawl'
              execChmodStream.destroy()
              task.skip()
            }
          })
          process.stdin.setRawMode(true)
          process.stdin.resume()

          return execPromise
        }
      }
    ])

    await tasks.run()

  } catch (err) {
    console.error(chalk.redBright(err.message))
  }

  // ------------------------
  // Cleanup
  // ------------------------

  await cleanup()

  // ------------------------
  // Output results
  // ------------------------

  console.info('\n=====================')
  console.info('RESULTS')
  console.info('=====================\n')

  if (diffStack.length > 0) {
    for (const diffLine of diffStack) {
      console.info(`> ${diffLine}`)
    }
    console.info(chalk.blueBright(`\nFound ${diffStack.length} mention(s) of DIFF.\n`))
  } else {
    console.info(chalk.blueBright(`No mention of DIFF were found.\n`))
  }

  process.exit(0)
}

// Handle user interrupt
// process.once('SIGINT', async () => {
//   console.info('Trying to shutdown gracefully...')
//   if (config.shouldCleanup) {
//     setTimeout(() => { process.exit(1) }, 30000).unref()
//     try {
//       await cleanup()
//     } catch (err) {
//       console.warn(`Failed to shutdown gracefully: ${err.message}`)
//     }
//   }
//   process.exit(0)
// })

main()
