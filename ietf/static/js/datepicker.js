import {
    Datepicker
} from 'vanillajs-datepicker';

document.addEventListener("DOMContentLoaded", function () {
    const elems = document.querySelectorAll('[data-provide="datepicker"]');
    elems.forEach(el => {
        new Datepicker(el, {
            buttonClass: "btn"
        });
    });
});
