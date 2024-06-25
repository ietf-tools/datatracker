const template = (message) => `
<div class="toast" role="alert" aria-live="assertive" aria-atomic="true">
  <div class="toast-header">
    <strong class="mr-auto">Site status</strong>
    <small>11 mins ago</small>
    <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
      <span aria-hidden="true">&times;</span>
    </button>
  </div>
  <div class="toast-body">
    ${message}
  </div>
</div>`;

function escapeHTML(unsafeText) {
    let div = document.createElement('div');
    div.innerText = unsafeText;
    return div.innerHTML;
}

fetch('/status/index.json')
    .then(resp => resp.json())
    .then(data => {
        if(data === null) {
            return;
        }
        const parser = new DOMParser();
        const main = document.querySelector("main");
        const htmlString = template(escapeHTML(data.message));
        const toastDom = parser.parseFromString(htmlString, "text/html");
        main.prepend(toastDom.body)
    })
    .catch(e => {
        console.error(e)
    }) 
