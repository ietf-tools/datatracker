require('datatables.net')(window, $);
require('datatables.net-bs5')(window, $);

// Disable datatable paging by default.
$.extend($.fn.dataTable.defaults, {
  info : false,
  paging : false,
  order: [],
  "search": {
    "caseInsensitive": true
  }
});

$(document).ready(function() { $(".tablesorter").DataTable(); });