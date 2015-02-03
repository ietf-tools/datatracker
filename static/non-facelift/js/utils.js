function showModalBox(content, callback) {
    content = $(content);

    // make sure previous one is gone
    $("#modal-overlay").remove();

    // the url(data:...) part is backwards compatibility for non-rgba
    // supporting browsers (IE 8) - it's a 2 pixel black PNG with
    // opacity 50%
    var overlay = $('<div id="modal-overlay" style="position:fixed;z-index:100;top:0;left:0;height:100%;width:100%;background:transparent url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAQAAABeK7cBAAAACXBIWXMAAAsTAAALEwEAmpwYAAAADUlEQVQIHWNgqGeoBwACAQD/+EjsGgAAAABJRU5ErkJggg==);background:rgba(0,0,0,0.5);"></div>');
    var box = $('<div id="modal-box" style="position:absolute;left:50%;top:50%"></div>');

    box.append(content);
    overlay.append(box);

    box.click(function (e) {
        e.stopPropagation();
    });
    overlay.click(closeModalBox);
    box.find(".button.close").click(function (e) {
        e.preventDefault();
        closeModalBox();
    });
    overlay.keydown(function (e) {
        if (e.which == 27)
            closeModalBox();
    });

    $("body").append(overlay);

    var w = content.outerWidth() || 400;
    var h = content.outerHeight() || 300;
    box.css({ "margin-left": -parseInt(w/2), "margin-top": -parseInt(h/2) });

    content.focus();

    if (callback)
        callback();
}

function closeModalBox() {
    $("#modal-overlay").remove();
}
