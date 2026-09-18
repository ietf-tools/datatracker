import github from '@actions/github'
import core from '@actions/core'
import { orderBy } from 'es-toolkit/array'
import { round } from 'es-toolkit/compat'
import fs from 'fs/promises'

const dec = new TextDecoder()

async function main() {
  const token = core.getInput('token')
  const inputCovPath = core.getInput('coverageResultsPath') // 'data/coverage-raw.json'
  const outputCovPath = core.getInput('coverageResultsPath') // 'data/coverage.json'
  const outputHistPath = core.getInput('histCoveragePath') // 'data/historical-coverage.json'
  const relVersionRaw = core.getInput('version') // 'v7.47.0'
  const relVersion = relVersionRaw.indexOf('v') === 0 ? relVersionRaw.substring(1) : relVersionRaw
  const gh = github.getOctokit(token)
  const owner = github.context.repo.owner // 'ietf-tools'
  const repo = github.context.repo.repo // 'datatracker'
  const sender = github.context.payload.sender.login // 'rjsparks'
  const repoCommon = core.getInput('repoCommon') // 'common'
  const summary = core.getInput('summary') // ''
  const changelog = core.getInput('changelog') // ''

  // -> Parse coverage results
  console.info('Parsing coverage.json file...')
  const covLatest = JSON.parse(await fs.readFile(inputCovPath, 'utf8'))
  const covLatestStats = {
    code: covLatest.latest.code.coverage,
    template: covLatest.latest.template.coverage,
    url: covLatest.latest.url.coverage
  }

  // -> Fix coverage results versioning
  console.info(`Writing ${relVersion} normalized coverage.json file...`)
  fs.writeFile(
    outputCovPath,
    JSON.stringify(
      {
        [relVersion]: covLatest.latest,
        version: relVersion
      },
      null,
      2
    ),
    'utf8'
  )

  // -> Fetch existing releases
  const releases = []
  let hasMoreReleases = false
  let releasesCurPage = 0
  do {
    hasMoreReleases = false
    releasesCurPage++
    const resp = await gh.request('GET /repos/{owner}/{repo}/releases', {
      owner,
      repo,
      page: releasesCurPage,
      per_page: 100
    })
    if (resp?.data?.length > 0) {
      console.info(`Fetching existing releases... ${(releasesCurPage - 1) * 100}`)
      hasMoreReleases = true
      releases.push(...resp.data)
    }
  } while (hasMoreReleases)
  console.info(`Found ${releases.length} existing releases.`)

  // -> Fetch latest historical coverage
  let covData = null
  for (const rel of orderBy(releases, ['created_at'], ['desc'])) {
    if (rel.draft) {
      continue
    }

    const covAsset = rel.assets.find((a) => a.name === 'historical-coverage.json')
    if (covAsset) {
      console.info(`Fetching latest historical-coverage.json from release ${rel.name}...`)
      const covRaw = await gh.request('GET /repos/{owner}/{repo}/releases/assets/{asset_id}', {
        owner,
        repo,
        asset_id: covAsset.id,
        headers: {
          Accept: 'application/octet-stream'
        }
      })
      covData = JSON.parse(dec.decode(covRaw.data))
      break
    }
  }

  // -> Update historical coverage
  if (!covData) {
    console.warn('Could not find historical coverage data... Skipping...')
  } else {
    console.info('Writing updated historical-coverage.json file...')
    covData = {
      [relVersion]: covLatestStats,
      ...covData
    }
    await fs.writeFile(outputHistPath, JSON.stringify(covData, null, 2), 'utf8')
  }

  // -> Find matching release version
  const newRelease = releases.find((r) => r.name === relVersionRaw)
  if (!newRelease) {
    console.warn(
      `Could not find a release matching ${relVersionRaw}... Skipping coverage chart generation...`
    )
    return
  }

  // -> Fetch list of existing chart files in common repo
  console.info('Fetching list of existing chart files from common repo...')
  const chartsDirListing = []
  const respDir = await gh.request('GET /repos/{owner}/{repo}/contents/{path}', {
    owner,
    repo: repoCommon,
    path: 'assets/graphs/datatracker'
  })
  if (respDir?.data?.length > 0) {
    chartsDirListing.push(...respDir.data)
  }

  // -> Add to changelog body
  let formattedBody = ''
  const covInfo = {
    code: round(covLatestStats.code * 100, 2),
    template: round(covLatestStats.template * 100, 2),
    url: round(covLatestStats.url * 100, 2)
  }

  formattedBody = summary ? `**Summary:** ${summary}\n` : ''
  formattedBody += `**Release Date**: ${Temporal.Now.zonedDateTimeISO('UTC').toLocaleString(
    'en-US',
    {
      weekday: 'short',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short'
    }
  )}\n`
  formattedBody += `**Release Author**: @${sender}\n`
  formattedBody += '\n---\n\n'
  formattedBody += changelog
  formattedBody += '\n\n---\n\n**Coverage**\n\n'
  formattedBody += `![](https://img.shields.io/badge/Code-${covInfo.code}%25-${getCoverageColor(covInfo.code)}?style=flat-square)`
  formattedBody += `![](https://img.shields.io/badge/Templates-${covInfo.template}%25-${getCoverageColor(covInfo.template)}?style=flat-square)`
  formattedBody += `![](https://img.shields.io/badge/URLs-${covInfo.url}%25-${getCoverageColor(covInfo.url)}?style=flat-square)\n\n`

  core.setOutput('changelog', formattedBody)
}

main()

function getCoverageColor(val) {
  if (val >= 95) {
    return 'brightgreen'
  } else if (val >= 90) {
    return 'green'
  } else if (val >= 80) {
    return 'yellowgreen'
  } else if (val >= 60) {
    return 'yellow'
  } else if (val >= 50) {
    return 'orange'
  } else {
    return 'red'
  }
}
