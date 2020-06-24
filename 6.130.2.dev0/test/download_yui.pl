# Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

unless (-d 'images/yui' && -d 'js/yui' && -d 'css/yui') {
    die "run this script under /static/\n";
}

# From: http://developer.yahoo.com/yui/articles/hosting/?button&connection&container&cookie&event&fonts&menu&tabview&yahoo&MIN&norollup

$css_url = 'http://yui.yahooapis.com/combo?2.8.0r4/build/fonts/fonts-min.css&2.8.0r4/build/container/assets/skins/sam/container.css&2.8.0r4/build/menu/assets/skins/sam/menu.css&2.8.0r4/build/button/assets/skins/sam/button.css&2.8.0r4/build/tabview/assets/skins/sam/tabview.css';
$js_url = 'http://yui.yahooapis.com/combo?2.8.0r4/build/yahoo/yahoo-min.js&2.8.0r4/build/event/event-min.js&2.8.0r4/build/connection/connection-min.js&2.8.0r4/build/dom/dom-min.js&2.8.0r4/build/container/container-min.js&2.8.0r4/build/menu/menu-min.js&2.8.0r4/build/element/element-min.js&2.8.0r4/build/button/button-min.js&2.8.0r4/build/cookie/cookie-min.js&2.8.0r4/build/tabview/tabview-min.js';

$cmd = "wget '$css_url' -O css/yui/yui-original.css";
print $cmd; system $cmd;
$cmd = "wget '$js_url' -O js/yui/yui.js";
print $cmd; system $cmd;

open(I, "css/yui/yui-original.css") || die "yui-original.css: $!\n";
open(O, ">css/yui/yui.css") || die "yui.css: $!\n";
$/ = '(';
%done = ();
while ($_ = <I>) {
    if (m!(http://[^/]+)(/.*?/)([^)./]+)(.png)!) {
	if (!exists $done{"$3$4"}) {
	    $cmd = "wget -nd $1$2$3$4 -O images/yui/$3$4\n";
	    print $cmd; system $cmd;
	    $done{"$3$4"} = 1;
	}
	s!(http://[^/]+)(/.*?/)([^)./]+)(.png)!/images/yui/$3$4!;
    }
    print O ;
}
close I;
close O;
unlink "css/yui/yui-original.css";
