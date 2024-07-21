import slugify from 'slugify'

export default (str) => {
  return slugify(str.replaceAll('/', '-'), { lower: true })
}
