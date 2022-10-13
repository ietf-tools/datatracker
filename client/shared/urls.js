import template from 'lodash-es/template'
import transform from 'lodash-es/transform'

const urls = {
  meetingDetails: '/meeting/{meetingNumber}/session/{eventAcronym}/',
  meetingMaterialsPdf: '/meeting/{meetingNumber}/agenda/{eventAcronym}-drafts.pdf',
  meetingMaterialsTar: '/meeting/{meetingNumber}/agenda/{eventAcronym}-drafts.tgz',
  meetingNotes: 'https://notes.ietf.org/notes-ietf-{meetingNumber}-{eventAcronym}'
}

const interpolate = /{([\s\S]+?)}/g
const compiled = transform(urls, (result, value, key) => {
  result[key] = template(value, { interpolate })
}, {})

/**
 * Get an URL and replace tokens with provided values.
 *
 * @param {string} key The key of the URL template to use.
 * @param {Object} [tokens] An object of tokens to replace in the URL template.
 * @returns {string} URL with tokens replaced with the provided values.
 */
export const getUrl = (key, tokens = {}) => {
  if (!key) { throw new Error('Must provide a key for getUrl()') }
  if (!compiled[key]) { throw new Error('Invalid getUrl() key') }
  return compiled[key](tokens)
}
