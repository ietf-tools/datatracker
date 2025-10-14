#!/usr/bin/env node

import yargs from 'yargs/yargs'
import { hideBin } from 'yargs/helpers'
import slugify from 'slugify'

const argv = yargs(hideBin(process.argv)).argv

let branch = argv.branch
if (!branch) {
  throw new Error('Missing --branch argument!')
}
if (branch.indexOf('/') >= 0) {
  branch = branch.split('/').slice(1).join('-')
}
branch = slugify(branch, { lower: true, strict: true })
if (branch.length < 1) {
  throw new Error('Branch name is empty!')
}
process.stdout.write(`dt-${branch}`)

process.exit(0)
