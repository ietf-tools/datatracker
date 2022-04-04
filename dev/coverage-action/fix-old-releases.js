const github = require('@actions/github')
const fs = require('fs/promises')
const isPlainObject = require('lodash/isPlainObject')
const orderBy = require('lodash/orderBy')
const find = require('lodash/find')
const slice = require('lodash/slice')
const round = require('lodash/round')
const { ChartJSNodeCanvas } = require('chartjs-node-canvas')

const chartJSNodeCanvas = new ChartJSNodeCanvas({ type: 'svg', width: 850, height: 300, backgroundColour: '#FFFFFF' })

async function main () {
  const token = 'YOUR_TOKEN_HERE'
  const gh = github.getOctokit(token)
  const owner = 'ietf-tools'
  const repo = 'datatracker'
  const repoCommon = 'common'

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

  // -> Load full coverage file
  console.info('Loading coverage results file...')
  const rawCoverage = await fs.readFile('data/release-coverage.json', 'utf8')
  const coverage = JSON.parse(rawCoverage)

  // -> Parse and reorder results
  const versions = []
  for (const [key, value] of Object.entries(coverage)) {
    if (isPlainObject(value)) {
      versions.push({
        tag: key,
        time: value?.time,
        stats: {
          code: value?.code?.coverage || 0,
          template: value?.template?.coverage || 0,
          url: value?.url?.coverage || 0
        }
      })
    }
  }
  const oVersions = orderBy(versions, ['time', 'tag'], ['desc', 'desc'])
  const roVersions = orderBy(versions, ['time', 'tag'], ['asc', 'asc'])

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

  // -> Upload release coverage
  for (const [idx, value] of oVersions.entries()) {
    const rel = find(releases, ['tag_name', value.tag])
    if (!rel) { continue }

    // -> Full Coverage File
    if (rel?.assets?.some(a => a.name === 'coverage.json')) {
      console.info(`Coverage file already exists for ${value.tag}, skipping...`)
    } else {
      console.info(`Building coverage object for ${value.tag}...`)
      const covData = Buffer.from(JSON.stringify({
        [value.tag]: coverage[value.tag],
        version: value.tag
      }), 'utf8')

      console.info(`Uploading coverage file for ${value.tag}...`)
      await gh.rest.repos.uploadReleaseAsset({
        data: covData,
        owner,
        repo,
        release_id: rel.id,
        name: 'coverage.json',
        headers: {
          'Content-Type': 'application/json'
        }
      })
    }

    // -> Historical Coverage File
    if (rel?.assets?.some(a => a.name === 'historical-coverage.json')) {
      console.info(`Historical Coverage file already exists for ${value.tag}, skipping...`)
    } else {
      console.info(`Building historical coverage object for ${value.tag}...`)
      const final = {}
      for (const obj of slice(oVersions, idx)) {
        final[obj.tag] = obj.stats
      }

      const covData = Buffer.from(JSON.stringify(final), 'utf8')

      console.info(`Uploading historical coverage file for ${value.tag}...`)
      await gh.rest.repos.uploadReleaseAsset({
        data: covData,
        owner,
        repo,
        release_id: rel.id,
        name: 'historical-coverage.json',
        headers: {
          'Content-Type': 'application/json'
        }
      })
    }

    // -> Coverage Chart
    if (chartsDirListing.some(c => c.name === `${rel.id}.svg`)) {
      console.info(`Chart SVG already exists for ${rel.name}, skipping...`)
    } else {
      console.info(`Generating chart SVG for ${rel.name}...`)
      const labels = []
      const datasetCode = []
      const datasetTemplate = []
      const datasetUrl = []
      for (const obj of slice(roVersions, 0, roVersions.length - idx)) {
        labels.push(obj.tag)
        datasetCode.push(round(obj.stats.code * 100, 2))
        datasetTemplate.push(round(obj.stats.template * 100, 2))
        datasetUrl.push(round(obj.stats.url * 100, 2))
      }

      const outputStream = chartJSNodeCanvas.renderToBufferSync({
        type: 'line',
        options: {
          borderColor: '#CCC',
          layout: {
            padding: 20
          },
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                font: {
                  size: 11
                }
              }
            }
          },
          scales: {
            x: {
              ticks: {
                font: {
                  size: 10
                }
              }
            },
            y: {
              ticks: {
                callback: (value) => {
                  return `${value}%`
                },
                font: {
                  size: 10
                }
              }
            }
          }
        },
        data: {
          labels,
          datasets: [
            {
              label: 'Code',
              data: datasetCode,
              borderWidth: 2,
              borderColor: '#E53935',
              backgroundColor: '#C6282833',
              fill: false,
              cubicInterpolationMode: 'monotone',
              tension: 0.4,
              pointRadius: 0
            },
            {
              label: 'Templates',
              data: datasetTemplate,
              borderWidth: 2,
              borderColor: '#039BE5',
              backgroundColor: '#0277BD33',
              fill: false,
              cubicInterpolationMode: 'monotone',
              tension: 0.4,
              pointRadius: 0
            },
            {
              label: 'URLs',
              data: datasetUrl,
              borderWidth: 2,
              borderColor: '#7CB342',
              backgroundColor: '#558B2F33',
              fill: false,
              cubicInterpolationMode: 'monotone',
              tension: 0.4,
              pointRadius: 0
            }
          ]
        }
      }, 'image/svg+xml')
      const svg = Buffer.from(outputStream).toString('base64')

      console.info(`Uploading chart SVG for ${rel.name}...`)
      await gh.rest.repos.createOrUpdateFileContents({
        owner,
        repo: repoCommon,
        path: `assets/graphs/datatracker/${rel.id}.svg`,
        message: `chore: update datatracker release chart for release ${rel.name}`,
        content: svg
      })
    }

    if (rel.body.includes(`${rel.id}.svg`)) {
      console.info(`Release ${rel.name} body already contains the chart SVG, skipping...`)
    } else {
      console.info(`Appending chart SVG to release ${rel.name} body...`)
      await gh.request('PATCH /repos/{owner}/{repo}/releases/{release_id}', {
        owner,
        repo,
        release_id: rel.id,
        body: `${rel.body}\r\n\r\n![chart](https://raw.githubusercontent.com/${owner}/${repoCommon}/main/assets/graphs/datatracker/${rel.id}.svg)`
      })
    }
  }
}

main()
