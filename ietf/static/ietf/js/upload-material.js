// Copyright The IETF Trust 2021, All Rights Reserved
(
  function () {
    'use strict';

    /**
     * Hide the inactive input form-group
     * @param form form to process
     */
    function showUrlOrFile(form) {
      const useUrlInput = form.elements.namedItem('use_url');
      const urlGroup = form.elements.namedItem('external_url').closest('.form-group');
      const fileGroup = form.elements.namedItem('file').closest('.form-group');

      if (useUrlInput.checked) {
        urlGroup.hidden = false;
        fileGroup.hidden = true;
      } else {
        urlGroup.hidden = true;
        fileGroup.hidden = false;
      }
    }

    /**
     * Dispatch showUrlOrFile from a UI event on the enclosing form
     * @param evt change event instance
     */
    function handleFormChange(evt) {
      showUrlOrFile(evt.currentTarget); // currentTarget is the form
    }

    /**
     * Clear hidden file input values before submitting form to avoid
     * needlessly sending a file when use_url is selected
     * @param evt submit event instance
     */
    function handleFormSubmit(evt) {
      const form = evt.currentTarget;
      const fileInput = form.elements.namedItem('file');
      if (fileInput.hidden) {
        fileInput.value = '';
      }
    }

    /**
     * Register event handlers and other initialization tasks.
     */
    function initialize() {
      const forms = document.querySelectorAll('form.upload-material');
      for (let i = 0; i < forms.length; i++) {
        const form = forms[i];
        form.addEventListener('change', handleFormChange);
        form.addEventListener('submit', handleFormSubmit);
        showUrlOrFile(form);
      }
    }

    initialize();
  }
)();