/**
* Disable Submit Button on Form Submit
*/
function onLoginSubmit (ev) {
    const submitBtn = document.querySelector('#dt-login-form button[type=submit]')
    if (submitBtn) {
        submitBtn.disabled = true
        submitBtn.innerHTML = 'Signing in...'
    }
}

$(function() {
    document.querySelector('#dt-login-form').addEventListener('submit', onLoginSubmit)
})
