<script>
  import { h, onMounted, reactive, defineComponent } from 'vue'
  import { useNotification, NButton, Link } from 'naive-ui'
  
  // STATE
  const state = reactive({
    message: "",
  })
  
  export default defineComponent({
    setup() {
      const notification = useNotification()

      fetch('/status/latest.json')
        .then(resp => resp.json())
        .then(data => {
            if(data === null || data.hasMessage === false) {
                console.info("No status message")
                return
            }
            console.info("status message", data)
            
            const n = notification.create({
              title: 'Satisfaction',
              content: `wgat`,
              meta: '2019-5-27 15:11',
              action: () =>
                h(
                  'a',
                  {
                    href: "https://zombo.com",
                  },
                  "Read more"
                ),
              onClose: () => {
                if (!markAsRead) {
                  message.warning('Please mark as read')
                  return false
                }
              }
            })
        })
        .catch(e => {
            console.error(e)
        }) 
    }
  })
</script>
