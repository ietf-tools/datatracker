<template>
  <div>sdfsdfsdf</div>
</template>
<script>
  import { h, onMounted, reactive, defineComponent } from 'vue'
  import { useNotification, NButton, Link } from 'naive-ui'
  
  // STATE
  const state = reactive({
    message: "",
  })
  
  export default defineComponent({
    setup() {

      fetch('/status/index.json')
        .then(resp => resp.json())
        .then(data => {
            if(data === null || data.hasMessage === false) {
                console.info("No status message")
                return
            }
            console.info("status message", data)
            const parser = new DOMParser()
            const main = document.querySelector("main")
            const htmlString = template(escapeHTML(data.message))
            const toastDom = parser.parseFromString(htmlString, "text/html")
            const toastEl = toastDom.body.childNodes[0]
            main.prepend(toastEl)
            console.log(bootstrap);
            new bootstrap.Toast(toastEl)
        })
        .catch(e => {
            console.error(e)
        }) 


      const notification = useNotification()
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
    }
  })
</script>
