/* Copyright The IETF Trust 2021, All Rights Reserved
 *
 * JS support for the SessionPurposeAndTypeWidget
 * */
(function() {
  'use strict';

  /* Find elements that are parts of the session details widgets. This is an
  * HTMLCollection that will update if the DOM changes, so ok to evaluate immediately. */
  const widget_elements = document.getElementsByClassName('session_purpose_widget');

  /* Find the id prefix for each widget. Individual elements have a _<number> suffix. */
  function get_widget_ids(elements) {
    const ids = new Set();
    for (let ii=0; ii < elements.length; ii++) {
      const parts = elements[ii].id.split('_');
      parts.pop();
      ids.add(parts.join('_'));
    }
    return ids;
  }

  /* Set the 'type' element to a type valid for the currently selected purpose, if possible */
  function set_valid_type(type_elt, purpose, allowed_types) {
    const valid_types = allowed_types[purpose] || [];
    if (valid_types.indexOf(type_elt.value) === -1) {
      type_elt.value = (valid_types.length > 0) ? valid_types[0] : '';
    }
  }

  /* Hide any type options not allowed for the selected purpose */
  function update_type_option_visibility(type_option_elts, purpose, allowed_types) {
    const valid_types = allowed_types[purpose] || [];
    for (const elt of type_option_elts) {
      if (valid_types.indexOf(elt.value) === -1) {
        elt.setAttribute('hidden', 'hidden');
      } else {
        elt.removeAttribute('hidden');
      }
    }
  }

  /* Update visibility of 'type' select so it is only shown when multiple options are available */
  function update_widget_visibility(elt, purpose, allowed_types) {
    const valid_types = allowed_types[purpose] || [];
    if (valid_types.length > 1) {
      elt.removeAttribute('hidden'); // make visible
    } else {
      elt.setAttribute('hidden', 'hidden'); // make invisible
    }
  }

  /* Update the 'type' select to reflect a change in the selected purpose */
  function update_type_element(type_elt, purpose, type_options, allowed_types) {
    update_widget_visibility(type_elt, purpose, allowed_types);
    update_type_option_visibility(type_options, purpose, allowed_types);
    set_valid_type(type_elt, purpose, allowed_types);
  }

  /* Factory for event handler with a closure */
  function purpose_change_handler(type_elt, type_options, allowed_types) {
    return function(event) {
      update_type_element(type_elt, event.target.value, type_options, allowed_types);
    };
  }

  /* Initialization */
  function on_load() {
    for (const widget_id of get_widget_ids(widget_elements)) {
      const purpose_elt = document.getElementById(widget_id + '_0');
      const type_elt = document.getElementById(widget_id + '_1');
      const type_options = type_elt.getElementsByTagName('option');
      const allowed_types = JSON.parse(type_elt.dataset.allowedOptions);

      purpose_elt.addEventListener(
        'change',
        purpose_change_handler(type_elt, type_options, allowed_types)
      );
      update_type_element(type_elt, purpose_elt.value, type_options, allowed_types);
    }
  }
  window.addEventListener('load', on_load, false);
})();