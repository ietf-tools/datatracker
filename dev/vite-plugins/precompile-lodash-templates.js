import { createFilter } from '@rollup/pluginutils'
import template from 'lodash/template'
import transform from 'lodash/transform'
import fs from 'fs/promises'

export default function precompileLodashTemplates(options = {}) {
  const filter = createFilter(options.include, options.exclude)
  return {
    name: 'precompile-lodash-templates',
    enforce: 'pre',
    async transform(code, id) {
      if (!filter(id)) { return }

      const jsonPath = `${id}on`
      const urls = JSON.parse(await fs.readFile(jsonPath, { encoding: 'utf8' }))

      const interpolate = /{([\s\S]+?)}/g
      const compiledUrls = transform(urls, (result, value, key) => {
        result.push(`"${key}": ${template(value.replaceAll('{', '{data.'), { interpolate, variable: 'data' }).source.replace('function(obj)', '(obj) =>')}`)
      }, [])

      return {
        code: code.replace('/* __COMPILED_URLS__ */', compiledUrls.join(',\n')),
        map: null
      }
    }
  }
}
