// Copyright The IETF Trust 2021, All Rights Reserved

/*
 Javascript support for the materials modal rendered by session_agenda_include.html

 Requires jquery be loaded
 */

var agenda_materials; // public interface

(function() {
  'use strict';
  /**
   * Retrieve and display materials for a session
   *
   * If output_elt exists and has a "data-src" attribute, retrieves the document
   * from that URL and displays under output_elt. Handles text/plain, text/markdown,
   * and text/html.
   *
   * @param output_elt Element, probably a div, to hold the output
   */
  function retrieve_session_materials(output_elt) {
    if (!output_elt) {return;}
    output_elt = $(output_elt);
    var data_src = output_elt.attr("data-src");
    if (!data_src) {
      output_elt.html("<p>Error: missing data-src attribute</p>");
    } else {
      output_elt.html("<p>Loading " + data_src + "...</p>");
      var outer_xhr = $.ajax({url:data_src,headers:{'Accept':'text/plain;q=0.8,text/html;q=0.9'}})
      outer_xhr.done(function(data, status, xhr) {
        var t = xhr.getResponseHeader("content-type");
        if (!t) {
          data = "<p>Error retrieving " + data_src
            + ": Missing content-type in response header</p>";
        } else if (t.indexOf("text/plain") > -1) {
          data = "<pre class='agenda'>" + data + "</pre>";
        } else if (t.indexOf("text/markdown") > -1) {
          data = "<pre class='agenda'>" + data + "</pre>";
        } else if(t.indexOf("text/html") > -1) {
          // nothing to do here
        } else {
          data = "<p>Unknown type: " + xhr.getResponseHeader("content-type") + "</p>";
        }
        output_elt.html(data);
      }).fail(function() {
        output_elt.html("<p>Error retrieving " + data_src
          + ": (" + outer_xhr.status.toString() + ") "
          + outer_xhr.statusText + "</p>");
      })
    }
  }

  /**
   * Retrieve contents of a session materials modal
   *
   * Expects output_elt to exist and have a "data-src" attribute. Retrieves the
   * contents of that URL, then attempts to populate the .agenda-frame and
   * .minutes-frame elements.
   *
   * @param output_elt Element, probably a div, to hold the output
   */
  function retrieve_session_modal(output_elt) {
    if (!output_elt) {return;}
    output_elt = $(output_elt);
    var data_src = output_elt.attr("data-src");
    if (!data_src) {
      output_elt.html("<p>Error: missing data-src attribute</p>");
    } else {
      output_elt.html("<p>Loading...</p>");
      $.get(data_src).done(function(data) {
        output_elt.html(data);
        retrieve_session_materials(output_elt.find(".agenda-frame"));
        retrieve_session_materials(output_elt.find(".minutes-frame"));
      });
    }
  }

  $(document).ready(function() {
    $(".modal").on("show.bs.modal", function () {
      retrieve_session_modal($(this).find(".session-materials"));
    });
  })
})();