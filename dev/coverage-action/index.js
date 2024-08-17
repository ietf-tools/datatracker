const github = require('@actions/github')
const core = require('@actions/core')
const orderBy = require('lodash/orderBy')
const find = require('lodash/find')
const round = require('lodash/round')
const fs = require('fs/promises')
const { DateTime } = require('luxon')
// const isPlainObject = require('lodash/isPlainObject')

const dec = new TextDecoder()

async function main () {
  const token = core.getInput('token')
  // const tokenCommon = core.getInput('tokenCommon')
  const inputCovPath = core.getInput('coverageResultsPath') // 'data/coverage-raw.json'
  const outputCovPath = core.getInput('coverageResultsPath') // 'data/coverage.json'
  const outputHistPath = core.getInput('histCoveragePath') // 'data/historical-coverage.json'
  const relVersionRaw = core.getInput('version') // 'v7.47.0'
  const relVersion = relVersionRaw.indexOf('v') === 0 ? relVersionRaw.substring(1) : relVersionRaw
  const gh = github.getOctokit(token)
  // const ghCommon = github.getOctokit(tokenCommon)
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
  fs.writeFile(outputCovPath, JSON.stringify({
    [relVersion]: covLatest.latest,
    version: relVersion
  }, null, 2), 'utf8')

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
    if (rel.draft) { continue }

    const covAsset = find(rel.assets, ['name', 'historical-coverage.json'])
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
  const newRelease = find(releases, ['name', relVersionRaw])
  if (!newRelease) {
    console.warn(`Could not find a release matching ${relVersionRaw}... Skipping coverage chart generation...`)
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

  // -> Coverage Chart
  // if (chartsDirListing.some(c => c.name === `${newRelease.id}.svg`)) {
  //   console.info(`Chart SVG already exists for ${newRelease.name}, skipping...`)
  // } else {
  //   console.info(`Generating chart SVG for ${newRelease.name}...`)

  //   const { ChartJSNodeCanvas } = require('chartjs-node-canvas')
  //   const chartJSNodeCanvas = new ChartJSNodeCanvas({ type: 'svg', width: 850, height: 300, backgroundColour: '#FFFFFF' })

  //   // -> Reorder versions
  //   const versions = []
  //   for (const [key, value] of Object.entries(covData)) {
  //     if (isPlainObject(value)) {
  //       const vRel = find(releases, r => r.tag_name === key || r.tag_name === `v${key}`)
  //       if (!vRel) {
  //         continue
  //       }
  //       versions.push({
  //         tag: key,
  //         time: vRel.created_at,
  //         stats: {
  //           code: round(value.code * 100, 2),
  //           template: round(value.template * 100, 2),
  //           url: round(value.url * 100, 2)
  //         }
  //       })
  //     }
  //   }
  //   const roVersions = orderBy(versions, ['time', 'tag'], ['asc', 'asc'])

  //   // -> Fill axis + data points
  //   const labels = []
  //   const datasetCode = []
  //   const datasetTemplate = []
  //   const datasetUrl = []

  //   for (const ver of roVersions) {
  //     labels.push(ver.tag)
  //     datasetCode.push(ver.stats.code)
  //     datasetTemplate.push(ver.stats.template)
  //     datasetUrl.push(ver.stats.url)
  //   }

  //   // -> Generate chart SVG
  //   const outputStream = chartJSNodeCanvas.renderToBufferSync({
  //     type: 'line',
  //     options: {
  //       borderColor: '#CCC',
  //       layout: {
  //         padding: 20
  //       },
  //       plugins: {
  //         legend: {
  //           position: 'bottom',
  //           labels: {
  //             font: {
  //               size: 11
  //             }
  //           }
  //         }
  //       },
  //       scales: {
  //         x: {
  //           ticks: {
  //             font: {
  //               size: 10
  //             }
  //           }
  //         },
  //         y: {
  //           ticks: {
  //             callback: (value) => {
  //               return `${value}%`
  //             },
  //             font: {
  //               size: 10
  //             }
  //           }
  //         }
  //       }
  //     },
  //     data: {
  //       labels,
  //       datasets: [
  //         {
  //           label: 'Code',
  //           data: datasetCode,
  //           borderWidth: 2,
  //           borderColor: '#E53935',
  //           backgroundColor: '#C6282833',
  //           fill: false,
  //           cubicInterpolationMode: 'monotone',
  //           tension: 0.4,
  //           pointRadius: 0
  //         },
  //         {
  //           label: 'Templates',
  //           data: datasetTemplate,
  //           borderWidth: 2,
  //           borderColor: '#039BE5',
  //           backgroundColor: '#0277BD33',
  //           fill: false,
  //           cubicInterpolationMode: 'monotone',
  //           tension: 0.4,
  //           pointRadius: 0
  //         },
  //         {
  //           label: 'URLs',
  //           data: datasetUrl,
  //           borderWidth: 2,
  //           borderColor: '#7CB342',
  //           backgroundColor: '#558B2F33',
  //           fill: false,
  //           cubicInterpolationMode: 'monotone',
  //           tension: 0.4,
  //           pointRadius: 0
  //         }
  //       ]
  //     }
  //   }, 'image/svg+xml')
  //   const svg = Buffer.from(outputStream).toString('base64')

    // // -> Upload to common repo
    // console.info(`Uploading chart SVG for ${newRelease.name}...`)
    // await ghCommon.rest.repos.createOrUpdateFileContents({
    //   owner,
    //   repo: repoCommon,
    //   path: `assets/graphs/datatracker/${newRelease.id}.svg`,
    //   message: `chore: update datatracker release chart for release ${newRelease.name}`,
    //   content: svg
    // })
  // }

  // -> Add to changelog body
  let formattedBody = ''
  const covInfo = {
    code: round(covLatestStats.code * 100, 2),
    template: round(covLatestStats.template * 100, 2),
    url: round(covLatestStats.url * 100, 2)
  }

  formattedBody = summary ? `**Summary:** ${summary}\n` : ''
  formattedBody += `**Release Date**: ${DateTime.now().setZone('utc').toFormat('ccc, LLLL d, y \'at\' h:mm a ZZZZ')}\n`
  formattedBody += `**Release Author**: @${sender}\n`
  formattedBody += '\n---\n\n'
  formattedBody += changelog
  formattedBody += '\n\n---\n\n**Coverage**\n\n'
  formattedBody += `![](https://img.shields.io/badge/Code-${covInfo.code}%25-${getCoverageColor(covInfo.code)}?style=flat-square)`
  formattedBody += `![](https://img.shields.io/badge/Templates-${covInfo.template}%25-${getCoverageColor(covInfo.template)}?style=flat-square)`
  formattedBody += `![](https://img.shields.io/badge/URLs-${covInfo.url}%25-${getCoverageColor(covInfo.url)}?style=flat-square)\n\n`
  // formattedBody += `![chart](https://raw.githubusercontent.com/${owner}/${repoCommon}/main/assets/graphs/datatracker/${newRelease.id}.svg)`

  core.setOutput('changelog', formattedBody)
}

main()

function getCoverageColor (val) {
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
