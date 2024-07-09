
/*
 *  DEVELOPER NOTE
 *
 *  Some browsers can block storage (localStorage, sessionStorage)
 *  access for privacy reasons, and all browsers can have storage
 *  that's full, and then they throw exceptions.
 *
 *  See https://michalzalecki.com/why-using-localStorage-directly-is-a-bad-idea/
 *
 *  Exceptions can even be thrown when testing if localStorage
 *  even exists. This can throw:
 * 
 *      if (window.localStorage)
 *
 *  Also localStorage/sessionStorage can be enabled after DOMContentLoaded
 *  so we handle it gracefully.
 *
 *  1) we need to wrap all usage in try/catch
 *  2) we need to defer actual usage of these until
 *     necessary,
 *    
 */

export const localStorageWrapper = {
  getItem: (key) => {
    try {
      return localStorage.getItem(key)
    } catch (e) {
      console.error(e); 
    }
    return null;
  },
  setItem: (key, value) => {
    try {
      return localStorage.setItem(key, value)
    } catch (e) {
      console.error(e); 
    }
    return;
  },
}
