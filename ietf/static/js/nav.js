function make_nav() {
    const nav = document.createElement("nav");
    nav.classList.add("nav-pills", "ps-3", "flex-column");
    return nav;
}

export function populate_nav(nav, heading_selector, start_level, classes) {
    // Extract section headings from document
    const headings = document.querySelectorAll(heading_selector);

    let nav_stack = [nav];
    let cur_level = 0;
    let n = 0;

    headings.forEach(el => {
        let level = el.tagName.charAt(el.tagName.length - 1) -
            start_level;

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
        link.classList.add("nav-link", "ps-1", "d-flex", "hyphenate", classes);

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
}
