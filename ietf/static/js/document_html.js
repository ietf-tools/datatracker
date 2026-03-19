import {
    Tooltip as Tooltip,
    // Button as Button,
    // Collapse as Collapse,
    // ScrollSpy as ScrollSpy,
    Tab as Tab
} from "bootstrap";

import Cookies from "js-cookie";
import { populate_nav } from "./nav.js";
import "./select2.js";

const cookies = Cookies.withAttributes({ sameSite: "strict" });

// set initial point size from cookie before DOM is ready, to avoid flickering
const ptsize_var = "doc-ptsize-max";

function change_ptsize(ptsize) {
    document.documentElement.style.setProperty(`--${ptsize_var}`,
        `${ptsize}pt`);
    localStorage.setItem(ptsize_var, ptsize);
}

const ptsize = localStorage.getItem(ptsize_var);
change_ptsize(ptsize ? Math.min(Math.max(7, ptsize), 16) : 12);

document.addEventListener("DOMContentLoaded", function (event) {
    // handle point size slider
    document.getElementById("ptsize")
        .oninput = function () { change_ptsize(this.value) };

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
    const headings = document.querySelectorAll(`#content :is(h2, h3, h4, h5, h6, .h2, .h3, .h4, .h5, .h6)`);
    populate_nav(toc_pane, headings, ["py-0"]);

    // activate pref buttons selected by pref cookies or localStorage
    const in_localStorage = ["deftab", "reflinks"];
    const btn_pref = {
        "sidebar": "on",
        "deftab": "docinfo",
        "htmlconf": "html",
        "pagedeps": "reference",
        "reflinks": "refsection"
    };
    document.querySelectorAll("#pref-tab-pane .btn-check")
        .forEach(btn => {
            const id = btn.id.replace("-radio", "");

            const val = in_localStorage.includes(btn.name) ?
                localStorage.getItem(btn.name) : cookies.get(btn.name);
            if (val === id || (val === null && btn_pref[btn.name] === id)) {
                btn.checked = true;
            }

            btn.addEventListener("click", el => {
                // only use cookies for things used in HTML templates
                if (in_localStorage.includes(btn.name)) {
                    localStorage.setItem(btn.name, id)
                } else {
                    cookies.set(btn.name, id);
                }
                window.location.reload();
            });
        });

    // activate tab selected in prefs
    let defpane;
    try {
        defpane = Tab.getOrCreateInstance(
            `#${localStorage.getItem("deftab")}-tab`);
    } catch (err) {
        defpane = Tab.getOrCreateInstance("#docinfo-tab");
    };
    defpane.show();
    document.activeElement.blur();

    if (localStorage.getItem("reflinks") != "refsection") {
        // make links to references go directly to the referenced doc
        document.querySelectorAll("a[href^='#'].xref")
            .forEach(ref => {
                const loc = document
                    .getElementById(ref.hash.substring(1))
                    .nextElementSibling;

                if (!loc ||
                    loc.tagName != "DD" ||
                    !loc.closest(".references")) {
                    return;
                }

                const url = loc.querySelector(
                    "a:not([href='']:last-of-type)");
                if (url) {
                    const rfc = url.href.match(/(rfc\d+)$/i);
                    if (rfc) {
                        // keep RFC links within the datatracker
                        const base = ref.href.match(
                            /^(.*\/)rfc\d+.*$/i);
                        if (base) {
                            ref.href = base[1] + rfc[1];
                            return;
                        }
                    }
                    ref.href = url.href;
                }
            });
    }

    // Rewrite these CSS properties so that the values are available for restyling.
    document.querySelectorAll("svg [style]").forEach(el => {
        // Push these CSS properties into their own attributes
        const SVG_PRESENTATION_ATTRS = new Set([
            'alignment-baseline', 'baseline-shift', 'clip', 'clip-path', 'clip-rule',
            'color', 'color-interpolation', 'color-interpolation-filters',
            'color-rendering', 'cursor', 'direction', 'display', 'dominant-baseline',
            'fill', 'fill-opacity', 'fill-rule', 'filter', 'flood-color',
            'flood-opacity', 'font-family', 'font-size', 'font-size-adjust',
            'font-stretch', 'font-style', 'font-variant', 'font-weight',
            'image-rendering', 'letter-spacing', 'lighting-color', 'marker-end',
            'marker-mid', 'marker-start', 'mask', 'opacity', 'overflow', 'paint-order',
            'pointer-events', 'shape-rendering', 'stop-color', 'stop-opacity',
            'stroke', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap',
            'stroke-linejoin', 'stroke-miterlimit', 'stroke-opacity', 'stroke-width',
            'text-anchor', 'text-decoration', 'text-rendering', 'unicode-bidi',
            'vector-effect', 'visibility', 'word-spacing', 'writing-mode',
        ]);

        // Simple CSS splitter: respects quoted strings and parens so semicolons
        // inside url(...) or "..." don't get treated as declaration boundaries.
        function parseDeclarations(styleText) {
            const decls = [];
            let buf = '';
            let inStr = false;
            let strChar = '';
            let escaped = false;
            let depth = 0;

            for (const ch of styleText) {
                if (inStr) {
                    if (escaped) {
                        escaped = false;
                    } else if (ch === '\\') {
                        escaped = true;
                    } else if (ch === strChar) {
                        inStr = false;
                    }
                } else if (ch === '"' || ch === "'") {
                    inStr = true;
                    strChar = ch;
                } else if (ch === '(') {
                    depth++;
                } else if (ch === ')') {
                    depth--;
                } else if (ch === ';' && depth === 0) {
                    const trimmed = buf.trim();
                    if (trimmed) {
                        decls.push(trimmed);
                    }
                    buf = '';
                    continue;
                }
                buf += ch;
            }
            const trimmed = buf.trim();
            if (trimmed) {
                decls.push(trimmed);
            }
            return decls;
        }

        const remainder = [];
        for (const decl of parseDeclarations(el.getAttribute('style'))) {
            const [prop, val] = decl.split(":", 2).map(v => v.trim());
            if (val && !/!important$/.test(val) && SVG_PRESENTATION_ATTRS.has(prop)) {
                el.setAttribute(prop, val);
            } else {
                remainder.push(decl);
            }
        }

        if (remainder.length > 0) {
            el.setAttribute('style', remainder.join('; '));
        } else {
            el.removeAttribute('style');
        }
    });
});
