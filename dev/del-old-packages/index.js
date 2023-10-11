import { Octokit } from '@octokit/core'
import { setTimeout } from 'node:timers/promises'
import { DateTime } from 'luxon'

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN
})

const oldestDate = DateTime.utc().minus({ days: 7 })

for (const pkgName of ['datatracker-db']) {
  let hasMore = true
  let currentPage = 1

  while (hasMore) {
    try {
      console.info(`Fetching page ${currentPage}...`)
      const versions = await octokit.request('GET /orgs/{org}/packages/{package_type}/{package_name}/versions{?page,per_page,state}', {
        package_type: 'container',
        package_name: pkgName,
        org: 'ietf-tools',
        page: currentPage,
        per_page: 100
      })
      if (versions?.data?.length > 0) {
        for (const ver of versions?.data) {
          const verDate = DateTime.fromISO(ver.created_at)
          if (ver?.metadata?.container?.tags?.includes('latest') || ver?.metadata?.container?.tags?.includes('latest-arm64') || ver?.metadata?.container?.tags?.includes('latest-x64')) {
            console.info(`Latest package (${ver.id})... Skipping...`)
          } else if (verDate > oldestDate) {
            console.info(`Recent package (${ver.id}, ${verDate.toRelative()})... Skipping...`)
          } else {
            console.info(`Deleting package version ${ver.id}...`)
            await octokit.request('DELETE /orgs/{org}/packages/{package_type}/{package_name}/versions/{package_version_id}', {
              package_type: 'container',
              package_name: pkgName,
              org: 'ietf-tools',
              package_version_id: ver.id
            })
            await setTimeout(250)
          }
        }
        currentPage++
        hasMore = true
      } else {
        hasMore = false
        console.info('No more versions for this package.')
      }
    } catch (err) {
      console.error(err)
      hasMore = false
    }
  }
}
