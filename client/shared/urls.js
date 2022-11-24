/**
 * DO NOT add the urls here directly. Edit the urls.json file instead.
 * The urls are automatically precompiled into the variable below at build time.
 */
const urls = { /* __COMPILED_URLS__ */ }

/**
 * Get an URL and replace tokens with provided values.
 *
 * @param {string} key The key of the URL template to use.
 * @param {Object} [tokens] An object of tokens to replace in the URL template.
 * @returns {string} URL with tokens replaced with the provided values.
 */
export const getUrl = (key, tokens = {}) => {
  if (!key) { throw new Error('Must provide a key for getUrl()') }
  if (!urls[key]) { throw new Error('Invalid getUrl() key') }
  return urls[key](tokens)
}
