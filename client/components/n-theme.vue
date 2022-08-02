<template lang='pug'>
n-config-provider(:theme-overrides='themeOverrides')
  slot
</template>

<script>
import { NConfigProvider } from 'naive-ui'

export default {
  components: {
    NConfigProvider
  },
  data () {
    return {
      themeOverrides: {
        common: {
          primaryColor: '#0d6efd',
          primaryColorHover: '#0d6efd'
        }
      }
    }
  }
}
</script>
