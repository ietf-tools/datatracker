import debounce from "lodash/debounce";

function make_nav() {
    const nav = document.createElement("nav");
    nav.classList.add("nav-pills", "ps-3", "flex-column");
    return nav;
}

function get_level(el) {
    let h;
    if (el.tagName.match(/^h\d/i)) {
        h = el.tagName
    } else {
        el.classList.forEach(cl => {
            if (cl.match(/^h\d/i)) {
                h = cl;
                return;
            }
        });
    }
    return h.charAt(h.length - 1);
}

export function populate_nav(nav, headings, classes) {
    // Extract section headings from document
    const min_level = Math.min(...Array.from(headings)
        .map(get_level));

    let nav_stack = [nav];
    let cur_level = 0;
    let n = 0;

    headings.forEach(el => {
        const level = get_level(el) - min_level;

        if (level < cur_level) {
            while (level < cur_level) {
                let nav = nav_stack.pop();
                cur_level--;
                nav_stack[cur_level].appendChild(nav);
            }
        } else {
            while (level > cur_level) {
                nav_stack.push(make_nav());
                cur_level++;
            }
        }

        const link = document.createElement("a");
        link.classList.add("nav-link", "ps-1", "d-flex", "hyphenate",
            classes);

        if (!el.id) {
            el.id = `autoid-${++n}`;
        }
        link.href = `#${el.id}`;

        const words = el.innerText.split(/\s+/);
        let nr = "";
        if (words[0].includes(".")) {
            nr = words.shift();
        } else if (words.length > 1 && words[1].includes(".")) {
            nr = words.shift() + " " + words.shift();
            nr = nr.replace(/\s*Appendix\s*/, "");
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

    // Chrome apparently wants this debounced to something >10ms,
    // otherwise the main view doesn't scroll?
    document.addEventListener("scroll", debounce(function () {
        const items = nav.querySelectorAll(".active");
        const item = [...items].pop();
        if (item) {
            item.scrollIntoView({
                block: "center",
                behavior: "smooth"
            });
        }
    }, 100));
}
