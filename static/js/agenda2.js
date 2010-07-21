// Based on agenda.js written by Tony Hansen.

// Portion Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
// All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
//
//  * Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//
//  * Redistributions in binary form must reproduce the above
//    copyright notice, this list of conditions and the following
//    disclaimer in the documentation and/or other materials provided
//    with the distribution.
//
//  * Neither the name of the Nokia Corporation and/or its
//    subsidiary(-ies) nor the names of its contributors may be used
//    to endorse or promote products derived from this software
//    without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

function setAgendaColor(color) {
    IETF.agendaPalette.hide();  
    document.getElementById(IETF.agendaRow).className="bg"+color;  
    if (color == 'none') {
	YAHOO.util.Cookie.removeSub("ietf-agenda-colors", IETF.agendaRow);
    } else {
	var twoMonths = new Date(new Date().getTime() + 60*24*60*60*1000);
	YAHOO.util.Cookie.setSub("ietf-agenda-colors", IETF.agendaRow, color, { expires:twoMonths });
    }
}
function createPalette() {
    IETF.agendaPalette = new YAHOO.widget.Overlay("ietf-agenda-palette", { constraintoviewport:true, visible:false } ); 
    var body = '<table class="ietf-agenda-palette"><tr><td colspan="4">Select a color for this line</td></tr>';
    var c = ['aqua', 'blue', 'fuchsia', 'gray', 'green', 'lime',
        'maroon', 'navy', 'olive', 'purple', 'red', 'silver',
        'teal', 'white', 'yellow', 'black'];
    for (var i = 0; i < c.length; i++) {
        if ((i%4) == 0) { body += "<tr>" }
        body += '<td class="bg'+c[i]+'"><a href=\'javascript:setAgendaColor("'+c[i]+'");\'>'+c[i]+'</a></td>';
        if ((i%4) == 3) { body += "</tr>" }
    }
    body += '<tr><td class="bgnone" colspan="4"><a href="javascript:setAgendaColor(\'none\');">none</a></td></tr></table>';
    IETF.agendaPalette.setBody(body);
    IETF.agendaPalette.render(document.body); 
}
function pickAgendaColor(row, place) {
    if (!IETF.agendaPalette) {
        createPalette();
    }
    IETF.agendaRow = row;
    IETF.agendaPalette.cfg.setProperty("context", [place, "tl", "tl"]);
    IETF.agendaPalette.show();
}
function updateAgendaColors() {
    var colors = YAHOO.util.Cookie.getSubs("ietf-agenda-colors");
    for (var k in colors) {  
	document.getElementById(k).className="bg"+colors[k];
    }
}
