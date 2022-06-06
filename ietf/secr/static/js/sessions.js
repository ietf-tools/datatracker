// Copyright The IETF Trust 2015-2021, All Rights Reserved
/* global alert */
var ietf_sessions; // public interface

(function() {
  'use strict';

  function get_formset_management_data(prefix) {
    return {
      total_forms: document.getElementById('id_' + prefix + '-TOTAL_FORMS').value,
    };
  }

  function update_session_form_visibility(session_num, is_visible) {
    const elt = document.getElementById('session_row_' + session_num);
    if (elt) {
      elt.hidden = !is_visible;
      elt.querySelector('[name$="DELETE"]').value = is_visible ? '' : 'on';
    }
  }

  function have_additional_session() {
    const elt = document.getElementById('id_third_session');
    return elt && elt.checked;
  }

  function update_for_num_sessions(val) {
    const total_forms = get_formset_management_data('session_set').total_forms;
    val = Number(val);
    if (have_additional_session()) {
      val++;
    }

    for (let i=0; i < total_forms; i++) {
      update_session_form_visibility(i, i < val);
    }

    const only_one_session = (val === 1);
    if (document.form_post.session_time_relation) {
      document.form_post.session_time_relation.disabled = only_one_session;
      document.form_post.session_time_relation.closest('tr').hidden = only_one_session;
    }
    if (document.form_post.joint_for_session) {
      document.form_post.joint_for_session.disabled = only_one_session;
    }
    const third_session_row = document.getElementById('third_session_row');
    if (third_session_row) {
      third_session_row.hidden = val < 2;
    }
  }

  function delete_last_joint_with_groups () {
    var b = document.form_post.joint_with_groups.value;
    var temp = b.split(' ');
    temp.pop();
    b = temp.join(' ');
    document.form_post.joint_with_groups.value = b;
    document.form_post.joint_with_groups_selector.selectedIndex=0;
  }

/*******************************************************************/
// WG constraint UI support

// get the constraint field element for a given slug
  function constraint_field(slug) {
    return document.getElementById('id_constraint_' + slug);
  }

// get the wg selection element for a given slug
  function constraint_selector(slug) {
    return document.getElementById('id_wg_selector_' + slug);
  }

  /**
   * Handler for constraint select input 'change' event
   */
  function wg_constraint_selector_changed() {
    let slug = this.getAttribute('data-slug');
    let cfield = constraint_field(slug);
    // add selected value to constraint_field
    cfield.value += ' ' + this.options[this.selectedIndex].value;
  }

  /**
   * Remove the last group in a WG constraint field
   *
   * @param slug ConstraintName slug
   */
  function delete_last_wg_constraint(slug) {
    let cfield = constraint_field(slug);
    if (cfield) {
      var b = cfield.value;
      var temp = b.split(' ');
      temp.pop();
      b = temp.join(' ');
      cfield.value = b;
      constraint_selector(slug).selectedIndex = 0;
    }
  }

  /**
   * Handle click event on a WG constraint's delete button
   *
   * @param slug ConstraintName slug
   */
  function delete_wg_constraint_clicked(slug) {
    delete_last_wg_constraint(slug);
  }

  /**
   * Handler for the change event on the session count select or 'third session' checkbox
   */
  function handle_num_session_change(event) {
    const num_select_value = Number(event.target.value);
    if (num_select_value !== 2) {
      if (document.form_post.third_session) {
        document.form_post.third_session.checked = false;
      }
    }
    update_for_num_sessions(num_select_value);
  }

  function handle_third_session_change(event) {
    const num_select_value = Number(document.getElementById('id_num_session').value);
    if (num_select_value === 2) {
      update_for_num_sessions(num_select_value);
    } else {
      event.target.checked = false;
    }
  }

  /* Initialization */
  function on_load() {
    // Attach event handler to session count select
    const num_session_select = document.getElementById('id_num_session');
    num_session_select.addEventListener('change', handle_num_session_change);
    const third_session_input = document.getElementById('id_third_session');
    if (third_session_input) {
      third_session_input.addEventListener('change', handle_third_session_change);
    }
    update_for_num_sessions(num_session_select.value);

    // Attach event handlers to constraint selectors
    let selectors = document.getElementsByClassName('wg_constraint_selector');
    for (let index = 0; index < selectors.length; index++) {
      selectors[index].addEventListener('change', wg_constraint_selector_changed, false)
    }

  }

  // initialize after page loads
  window.addEventListener('load', on_load, false);

  // expose public interface methods
  ietf_sessions = {
    delete_last_joint_with_groups: delete_last_joint_with_groups,
    delete_wg_constraint_clicked: delete_wg_constraint_clicked
  }
})();