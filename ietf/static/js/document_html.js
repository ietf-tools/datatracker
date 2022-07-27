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
    nav.classList.add("nav-pills", "ps-3", "flex-column");
    return nav;
}

// Chrome apparently wants this debounced to something >10ms,
// otherwise the main view doesn't scroll?

document.addEventListener("scroll", debounce(function () {
    const items = document.querySelector("#toc-nav")
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
        "#content [id^=section-], #content [id^=appendix-]");
    [...ids].map(id_el => id_el.id = id_el.id.replaceAll(/\./g, "-"));
    const hrefs = document.querySelectorAll(
        "#content [href*='#section-'], #content [href*='#appendix-']"
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

    // Set up a nav pane
    const toc_pane = document.querySelector("#toc-nav");

    // Extract section headings from document
    const headings = document.querySelectorAll(
        // "#content h1, "
        "#content h2, #content h3, " +
        "#content h4, #content h5, #content h6"
    );

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

        for (let i = 0; i < el.childNodes.length; i++) {
            if (el.childNodes[i].attributes &&
                el.childNodes[i].attributes.href.nodeValue) {
                link.href = el.childNodes[i].attributes.href.nodeValue;
            }
        }
        if (!link.href) {
            link.classList.add("disabled");
            link.setAttribute("href", "#");
        }

        const words = el.innerText.split(/\s+/);
        let nr = "";
        if (words[0].includes(".")) {
            nr = words.shift();
        } else if (words.length > 1 && words[1].includes(".")) {
            nr = words.shift() + " " + words.shift();
        }

        if (nr) {
            const number = document.createElement("div");
            number.classList.add("pe-1");
            number.textContent = nr;
            link.appendChild(number);
        }

        const text = document.createElement("div");
        text.classList.add("text-break");
        text.textContent = words.join(" ");
        link.appendChild(text);

        nav_stack[level].appendChild(link);
    });

    for (var i = nav_stack.length - 1; i > 0; i--) {
        nav_stack[i - 1].appendChild(nav_stack[i]);
    }
});
