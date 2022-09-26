import {
    Tooltip as Tooltip,
    // Button as Button,
    // Collapse as Collapse,
    // ScrollSpy as ScrollSpy,
    Tab as Tab
} from "bootstrap";

import debounce from "lodash/debounce";
import Cookies from "js-cookie";
import { populate_nav } from "./nav.js";

const cookies = Cookies.withAttributes({ sameSite: "strict" });

// Chrome apparently wants this debounced to something >10ms,
// otherwise the main view doesn't scroll?

document.addEventListener("scroll", debounce(function () {
    const items = document.getElementById("toc-nav")
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
    // handle point size slider
    const cookie = "doc-ptsize-max";

    function change_ptsize(ptsize) {
        document.documentElement.style.setProperty(`--${cookie}`,
            `${ptsize}pt`);
        cookies.set(cookie, ptsize);
    }

    document.getElementById("ptsize")
        .oninput = function () { change_ptsize(this.value) };

    const ptsize = cookies.get(cookie);
    change_ptsize(ptsize ? Math.min(Math.max(7, ptsize), 16) : 16);

    // Use the Bootstrap tooltip plugin for all elements with a title attribute
    const tt_triggers = document.querySelectorAll(
        "[title]:not([title=''])");
    [...tt_triggers].map(tt_el => {
        const tooltip = Tooltip.getOrCreateInstance(tt_el);
        tt_el.addEventListener("click", el => {
            tooltip.hide();
            tt_el.blur();
        });
    });

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

    // Set up a nav pane
    const toc_pane = document.getElementById("toc-nav");
    populate_nav(toc_pane,
        `#content h2, #content h3, #content h4, #content h5, #content h6
         #content .h1, #content .h2, #content .h3, #content .h4, #content .h5, #content .h6`,
        ["py-0"]);

    // activate pref buttons selected by pref cookies
    document.querySelectorAll(".btn-check")
        .forEach(btn => {
            const id = btn.id.replace("-radio", "");
            if (cookies.get(btn.name) == id) {
                btn.checked = true;
            }
            btn.addEventListener("click", el => {
                cookies.set(btn.name, id);
                window.location.reload();
            });
        });

    // activate tab selected in prefs
    let defpane;
    try {
        defpane = Tab.getOrCreateInstance(
            `#${cookies.get("deftab")}-tab`);
    } catch (err) {
        defpane = Tab.getOrCreateInstance("#docinfo-tab");
    };
    defpane.show();
    document.activeElement.blur();
});
