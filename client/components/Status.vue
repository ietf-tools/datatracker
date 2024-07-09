<script>
  import { h, defineComponent } from 'vue'
  import { useNotification } from 'naive-ui'
  import { localStorageWrapper } from '../shared/local-storage-wrapper';
  import { JSONWrapper } from '../shared/json-wrapper';

  const STORAGE_KEY = "status-dismissed"

  const getDismissedStatuses = () => {
    const jsonString = localStorageWrapper.getItem(STORAGE_KEY)
    const jsonValue = JSONWrapper.parse(jsonString, [])
    if(Array.isArray(jsonValue)) {
      return jsonValue;
    }
    return [];
  }

  const dismissStatus = (id) => {
    const dissmissed = [id, ...getDismissedStatuses()];
    localStorageWrapper.setItem(STORAGE_KEY, JSONWrapper.stringify(dissmissed));
    return true;
  }

  let timer
  let notificationInstances = {} // keyed by status.id
  let notification


  const pollStatusAPI = () => {
    if (timer) {
      clearTimeout(timer)
    }

    fetch('/status/latest.json')
        .then(resp => resp.json())
        .then(status => {
            if(status === null || status.hasMessage === false) {
                console.info("No status message")
                return
            }
            const dismissedStatuses = getDismissedStatuses()
            if(dismissedStatuses.includes(status.id)) {
              console.info(`Not showing site status ${status.id} because it was already dismissed. Dismissed Ids:`, dismissedStatuses)
              return
            }

            const isSameStatusPage = Boolean(document.querySelector(`[data-status-id="${status.id}"]`))

            if(isSameStatusPage) {
              console.info(`Not showing site status ${status.id} because we're on the target page`)
              return
            }

            if(notificationInstances[status.id]) {
              console.info(`Not showing site status ${status.id} because it's already been displayed`)
              return
            }

            notificationInstances[status.id] = notification.create({
              title: status.title,
              content: status.body,
              meta: `${status.date}`,
              action: () =>
                h(
                  'a',
                  {
                    href: status.url,
                  },
                  "Read more"
                ),
              onClose: () => {
                return dismissStatus(status.id)
              }
            })
        })
        .catch(e => {
            console.error(e)
        })
    
    timer = setTimeout(pollStatusAPI, 60 * 1000)
  }
  
  
  export default defineComponent({
    setup() {
      notification = useNotification()
      pollStatusAPI(notification)
    }
  })
</script>
