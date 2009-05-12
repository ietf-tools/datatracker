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

function showBallot(draftName, trackerId) {

    var handleEditPosition = function() {
        IETF.ballotDialog.hide();
        var tid = document.getElementById("doc_ballot_dialog_id").innerHTML;
        window.open("https://datatracker.ietf.org/cgi-bin/idtracker.cgi?command=open_ballot&id_document_tag="+tid);
    }; 
    var handleClose = function() {
        IETF.ballotDialog.hide();
    };
    var el;

    if (!IETF.ballotDialog) {
        el = document.createElement("div");
        el.innerHTML = '<div id="doc_ballot_dialog" class="mydialog" style="visibility:hidden;"><div class="hd">Positions for <span id="doc_ballot_dialog_name">draft-ietf-foo-bar</span><span id="doc_ballot_dialog_id" style="display:none;"></span></div><div class="bd">  <div id="doc_ballot_dialog_12" style="overflow-y:scroll; height:500px;"></div>   </div></div>';
        document.getElementById("db-extras").appendChild(el);

        var buttons = [{text:"Close", handler:handleClose, isDefault:true}];
	buttons.unshift({text:"Edit Position", handler:handleEditPosition});
        IETF.ballotDialog = new YAHOO.widget.Dialog("doc_ballot_dialog", {
            visible:false, draggable:false, close:true, modal:true,
            width:"850px", fixedcenter:true, constraintoviewport:true,
            buttons: buttons});
        IETF.ballotDialog.render();
    }
    document.getElementById("doc_ballot_dialog_name").innerHTML = draftName;
    document.getElementById("doc_ballot_dialog_id").innerHTML = trackerId;

    IETF.ballotDialog.show();

    el = document.getElementById("doc_ballot_dialog_12");
    el.innerHTML = "Loading...";
    YAHOO.util.Connect.asyncRequest('GET', 
          "/doc/"+draftName+"/_ballot.data",
          { success: function(o) { el.innerHTML = (o.responseText !== undefined) ? o.responseText : "?"; }, 
            failure: function(o) { el.innerHTML = "Error: "+o.status+" "+o.statusText; },
            argument: null
   	  }, null);
}

function signIn() {
   document.cookie = "mytestcookie=worked; path=/";
   if (document.cookie.length == 0) {
      alert("You must enable cookies to sign in");
      return;
   }
   // Initialize Django session cookie
   YAHOO.util.Connect.asyncRequest('GET', '/account/login/', {}, null);

   var onSuccess = function(o) {
       if (o.status != 200) {
           document.getElementById("signin_msg").innerHTML = o.statusText;
       } else {
           var t = o.responseText;
           if (t.search("Please enter a correct username and password") >= 0) {
               document.getElementById("signin_msg").innerHTML = "The username or password you entered is incorrect.";
           } else if (t.search("Username and Email Address for legacy tools") >= 0) {
               IETF.signinDialog.hide();
               window.location.reload();
           } else {
               alert(t);
               document.getElementById("signin_msg").innerHTML = "Internal error?";
           }
       }
    };
    var onFailure = function(o) {
        document.getElementById("signin_msg").innerHTML = o.statusText;
    };
    var handleOk = function() {
        document.getElementById("signin_msg").innerHTML = "Signing in...";
        document.cookie = "testcookie=worked; path=/";
        YAHOO.util.Connect.setForm(document.signin_form); 
        YAHOO.util.Connect.asyncRequest('POST',
            '/account/login/', {success:onSuccess,failure:onFailure});
        return false;
    };
    if (!IETF.signinDialog) {
        var dialog = new YAHOO.widget.Panel("signin_dlg", {
            draggable:false, modal:true,
            width:"350px", fixedcenter:true, constraintoviewport:true });
        var kl1 = new YAHOO.util.KeyListener(document, { keys: 27 }, function() { dialog.cancel();}); 
	var kl2 = new YAHOO.util.KeyListener("signin_password", { keys: 13 }, function () {  } );
        dialog.cfg.queueProperty("keylisteners", [kl1,kl2]);
        dialog.render();
        YAHOO.util.Event.addListener(document.signin_form, "submit", handleOk);
        var cancelButton = new YAHOO.widget.Button("signin_button2");
        cancelButton.on("click", function() {dialog.hide();});
        IETF.signinDialog = dialog;
    }
    document.getElementById("signin_msg").innerHTML = "";
    IETF.signinDialog.show();
}
function signOut() {
    YAHOO.util.Connect.asyncRequest('GET', '/account/logout/', { success: function(o) { window.location.reload(); } }, null);
};
