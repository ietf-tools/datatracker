// Copyright The IETF Trust 2021, All Rights Reserved
/* global URLSearchParams */
(function() {
  'use strict';

  function initialize() {
    const form = document.getElementById('timeslot-form');
    if (!form) {
      return;
    }

    const params = new URLSearchParams(document.location.search);
    const day = params.get('day');
    const date = params.get('date');
    const location = params.get('location');
    const time = params.get('time');
    const duration = params.get('duration');

    if (day) {
      const inp = form.querySelector('#id_days input[value="' + day +'"]');
      if (inp) {
        inp.checked = true;
      } else if (date) {
        const date_field = form.querySelector('#id_other_date');
        date_field.value = date;
      }
    }
    if (location) {
      const inp = form.querySelector('#id_locations input[value="' + location + '"]');
      inp.checked=true;
    }
    if (time) {
      const inp = form.querySelector('input#id_time');
      inp.value = time;
    }
    if (duration) {
      const inp = form.querySelector('input#id_duration');
      inp.value = duration;
    }
  }

  window.addEventListener('load', initialize);
})();