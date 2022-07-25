import { Tooltip as Tooltip, Button as Button, Collapse as Collapse } from 'bootstrap';

// Use the Bootstrap tooltip plugin for all elements with a title attribute
document.addEventListener("DOMContentLoaded", function (event) {
    const tooltipTriggerList = document.querySelectorAll(
        '[title]:not([title=""])');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl =>
        new Tooltip(tooltipTriggerEl));
});
