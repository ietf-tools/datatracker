export const JSONWrapper = {
  parse(jsonString, defaultValue) {
    if(typeof jsonString !== "string") {
      return defaultValue
    }
    try {
      return JSON.parse(jsonString);
    } catch (e) {
      console.error(e);
    }
    return defaultValue
  },
  stringify(data) {
    try {
      return JSON.stringify(data);
    } catch (e) {
      console.error(e)
    }
  },
}
