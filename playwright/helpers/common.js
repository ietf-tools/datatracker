module.exports = {
  /**
   * Validate whether a selector is visible in viewport
   *
   * @param {Object} page Page object
   * @param {String} selector Selector to validate
   * @returns Boolean
   */
  isIntersectingViewport: async (page, selector) => {
    return page.$eval(selector, async el => {
      const bottom = window.innerHeight
      const rect = el.getBoundingClientRect()

      return rect.top < bottom && rect.top > 0 - rect.height
    })
  }
}
