import $ from "jquery";
import select2 from "select2";

select2($);

$.fn.select2.defaults.set("allowClear", true);
$.fn.select2.defaults.set("dropdownCssClass", ":all:");
$.fn.select2.defaults.set("minimumInputLength", 2);
$.fn.select2.defaults.set("theme", "bootstrap-5");
$.fn.select2.defaults.set("width", "off");
$.fn.select2.defaults.set("escapeMarkup", function (m) {
    return m;
});