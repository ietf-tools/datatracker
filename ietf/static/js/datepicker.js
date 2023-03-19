import {
    Datepicker
} from 'vanillajs-datepicker';

global.enable_datepicker = function (el) {
    // we need to translate from bootstrap-datepicker options to
    // vanillajs-datepicker options
    const view_mode = {
        day: 0,
        days: 0,
        month: 1,
        months: 1,
        year: 2,
        years: 2,
        decade: 3,
        decades: 3
    };

    let options = {
        buttonClass: "btn"
    };
    if (el.dataset.dateFormat) {
        options = { ...options,
            format: el.dataset.dateFormat
        };
        if (!el.dataset.dateFormat.includes("dd")) {
            options = { ...options,
                pickLevel: 1
            };
        }
    }
    if (el.dataset.dateMinViewMode && view_mode[el.dataset.dateMinViewMode]) {
        options = { ...options,
            startView: view_mode[el.dataset.dateMinViewMode]
        };
    }
    if (el.dataset.dateViewMode && view_mode[el.dataset.dateViewMode]) {
        options = { ...options,
            maxView: view_mode[el.dataset.dateViewMode]
        };
    }
    if (el.dataset.dateAutoclose) {
        options = { ...options,
            autohide: el.dataset.dateAutoclose
        };
    }

    new Datepicker(el, options);
}

document.addEventListener("DOMContentLoaded", function () {
    const elems = document.querySelectorAll('[data-provide="datepicker"]');
    elems.forEach(el => enable_datepicker(el));
});
