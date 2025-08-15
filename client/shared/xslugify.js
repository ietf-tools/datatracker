import slugify from 'slugify'

export default (str) => {
  return slugify(str.replaceAll('/', '-').replaceAll(/['&]/g, ''), { lower: true })
}
