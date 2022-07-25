import {
    Tooltip as Tooltip,
    // Button as Button,
    // Collapse as Collapse,
    // ScrollSpy as ScrollSpy,
    // Tab as Tab
} from "bootstrap";

import debounce from "lodash/debounce";

function make_nav() {
    const nav = document.createElement("nav");
    nav.classList.add("nav-pills", "ps-3", "fw-normal", "flex-column");
    return nav;
}

// Chrome apparently wants this debounced to something >10ms,
// otherwise the main view doesn't scroll?

document.addEventListener("scroll", debounce(function () {
    const items = document.querySelector("#toc")
        .querySelectorAll(".active");
    const item = [...items].pop();
    if (item) {
        item.scrollIntoView({
            block: "center",
            behavior: "smooth"
        });
    }
}, 100));

document.addEventListener("DOMContentLoaded", function (event) {
    // Use the Bootstrap tooltip plugin for all elements with a title attribute
    const tt_triggers = document.querySelectorAll(
        "[title]:not([title=''])");
    [...tt_triggers].map(tt_el => new Tooltip(tt_el));

    // Rewrite ids and hrefs to not contains dots (bug in bs5.2 scrollspy)
    // See https://github.com/twbs/bootstrap/issues/34381
    // TODO: check if this can be removed when bs5 is updated
    const ids = document.querySelectorAll(
        ".rfcmarkup [id^=section-], .rfcmarkup [id^=appendix-]");
    [...ids].map(id_el => id_el.id = id_el.id.replaceAll(/\./g, "-"));
    const hrefs = document.querySelectorAll(
        ".rfcmarkup [href*='#section-'], .rfcmarkup [href*='#appendix-']"
    );
    [...hrefs].map(id_el => {
        const href = new URL(id_el.href);
        href.hash = href.hash.replaceAll(/\./g, "-");
        id_el.href = href.href;
    });

    const tabs = document.querySelectorAll("li.nav-item");
    [...tabs].map(t_el => {
        const tooltip = Tooltip.getInstance(t_el);
        t_el.addEventListener("click", el => {
            tooltip.hide();
        });

    });

    // Extract section headings from document
    const headings = document.querySelectorAll(
        // ".rfcmarkup h1, "
        ".rfcmarkup h2, .rfcmarkup h3, " +
        ".rfcmarkup h4, .rfcmarkup h5, .rfcmarkup h6"
    );

    // Set up a nav pane
    const toc_pane = document.querySelector("#toc");
    let nav_stack = [toc_pane];
    let cur_level = 0;
    headings.forEach(el => {
        let level = el.tagName.at(-1) - 2;
        if (level < cur_level) {
            while (level < cur_level) {
                let nav = nav_stack.pop();
                cur_level--;
                nav_stack[level].appendChild(nav);
            }
        } else {
            while (level > cur_level) {
                nav_stack.push(make_nav());
                cur_level++;
            }
        }

        const link = document.createElement("a");
        link.classList.add("nav-link", "py-0", "ps-1", "d-flex");

        if (el.childNodes.length > 1) {
            link.href = el.childNodes[0].attributes.href.nodeValue;
        } else {
            link.classList.add("disabled");
            link.setAttribute("href", "#");
        }

        const words = el.innerText.split(/\s+/);
        const number = document.createElement("div");
        number.classList.add("pe-1");
        number.textContent = words[0];
        link.appendChild(number);
        const text = document.createElement("div");
        text.classList.add("text-break");
        text.textContent = words.slice(1)
            .join(" ");
        link.appendChild(text);

        nav_stack[level].appendChild(link);
    });

    for (var i = nav_stack.length - 1; i > 0; i--) {
        nav_stack[i - 1].appendChild(nav_stack[i]);
    }
});
