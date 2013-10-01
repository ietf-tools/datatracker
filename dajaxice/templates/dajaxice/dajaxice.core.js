var Dajaxice = {
    {% for module in dajaxice_js_functions %}
        {% include "dajaxice/dajaxice_core_loop.js" %}
        {% endfor %}{% ifnotequal dajaxice_js_functions|length 0 %},{% endifnotequal %}
    
    get_cookie: function(name)
    {
        var cookieValue = null;
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].toString().replace(/^\s+/, "").replace(/\s+$/, "");
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },
            
    call: function(dajaxice_function, dajaxice_callback, argv, exception_callback)
    {
        var send_data = [];
        var is_callback_a_function = (typeof(dajaxice_callback) == 'function');
        if(!is_callback_a_function){
            alert("dajaxice_callback should be a function since dajaxice 0.2")
        }
        
        if(exception_callback==undefined || typeof(dajaxice_callback) != 'function'){
            exception_callback = this.get_setting('default_exception_callback');
        }
        
        send_data.push('argv='+encodeURIComponent(JSON.stringify(argv)));
        send_data = send_data.join('&');
        var oXMLHttpRequest = new XMLHttpRequest;
        oXMLHttpRequest.open('POST', '/{{DAJAXICE_URL_PREFIX}}/'+dajaxice_function+'/');
        oXMLHttpRequest.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        oXMLHttpRequest.setRequestHeader("X-CSRFToken",Dajaxice.get_cookie('csrftoken'));
        oXMLHttpRequest.onreadystatechange = function() {
            if (this.readyState == XMLHttpRequest.DONE) {
                if(this.responseText == Dajaxice.EXCEPTION){
                    exception_callback();
                }
                else{
                    try{
                        dajaxice_callback(JSON.parse(this.responseText));
                    }
                    catch(exception){
                        dajaxice_callback(this.responseText);
                    }
                }
            }
        }
        oXMLHttpRequest.send(send_data);
    },
    
    setup: function(settings)
    {
        this.settings = settings;
    },
    
    get_setting: function(key){
        if(this.settings == undefined || this.settings[key] == undefined){
            return this.default_settings[key];
        }
        return this.settings[key];
    },
    
    default_exception_callback: function(data){
        alert('Something goes wrong');
    }
};

Dajaxice.EXCEPTION = '{{ DAJAXICE_EXCEPTION }}';
Dajaxice.default_settings = {'default_exception_callback': Dajaxice.default_exception_callback}

window['Dajaxice'] = Dajaxice;

{% comment %}
/*
    XMLHttpRequest.js Compiled with Google Closure
    
    XMLHttpRequest.js Copyright (C) 2008 Sergey Ilinsky (http://www.ilinsky.com)
    
    This work is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; either version 2.1 of the License, or
    (at your option) any later version.
    
    This work is distributed in the hope that it will be useful,
    but without any warranty; without even the implied warranty of
    merchantability or fitness for a particular purpose. See the
    GNU Lesser General Public License for more details.
    
    You should have received a copy of the GNU Lesser General Public License
    along with this library; if not, write to the Free Software Foundation, Inc.,
    59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
*/
{% endcomment %}
{% if DAJAXICE_XMLHTTPREQUEST_JS_IMPORT %}
(function(){function b(){this._object=i?new i:new window.ActiveXObject("Microsoft.XMLHTTP");this._listeners=[]}function k(a){b.onreadystatechange&&b.onreadystatechange.apply(a);a.dispatchEvent({type:"readystatechange",bubbles:false,cancelable:false,timeStamp:new Date+0})}function p(a){var c=a.responseXML,d=a.responseText;if(h&&d&&c&&!c.documentElement&&a.getResponseHeader("Content-Type").match(/[^\/]+\/[^\+]+\+xml/)){c=new window.ActiveXObject("Microsoft.XMLDOM");c.async=false;c.validateOnParse=false;
c.loadXML(d)}if(c)if(h&&c.parseError!=0||!c.documentElement||c.documentElement&&c.documentElement.tagName=="parsererror")return null;return c}function o(a){try{a.responseText=a._object.responseText}catch(c){}try{a.responseXML=p(a._object)}catch(d){}try{a.status=a._object.status}catch(g){}try{a.statusText=a._object.statusText}catch(e){}}function l(a){a._object.onreadystatechange=new window.Function}var i=window.XMLHttpRequest,j=!!window.controllers,h=window.document.all&&!window.opera;if(j&&i.wrapped)b.wrapped=
i.wrapped;b.UNSENT=0;b.OPENED=1;b.HEADERS_RECEIVED=2;b.LOADING=3;b.DONE=4;b.prototype.readyState=b.UNSENT;b.prototype.responseText="";b.prototype.responseXML=null;b.prototype.status=0;b.prototype.statusText="";b.prototype.onreadystatechange=null;b.onreadystatechange=null;b.onopen=null;b.onsend=null;b.onabort=null;b.prototype.open=function(a,c,d,g,e){delete this._headers;if(arguments.length<3)d=true;this._async=d;var f=this,m=this.readyState,n;if(h&&d){n=function(){if(m!=b.DONE){l(f);f.abort()}};window.attachEvent("onunload",
n)}b.onopen&&b.onopen.apply(this,arguments);if(arguments.length>4)this._object.open(a,c,d,g,e);else arguments.length>3?this._object.open(a,c,d,g):this._object.open(a,c,d);if(!j&&!h){this.readyState=b.OPENED;k(this)}this._object.onreadystatechange=function(){if(!(j&&!d)){f.readyState=f._object.readyState;o(f);if(f._aborted)f.readyState=b.UNSENT;else{if(f.readyState==b.DONE){l(f);h&&d&&window.detachEvent("onunload",n)}m!=f.readyState&&k(f);m=f.readyState}}}};b.prototype.send=function(a){b.onsend&&b.onsend.apply(this,
arguments);if(a&&a.nodeType){a=window.XMLSerializer?(new window.XMLSerializer).serializeToString(a):a.xml;this._headers["Content-Type"]||this._object.setRequestHeader("Content-Type","application/xml")}this._object.send(a);if(j&&!this._async){this.readyState=b.OPENED;for(o(this);this.readyState<b.DONE;){this.readyState++;k(this);if(this._aborted)return}}};b.prototype.abort=function(){b.onabort&&b.onabort.apply(this,arguments);if(this.readyState>b.UNSENT)this._aborted=true;this._object.abort();l(this)};
b.prototype.getAllResponseHeaders=function(){return this._object.getAllResponseHeaders()};b.prototype.getResponseHeader=function(a){return this._object.getResponseHeader(a)};b.prototype.setRequestHeader=function(a,c){if(!this._headers)this._headers={};this._headers[a]=c;return this._object.setRequestHeader(a,c)};b.prototype.addEventListener=function(a,c,d){for(var g=0,e;e=this._listeners[g];g++)if(e[0]==a&&e[1]==c&&e[2]==d)return;this._listeners.push([a,c,d])};b.prototype.removeEventListener=function(a,
c,d){for(var g=0,e;e=this._listeners[g];g++)if(e[0]==a&&e[1]==c&&e[2]==d)break;e&&this._listeners.splice(g,1)};b.prototype.dispatchEvent=function(a){a={type:a.type,target:this,currentTarget:this,eventPhase:2,bubbles:a.bubbles,cancelable:a.cancelable,timeStamp:a.timeStamp,stopPropagation:function(){},preventDefault:function(){},initEvent:function(){}};if(a.type=="readystatechange"&&this.onreadystatechange)(this.onreadystatechange.handleEvent||this.onreadystatechange).apply(this,[a]);for(var c=0,d;d=
this._listeners[c];c++)if(d[0]==a.type&&!d[2])(d[1].handleEvent||d[1]).apply(this,[a])};b.prototype.toString=function(){return"[object XMLHttpRequest]"};b.toString=function(){return"[XMLHttpRequest]"};if(!window.Function.prototype.apply)window.Function.prototype.apply=function(a,c){c||(c=[]);a.__func=this;a.__func(c[0],c[1],c[2],c[3],c[4]);delete a.__func};window.XMLHttpRequest=b})();
{% endif %}

{% comment %}
/*
    http://www.json.org/json2.js Compiled with Google Closure
    This code was released under Public Domain by json.org , Thanks!
    I hope that in the future this code won't be neccessary, but today all browsers doesn't supports JSON.stringify().
*/
{% endcomment %}
{% if DAJAXICE_JSON2_JS_IMPORT %}
if(!this.JSON)this.JSON={};
(function(){function k(a){return a<10?"0"+a:a}function n(a){o.lastIndex=0;return o.test(a)?'"'+a.replace(o,function(c){var d=q[c];return typeof d==="string"?d:"\\u"+("0000"+c.charCodeAt(0).toString(16)).slice(-4)})+'"':'"'+a+'"'}function l(a,c){var d,f,i=g,e,b=c[a];if(b&&typeof b==="object"&&typeof b.toJSON==="function")b=b.toJSON(a);if(typeof j==="function")b=j.call(c,a,b);switch(typeof b){case "string":return n(b);case "number":return isFinite(b)?String(b):"null";case "boolean":case "null":return String(b);case "object":if(!b)return"null";
g+=m;e=[];if(Object.prototype.toString.apply(b)==="[object Array]"){f=b.length;for(a=0;a<f;a+=1)e[a]=l(a,b)||"null";c=e.length===0?"[]":g?"[\n"+g+e.join(",\n"+g)+"\n"+i+"]":"["+e.join(",")+"]";g=i;return c}if(j&&typeof j==="object"){f=j.length;for(a=0;a<f;a+=1){d=j[a];if(typeof d==="string")if(c=l(d,b))e.push(n(d)+(g?": ":":")+c)}}else for(d in b)if(Object.hasOwnProperty.call(b,d))if(c=l(d,b))e.push(n(d)+(g?": ":":")+c);c=e.length===0?"{}":g?"{\n"+g+e.join(",\n"+g)+"\n"+i+"}":"{"+e.join(",")+"}";
g=i;return c}}if(typeof Date.prototype.toJSON!=="function"){Date.prototype.toJSON=function(){return isFinite(this.valueOf())?this.getUTCFullYear()+"-"+k(this.getUTCMonth()+1)+"-"+k(this.getUTCDate())+"T"+k(this.getUTCHours())+":"+k(this.getUTCMinutes())+":"+k(this.getUTCSeconds())+"Z":null};String.prototype.toJSON=Number.prototype.toJSON=Boolean.prototype.toJSON=function(){return this.valueOf()}}var p=/[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,
o=/[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,g,m,q={"\u0008":"\\b","\t":"\\t","\n":"\\n","\u000c":"\\f","\r":"\\r",'"':'\\"',"\\":"\\\\"},j;if(typeof JSON.stringify!=="function")JSON.stringify=function(a,c,d){var f;m=g="";if(typeof d==="number")for(f=0;f<d;f+=1)m+=" ";else if(typeof d==="string")m=d;if((j=c)&&typeof c!=="function"&&(typeof c!=="object"||typeof c.length!=="number"))throw new Error("JSON.stringify");return l("",
{"":a})};if(typeof JSON.parse!=="function")JSON.parse=function(a,c){function d(f,i){var e,b,h=f[i];if(h&&typeof h==="object")for(e in h)if(Object.hasOwnProperty.call(h,e)){b=d(h,e);if(b!==undefined)h[e]=b;else delete h[e]}return c.call(f,i,h)}p.lastIndex=0;if(p.test(a))a=a.replace(p,function(f){return"\\u"+("0000"+f.charCodeAt(0).toString(16)).slice(-4)});if(/^[\],:{}\s]*$/.test(a.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g,"@").replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,
"]").replace(/(?:^|:|,)(?:\s*\[)+/g,""))){a=eval("("+a+")");return typeof c==="function"?d({"":a},""):a}throw new SyntaxError("JSON.parse");}})();
{% endif %}