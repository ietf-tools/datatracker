import slugify from 'slugify'

export default (str) => {
  return slugify(str.replace('/', '-'), { lower: true })
}
