{% load url from future %}
var Dajaxice = {

    {% with module=dajaxice_config.modules top='top' %}
    {% include "dajaxice/dajaxice_function_loop.js" %}
    {% endwith %}

    {% for name, module in dajaxice_config.modules.submodules.items %}
    {% include "dajaxice/dajaxice_module_loop.js" %},
    {% endfor %}

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

    call: function(dajaxice_function, method, dajaxice_callback, argv, custom_settings)
    {
        var custom_settings = custom_settings || {},
            error_callback = Dajaxice.get_setting('default_exception_callback');

        if('error_callback' in custom_settings && typeof(custom_settings['error_callback']) == 'function'){
            error_callback = custom_settings['error_callback'];
        }

        var send_data = 'argv='+encodeURIComponent(JSON.stringify(argv)),
            oXMLHttpRequest = new XMLHttpRequest,
            endpoint = '{% url 'dajaxice-endpoint' %}'+dajaxice_function+'/';

        if(method == 'GET'){
            endpoint = endpoint + '?' + send_data;
        }
        oXMLHttpRequest.open(method, endpoint);
        oXMLHttpRequest.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
        oXMLHttpRequest.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        oXMLHttpRequest.setRequestHeader("X-CSRFToken", Dajaxice.get_cookie('{{ dajaxice_config.django_settings.CSRF_COOKIE_NAME }}'));
        oXMLHttpRequest.onreadystatechange = function() {
            if (this.readyState == XMLHttpRequest.DONE) {
                if(this.responseText == Dajaxice.EXCEPTION || !(this.status in Dajaxice.valid_http_responses())){
                    error_callback();
                }
                else{
                    var response;
                    try {
                        response = JSON.parse(this.responseText);
                    }
                    catch (exception) {
                        response = this.responseText;
                    }
                    dajaxice_callback(response);
                }
            }
        }
        if(method == 'POST'){
            oXMLHttpRequest.send(send_data);
        }
        else{
            oXMLHttpRequest.send();
        }
        return oXMLHttpRequest;
    },

    setup: function(settings)
    {
        this.settings = settings;
    },

    get_setting: function(key){
        if(this.settings == undefined || this.settings[key] == undefined){
            return Dajaxice.default_settings[key];
        }
        return this.settings[key];
    },

    valid_http_responses: function(){
        return {200: null, 301: null, 302: null, 304: null}
    },

    EXCEPTION: '{{ dajaxice_config.DAJAXICE_EXCEPTION }}',
    default_settings: {'default_exception_callback': function(){ console.log('Dajaxice: Something went wrong.')}}
};

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
{% if dajaxice_config.DAJAXICE_XMLHTTPREQUEST_JS_IMPORT %}
(function(){function n(){this._object=h&&!p?new h:new window.ActiveXObject("Microsoft.XMLHTTP");this._listeners=[]}function a(){return new n}function j(b){a.onreadystatechange&&a.onreadystatechange.apply(b);b.dispatchEvent({type:"readystatechange",bubbles:!1,cancelable:!1,timeStamp:new Date+0})}function o(b){try{b.responseText=b._object.responseText}catch(a){}try{var d;var g=b._object,c=g.responseXML,f=g.responseText;i&&(f&&c&&!c.documentElement&&g.getResponseHeader("Content-Type").match(/[^\/]+\/[^\+]+\+xml/))&&
(c=new window.ActiveXObject("Microsoft.XMLDOM"),c.async=!1,c.validateOnParse=!1,c.loadXML(f));d=c&&(i&&0!==c.parseError||!c.documentElement||c.documentElement&&"parsererror"==c.documentElement.tagName)?null:c;b.responseXML=d}catch(h){}try{b.status=b._object.status}catch(k){}try{b.statusText=b._object.statusText}catch(j){}}function l(b){b._object.onreadystatechange=new window.Function}var h=window.XMLHttpRequest,m=!!window.controllers,i=window.document.all&&!window.opera,p=i&&window.navigator.userAgent.match(/MSIE 7.0/);
a.prototype=n.prototype;m&&h.wrapped&&(a.wrapped=h.wrapped);a.UNSENT=0;a.OPENED=1;a.HEADERS_RECEIVED=2;a.LOADING=3;a.DONE=4;a.prototype.readyState=a.UNSENT;a.prototype.responseText="";a.prototype.responseXML=null;a.prototype.status=0;a.prototype.statusText="";a.prototype.priority="NORMAL";a.prototype.onreadystatechange=null;a.onreadystatechange=null;a.onopen=null;a.onsend=null;a.onabort=null;a.prototype.open=function(b,e,d,g,c){delete this._headers;arguments.length<3&&(d=true);this._async=d;var f=
this,h=this.readyState,k=null;if(i&&d){k=function(){if(h!=a.DONE){l(f);f.abort()}};window.attachEvent("onunload",k)}a.onopen&&a.onopen.apply(this,arguments);arguments.length>4?this._object.open(b,e,d,g,c):arguments.length>3?this._object.open(b,e,d,g):this._object.open(b,e,d);this.readyState=a.OPENED;j(this);this._object.onreadystatechange=function(){if(!m||d){f.readyState=f._object.readyState;o(f);if(f._aborted)f.readyState=a.UNSENT;else if(f.readyState==a.DONE){delete f._data;l(f);i&&d&&window.detachEvent("onunload",
k);h!=f.readyState&&j(f);h=f.readyState}}}};a.prototype.send=function(b){a.onsend&&a.onsend.apply(this,arguments);arguments.length||(b=null);if(b&&b.nodeType){b=window.XMLSerializer?(new window.XMLSerializer).serializeToString(b):b.xml;this._headers["Content-Type"]||this._object.setRequestHeader("Content-Type","application/xml")}this._data=b;a:{this._object.send(this._data);if(m&&!this._async){this.readyState=a.OPENED;for(o(this);this.readyState<a.DONE;){this.readyState++;j(this);if(this._aborted)break a}}}};
a.prototype.abort=function(){a.onabort&&a.onabort.apply(this,arguments);if(this.readyState>a.UNSENT)this._aborted=true;this._object.abort();l(this);this.readyState=a.UNSENT;delete this._data};a.prototype.getAllResponseHeaders=function(){return this._object.getAllResponseHeaders()};a.prototype.getResponseHeader=function(b){return this._object.getResponseHeader(b)};a.prototype.setRequestHeader=function(b,a){if(!this._headers)this._headers={};this._headers[b]=a;return this._object.setRequestHeader(b,
a)};a.prototype.addEventListener=function(a,e,d){for(var g=0,c;c=this._listeners[g];g++)if(c[0]==a&&c[1]==e&&c[2]==d)return;this._listeners.push([a,e,d])};a.prototype.removeEventListener=function(a,e,d){for(var g=0,c;c=this._listeners[g];g++)if(c[0]==a&&c[1]==e&&c[2]==d)break;c&&this._listeners.splice(g,1)};a.prototype.dispatchEvent=function(a){a={type:a.type,target:this,currentTarget:this,eventPhase:2,bubbles:a.bubbles,cancelable:a.cancelable,timeStamp:a.timeStamp,stopPropagation:function(){},preventDefault:function(){},
initEvent:function(){}};a.type=="readystatechange"&&this.onreadystatechange&&(this.onreadystatechange.handleEvent||this.onreadystatechange).apply(this,[a]);for(var e=0,d;d=this._listeners[e];e++)d[0]==a.type&&!d[2]&&(d[1].handleEvent||d[1]).apply(this,[a])};a.prototype.toString=function(){return"[object XMLHttpRequest]"};a.toString=function(){return"[XMLHttpRequest]"};window.Function.prototype.apply||(window.Function.prototype.apply=function(a,e){e||(e=[]);a.__func=this;a.__func(e[0],e[1],e[2],e[3],
e[4]);delete a.__func});window.XMLHttpRequest=a})();
{% endif %}

{% comment %}
/*
    http://www.json.org/json2.js Compiled with Google Closure
    This code was released under Public Domain by json.org , Thanks!
    I hope that in the future this code won't be neccessary, but today all browsers doesn't supports JSON.stringify().
*/
{% endcomment %}
{% if dajaxice_config.DAJAXICE_JSON2_JS_IMPORT %}
var JSON;JSON||(JSON={});
(function(){function k(a){return 10>a?"0"+a:a}function o(a){p.lastIndex=0;return p.test(a)?'"'+a.replace(p,function(a){var c=r[a];return"string"===typeof c?c:"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)})+'"':'"'+a+'"'}function m(a,j){var c,d,h,n,g=e,f,b=j[a];b&&("object"===typeof b&&"function"===typeof b.toJSON)&&(b=b.toJSON(a));"function"===typeof i&&(b=i.call(j,a,b));switch(typeof b){case "string":return o(b);case "number":return isFinite(b)?String(b):"null";case "boolean":case "null":return String(b);case "object":if(!b)return"null";
e+=l;f=[];if("[object Array]"===Object.prototype.toString.apply(b)){n=b.length;for(c=0;c<n;c+=1)f[c]=m(c,b)||"null";h=0===f.length?"[]":e?"[\n"+e+f.join(",\n"+e)+"\n"+g+"]":"["+f.join(",")+"]";e=g;return h}if(i&&"object"===typeof i){n=i.length;for(c=0;c<n;c+=1)"string"===typeof i[c]&&(d=i[c],(h=m(d,b))&&f.push(o(d)+(e?": ":":")+h))}else for(d in b)Object.prototype.hasOwnProperty.call(b,d)&&(h=m(d,b))&&f.push(o(d)+(e?": ":":")+h);h=0===f.length?"{}":e?"{\n"+e+f.join(",\n"+e)+"\n"+g+"}":"{"+f.join(",")+
"}";e=g;return h}}"function"!==typeof Date.prototype.toJSON&&(Date.prototype.toJSON=function(){return isFinite(this.valueOf())?this.getUTCFullYear()+"-"+k(this.getUTCMonth()+1)+"-"+k(this.getUTCDate())+"T"+k(this.getUTCHours())+":"+k(this.getUTCMinutes())+":"+k(this.getUTCSeconds())+"Z":null},String.prototype.toJSON=Number.prototype.toJSON=Boolean.prototype.toJSON=function(){return this.valueOf()});var q=/[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,
p=/[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,e,l,r={"\b":"\\b","\t":"\\t","\n":"\\n","\f":"\\f","\r":"\\r",'"':'\\"',"\\":"\\\\"},i;"function"!==typeof JSON.stringify&&(JSON.stringify=function(a,j,c){var d;l=e="";if(typeof c==="number")for(d=0;d<c;d=d+1)l=l+" ";else typeof c==="string"&&(l=c);if((i=j)&&typeof j!=="function"&&(typeof j!=="object"||typeof j.length!=="number"))throw Error("JSON.stringify");return m("",{"":a})});
"function"!==typeof JSON.parse&&(JSON.parse=function(a,e){function c(a,d){var g,f,b=a[d];if(b&&typeof b==="object")for(g in b)if(Object.prototype.hasOwnProperty.call(b,g)){f=c(b,g);f!==void 0?b[g]=f:delete b[g]}return e.call(a,d,b)}var d,a=String(a);q.lastIndex=0;q.test(a)&&(a=a.replace(q,function(a){return"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)}));if(/^[\],:{}\s]*$/.test(a.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g,"@").replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,
"]").replace(/(?:^|:|,)(?:\s*\[)+/g,""))){d=eval("("+a+")");return typeof e==="function"?c({"":d},""):d}throw new SyntaxError("JSON.parse");})})();
{% endif %}
