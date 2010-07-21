// Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

function showBallot(draftName, editPositionUrl) {
    var handleEditPosition = function() {
        IETF.ballotDialog.hide();
        window.location = editPositionUrl;
    }; 
    var handleClose = function() {
        IETF.ballotDialog.hide();
    };
    var el;

    if (!IETF.ballotDialog) {
        el = document.createElement("div");
        el.innerHTML = '<div id="ballot_dialog" style="visibility:hidden;"><div class="hd">Positions for <span id="ballot_dialog_name">draft-ietf-foo-bar</span></span></div><div class="bd">  <div id="ballot_dialog_body" style="overflow-y:scroll; height:500px;"></div>   </div></div>';
        document.getElementById("ietf-extras").appendChild(el);

        var buttons = [{text:"Close", handler:handleClose, isDefault:true}];
	if (("Area_Director" in IETF.user_groups) ||
	    ("Secretariat" in IETF.user_groups)) {
	    buttons.unshift({text:"Edit Position", handler:handleEditPosition});
	}
	var kl = [new YAHOO.util.KeyListener(document, {keys:27}, handleClose)]						 
        IETF.ballotDialog = new YAHOO.widget.Dialog("ballot_dialog", {
            visible:false, draggable:false, close:true, modal:true,
            width:"860px", fixedcenter:true, constraintoviewport:true,
            buttons: buttons, keylisteners:kl});
        IETF.ballotDialog.render();
    }
    document.getElementById("ballot_dialog_name").innerHTML = draftName;

    IETF.ballotDialog.show();

    el = document.getElementById("ballot_dialog_body");
    el.innerHTML = "Loading...";
    YAHOO.util.Connect.asyncRequest('GET', 
          "/doc/"+draftName+"/_ballot.data",
          { success: function(o) { el.innerHTML = (o.responseText !== undefined) ? o.responseText : "?"; }, 
            failure: function(o) { el.innerHTML = "Error: "+o.status+" "+o.statusText; },
            argument: null
   	  }, null);
}
function editBallot(editPositionUrl) {
    window.open(editPositionUrl);
}
