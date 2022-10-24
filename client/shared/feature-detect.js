const cache = {}

export function storageAvailable(type) {
  if (Object.prototype.hasOwnProperty.call(cache, type)) {
    return cache[type]
  }
  try {
    let storage = window[type]
    const x = '__storage_test__'
    storage.setItem(x, x)
    storage.removeItem(x)
    cache[type] = true
    return true
  }
  catch (e) {
    cache[type] = false
    return false
  }
}
