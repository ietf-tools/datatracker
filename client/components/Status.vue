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

  let timer;
  let notificationInstance;

  const pollNotification = (notification) => {
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
            const dismissedStatuses = getDismissedStatuses();
            if(dismissedStatuses.includes(status.id)) {
              console.info(`Not showing site status ${status.id} because it was already dismissed. Dismissed Ids:`, dismissedStatuses)
              return;
            }

            console.log(status, status.date);
            
            notificationInstance = notification.create({
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
    
    timer = setTimeout(pollNotification, 60 * 1000)
  }
  
  
  export default defineComponent({
    setup() {
      const notification = useNotification()
      pollNotification(notification);
    }
  })
</script>
