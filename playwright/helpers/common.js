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
  },
  /**
   * Override page DateTime with a new value
   *
   * @param {Object} page Page object
   * @param {Object} dateTimeOverride New DateTime object
   */
  overridePageDateTime: async (page, dateTimeOverride) => {
    await page.addInitScript(`{
      // Extend Date constructor to default to fixed time
      Date = class extends Date {
        constructor(...args) {
          if (args.length === 0) {
            super(${dateTimeOverride.toMillis()});
          } else {
            super(...args);
          }
        }
      }
      // Override Date.now() to start from fixed time
      const __DateNowOffset = ${dateTimeOverride.toMillis()} - Date.now();
      const __DateNow = Date.now;
      Date.now = () => __DateNow() + __DateNowOffset;
    }`)
  }
}
