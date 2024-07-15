<script setup>
  import { h, onMounted } from 'vue'
  import { useNotification } from 'naive-ui'
  import { localStorageWrapper } from '../shared/local-storage-wrapper'
  import { JSONWrapper } from '../shared/json-wrapper'
  import { STATUS_STORAGE_KEY, generateStatusTestId } from '../shared/status-common'

  const getDismissedStatuses = () => {
    const jsonString = localStorageWrapper.getItem(STATUS_STORAGE_KEY)
    const jsonValue = JSONWrapper.parse(jsonString, [])
    if(Array.isArray(jsonValue)) {
      return jsonValue
    }
    return []
  }

  const dismissStatus = (id) => {
    const dissmissed = [id, ...getDismissedStatuses()]
    localStorageWrapper.setItem(STATUS_STORAGE_KEY, JSONWrapper.stringify(dissmissed))
    return true
  }

  let notificationInstances = {} // keyed by status.id
  let notification

  const pollStatusAPI = () => {
    fetch('/status/latest.json')
        .then(resp => resp.json())
        .then(status => {
            if(status === null || status.hasMessage === false) {
                console.debug("No status message")
                return
            }
            const dismissedStatuses = getDismissedStatuses()
            if(dismissedStatuses.includes(status.id)) {
              console.debug(`Not showing site status ${status.id} because it was already dismissed. Dismissed Ids:`, dismissedStatuses)
              return
            }

            const isSameStatusPage = Boolean(document.querySelector(`[data-status-id="${status.id}"]`))

            if(isSameStatusPage) {
              console.debug(`Not showing site status ${status.id} because we're on the target page`)
              return
            }

            if(notificationInstances[status.id]) {
              console.debug(`Not showing site status ${status.id} because it's already been displayed`)
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
                    'data-testid': generateStatusTestId(status.id),
                    href: status.url,
                    'aria-label': `Read more about ${status.title}`
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
  }
  
  onMounted(() => {
      notification = useNotification()
      pollStatusAPI(notification)
  })
</script>
