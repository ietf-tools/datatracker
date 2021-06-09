// Copyright The IETF Trust 2015-2021, All Rights Reserved
var ietf_sessions; // public interface

(function() {
  'use strict';

  function stat_ls (val){
    if (val == 0) {
      document.form_post.length_session1.disabled = true;
      document.form_post.length_session2.disabled = true;
      if (document.form_post.length_session3) { document.form_post.length_session3.disabled = true; }
      document.form_post.session_time_relation.disabled = true;
      document.form_post.joint_for_session.disabled = true;
      document.form_post.length_session1.value = 0;
      document.form_post.length_session2.value = 0;
      document.form_post.length_session3.value = 0;
      document.form_post.session_time_relation.value = '';
      document.form_post.joint_for_session.value = '';
      document.form_post.third_session.checked=false;
    }
    if (val == 1) {
      document.form_post.length_session1.disabled = false;
      document.form_post.length_session2.disabled = true;
      if (document.form_post.length_session3) { document.form_post.length_session3.disabled = true; }
      document.form_post.session_time_relation.disabled = true;
      document.form_post.joint_for_session.disabled = true;
      document.form_post.length_session2.value = 0;
      document.form_post.length_session3.value = 0;
      document.form_post.session_time_relation.value = '';
      document.form_post.joint_for_session.value = '1';
      document.form_post.third_session.checked=false;
    }
    if (val == 2) {
      document.form_post.length_session1.disabled = false;
      document.form_post.length_session2.disabled = false;
      if (document.form_post.length_session3) { document.form_post.length_session3.disabled = false; }
      document.form_post.session_time_relation.disabled = false;
      document.form_post.joint_for_session.disabled = false;
    }
  }

  function check_num_session (val) {
    if (document.form_post.num_session.value < val) {
      alert("Please change the value in the Number of Sessions to use this field");
      document.form_post.num_session.focused = true;
      return true;
    }
    return false;
  }

  function check_third_session () {
    if (document.form_post.third_session.checked == false) {

      return true;
    }
    return false;
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

  function on_load() {
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
    stat_ls: stat_ls,
    check_num_session: check_num_session,
    check_third_session: check_third_session,
    delete_last_joint_with_groups: delete_last_joint_with_groups,
    delete_wg_constraint_clicked: delete_wg_constraint_clicked
  }
})();