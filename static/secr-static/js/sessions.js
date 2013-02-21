function resetfieldstat () {
  if (document.form_post.p_num_session.value > 0) {
    document.form_post.length_session1.disabled=false;
  }
  if (document.form_post.p_num_session.value > 1) {
    document.form_post.length_session2.disabled=false;
  }
  if (document.form_post.prev_third_session.value > 0) {
    document.form_post.length_session3.disabled=false;
  }
  return 1;
}

function stat_ls (val){
  if (val == 0) {
    document.form_post.length_session1.disabled = true;
    document.form_post.length_session2.disabled = true;
    document.form_post.length_session3.disabled = true;
    document.form_post.length_session1.value = 0;
    document.form_post.length_session2.value = 0;
    document.form_post.length_session3.value = 0;
    document.form_post.third_session.checked=false;
  }
  if (val == 1) {
    document.form_post.length_session1.disabled = false;
    document.form_post.length_session2.disabled = true;
    document.form_post.length_session3.disabled = true;
    document.form_post.length_session2.value = 0;
    document.form_post.length_session3.value = 0;
    document.form_post.third_session.checked=false;
  }
  if (val == 2) {
    document.form_post.length_session1.disabled = false;
    document.form_post.length_session2.disabled = false;
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
function handleconflictfield (val) {
  if (val==1) {
    if (document.form_post.conflict1.value.length > 0) {
       document.form_post.conflict2.disabled=false;
       if (document.form_post.conflict2.value.length > 0) {
         document.form_post.conflict3.disabled=false;
       }
       return 1;
    } else {
       if (document.form_post.conflict2.value.length > 0 || document.form_post.conflict3.value.length > 0) {
         alert("Second and Third Conflicts to Avoid fields are being disabled");
         document.form_post.conflict2.disabled=true;   
         document.form_post.conflict3.disabled=true;   
         return 0;
       }
    }
  } else {
    if (document.form_post.conflict2.value.length > 0) {
       document.form_post.conflict3.disabled=false;
       return 1;
    } else {
       if (document.form_post.conflict3.value.length > 0) {
         alert("Third Conflicts to Avoid field is being disabled");
         document.form_post.conflict3.disabled=true;   
         return 0;
       }
    }
  }
  return 1; 
}
function delete_last1 () {
  var b = document.form_post.conflict1.value;
  var temp = new Array();
  temp = b.split(' ');
  temp.pop();
  b = temp.join(' ');
  document.form_post.conflict1.value = b;
  document.form_post.wg_selector1.selectedIndex=0;
}
function delete_last2 () {
  var b = document.form_post.conflict2.value;
  var temp = new Array();
  temp = b.split(' ');
  temp.pop();
  b = temp.join(' ');
  document.form_post.conflict2.value = b;
  document.form_post.wg_selector2.selectedIndex=0;
}
function delete_last3 () {
  var b = document.form_post.conflict3.value;
  var temp = new Array();
  temp = b.split(' ');
  temp.pop();
  b = temp.join(' ');
  document.form_post.conflict3.value = b;
  document.form_post.wg_selector3.selectedIndex=0;
}

function check_prior_conflict(val) {
  if (val == 2) {
    if (document.form_post.conflict1.value=="") { 
      alert("Please specify your First Priority prior to using this field");
      document.form_post.conflict2.disabled=true;
      document.form_post.conflict3.disabled=true;
      document.form_post.wg_selector1.focus();
      return 0;
    }
  }
  else  {
    if (document.form_post.conflict2.value=="" && document.form_post.conflict1.value=="") { 
      alert("Please specify your First and Second Priority prior to using this field");
      document.form_post.conflict3.disabled=true;
      document.form_post.wg_selector1.focus();
      return 0;
    } else {
       if (document.form_post.conflict2.value=="") {
         alert("Please specify your Second Priority prior to using this field");
         document.form_post.conflict3.disabled=true;
         document.form_post.wg_selector2.focus();
         return 0;
       }
    }
  }

  return 1;
}

function retrieve_data () {
  document.form_post.num_session.selectedIndex = document.form_post.prev_num_session.value;
  document.form_post.length_session1.selectedIndex = document.form_post.prev_length_session1.value;
  document.form_post.length_session2.selectedIndex = document.form_post.prev_length_session2.value;
  document.form_post.length_session3.selectedIndex = document.form_post.prev_length_session3.value;
  document.form_post.number_attendee.value = document.form_post.prev_number_attendee.value;
  document.form_post.conflict1.value = document.form_post.prev_conflict1.value;
  document.form_post.conflict2.value = document.form_post.prev_conflict2.value;
  document.form_post.conflict3.value = document.form_post.prev_conflict3.value;
  document.form_post.conflict_other.value = document.form_post.prev_conflict_other.value;
  document.form_post.special_req.value = document.form_post.prev_special_req.value;
  return 1;
}
