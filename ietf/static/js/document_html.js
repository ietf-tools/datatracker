import {
    Tooltip as Tooltip,
    // Button as Button,
    // Collapse as Collapse,
    // ScrollSpy as ScrollSpy,
    Tab as Tab
} from "bootstrap";

import Cookies from "js-cookie";
import { populate_nav } from "./nav.js";

const cookies = Cookies.withAttributes({ sameSite: "strict" });

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
    change_ptsize(ptsize ? Math.min(Math.max(7, ptsize), 16) : 12);

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

    // Enable version diff functionality
    document.querySelectorAll(
            ".rev-picker .dropdown-menu li .dropdown-item")
        .forEach(rev => {
            rev.addEventListener("click", el => {
                const which = rev
                    .closest(".dropdown-menu")
                    .dataset.which;
                const btn = document.getElementById(which);
                rev.closest(".dropdown-menu")
                    .previousElementSibling
                    .innerText = btn.innerText = rev.innerText +
                    " ";
            });
        });

    function xlate(url, data) {
        if (url.toLowerCase() === "rfc") {
            return `rfc${data.rfcNumber}.txt`;
        }
        return `${data.idName}-${url}.txt`;
    }

    document.querySelectorAll(".do-diff")
        .forEach(btn => {
            btn.addEventListener("click", el => {
                let url1 = document.getElementById("url1")
                    .innerText.trim();
                let url2 = document.getElementById("url2")
                    .innerText.trim();
                url1 = xlate(url1, btn.dataset);
                url2 = xlate(url2, btn.dataset);
                const href = btn.dataset.href.replace(
                        "__url1__", url1)
                    .replace("__url2__", url2);
                window.location = href;
            });
        });
});
