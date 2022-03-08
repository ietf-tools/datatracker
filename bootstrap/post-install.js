const fs = require('fs-extra')
const path = require('path')

fs.copySync(path.join(process.cwd(), 'dist'), path.join(process.cwd(), '../ietf/static/ietf/bootstrap'))
