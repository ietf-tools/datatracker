function getCookie(name){
  var cname = name + "=";
  var dc = document.cookie;
  if (dc.length > 0) {
    begin = dc.indexOf(cname);
    if (begin != -1) {
      begin += cname.length;
      end = dc.indexOf(";", begin);
      if (end == -1) end = dc.length;
        return unescape(dc.substring(begin, end));
    }
  }
  return null;
}

function setCookie(name, value, expires, path, domain, secure) {
  document.cookie = name + "=" + escape(value) +
  ((expires == null) ? "" : "; expires=" + expires) +
  ((path == null) ? "" : "; path=" + path) +
  ((domain == null) ? "" : "; domain=" + domain) +
  ((secure == null) ? "" : "; secure");
}

function delCookie (name,path,domain) {
  if (getCookie(name)) {
    document.cookie = name + "=" +
    ((path == null) ? "" : "; path=" + path) +
    ((domain == null) ? "" : "; domain=" + domain) +
    "; expires=Thu, 01-Jan-70 00:00:01 GMT";
  }
}

function setStyle (cstyleSheet) {
  var styleSheet = cstyleSheet;
  if(styleSheet=="0") { styleSheet = getCookie('styleSheet'); }
  var sheet1 = document.getElementById("sheet1");
  var sheet2 = document.getElementById("sheet2");
  var sheet3 = document.getElementById("sheet3");
  var sheet4 = document.getElementById("sheet4");
  sheet1.disabled=true;
  sheet2.disabled=true;
  sheet3.disabled=true;
  sheet4.disabled=true;
  if(styleSheet=="1") { sheet1.disabled=false; }
  else if(styleSheet=="2") { sheet2.disabled=false; }
  else if(styleSheet=="3") { sheet3.disabled=false; }
  else if(styleSheet=="4") { sheet4.disabled=false; }
  else { styleSheet="1"; sheet1.disabled=false; }
  setCookie('styleSheet',styleSheet,"Mon, 31-Dec-2035 23:59:59 GMT","/");
  }
