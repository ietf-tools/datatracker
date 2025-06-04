const announcementApp = (function() {
    'use strict';
    return {
        // functions for Announcement
        checkToField: function() {
            document.documentElement.scrollTop = 0; // For most browsers
            const toField = document.getElementById('id_to');
            const toCustomInput = document.getElementById('id_to_custom');
            const toCustomDiv = toCustomInput.closest('div.row');
            
            if (toField.value === 'Other...') {
                toCustomDiv.style.display = 'flex'; // Show the custom field
            } else {
                toCustomDiv.style.display = 'none'; // Hide the custom field
                toCustomInput.value = ''; // Optionally clear the input value if hidden
            }
        }
    };
})();

// Extra care is required to ensure the back button 
// works properly for the optional to_custom field.
// Take the case when a user selects "Other..." for
// "To" field. The "To custom" field appears and they
// enter a new address there.
// In Chrome, when the form is submitted and then the user
// uses the back button (or browser back), the page loads
// from bfcache then the javascript DOMContentLoaded event
// handler is run, hiding the empty to_custom field, THEN the
// browser autofills the form fields. Because to_submit
// is now hidden it does not get a value. This is a very
// bad experience for the user because the to_custom field
// was unexpectedly cleared and hidden. If they notice this
// they would need to know to first select another "To"
// option, then select "Other..." again just to get the
// to_custom field visible so they can re-enter the custom
// address.
// The solution is to use setTimeout to run checkToField
// after a short delay, giving the browser time to autofill
// the form fields before it checks to see if the to_custom
// field is empty and hides it.

document.addEventListener('DOMContentLoaded', function() {
    // Run the visibility check after allowing cache to populate values
    setTimeout(announcementApp.checkToField, 300);

    const toField = document.getElementById('id_to');
    toField.addEventListener('change', announcementApp.checkToField);
});

// Handle back/forward navigation with pageshow
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        // Then apply visibility logic after cache restoration
        setTimeout(announcementApp.checkToField, 300);
    }
});