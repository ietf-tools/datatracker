fetch('/status/index.json')
    .then(resp => resp.json())
    .then(data => {
        alert(JSON.stringify(data))
    })
