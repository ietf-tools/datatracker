/*Copyright (c) 2019 IETF Trust. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/
async function addMetadata() {

  // Copy all CSS rules for "#identifiers" to "#metadata"
    try {
        const cssRules = document.styleSheets[0].cssRules;
        for (let i = 0; i < cssRules.length; i++) {
            if (/#identifiers/.exec(cssRules[i].selectorText)) {
                const rule = cssRules[i].cssText.
                             replace('#identifiers','#external-updates');
                document.styleSheets[0].
                        insertRule(rule, document.styleSheets[0].cssRules.length);
            }
        }
    } catch (e) {
        console.log(e);
    }

    function getMeta(metaName) {
        const metas = document.getElementsByTagName('meta');

        for (let i = 0; i < metas.length; i++) {
            if (metas[i].getAttribute('name') === metaName) {
                return metas[i].getAttribute('content');
            }
        }

        return '';
    }

  // Retrieve the "metadata" element from the document
    const div = document.getElementById('external-metadata');
    if (!div) {
        console.log("Could not locate metadata <div> element");
        return;
    }

  // Insert the external metadata block
    try {

        var jsonfile;
        var metadata = '';
        var rfcnum = getMeta('rfc.number');
        if (rfcnum) {
            jsonfile = 'https://www.rfc-editor.org/rfc/rfc'+rfcnum+'.json';
            try {
                const response = await fetch(jsonfile);
                metadata = (await response.json());
            } catch(e) {
                if (document.URL.indexOf('html') >= 0){
                    jsonfile = document.URL.replace(/html$/,'json');
                } else {
                    jsonfile = document.URL + '.json';
                }
                const response = await fetch(jsonfile);
                metadata = (await response.json());
            }
        }
        if (! metadata) {
            return;
        } 
        div.style.display = 'block';
        
    //const base_url = 'https//www.rfc-editor.org';
        const base_url = '';
        const datatracker_base= 'https://datatracker.ietf.org/doc';
        const ipr_base ='https://datatracker.ietf.org/ipr/search';
        const info_page = 'https://www.rfc-editor.org/info';
    //const base_url = 'http://pubtest.rfc-editor.org';


        const doc_id = metadata['doc_id'].toLowerCase();
        const doc_id_str = metadata['doc_id'].slice(0,3).toLowerCase();
        const doc_id_num = metadata['doc_id'].slice(3).replace(/^0+/,''); 

        const label = {
            'status': 'Status',
            'obsoletes': 'Obsoletes',
            'obsoleted_by': 'Obsoleted By',
            'updates': 'Updates',
            'updated_by': 'Updated By',
            'see_also': 'See Also',
            'errata_url': 'Errata',
        };

        let metadataHTML = "<dl style='overflow:hidden' id='external-updates'>";
        ['status', 'obsoletes', 'obsoleted_by', 'updates',
         'updated_by', 'see_also', 'errata_url'].forEach(key => {
      //if (metadata[key]){
            if (key == 'status'){
                metadata[key] = metadata[key].toLowerCase();
                var status_array = metadata[key].split(" ");
                var sLen = status_array.length;
                var status_string="",s_counter =1;
                for (let i=0;i<sLen;i++){
                    if (s_counter < sLen){
                        status_string = status_string + capitalizeFirstLetter(status_array[i]) + " ";
                    }
                    else {

                        status_string = status_string + capitalizeFirstLetter(status_array[i]) ;
                    }
                    s_counter++;
                }
                metadata[key] = status_string;
            } else if (key == 'obsoletes' || key == 'obsoleted_by' || key == 'updates' || key == 'updated_by'){
                var  mLen,metadata_string="",counter=1;
                mLen = metadata[key].length;

                for (let i=0; i< mLen; i++){

                    if (metadata[key][i]){       
                        metadata[key][i] = String(metadata[key][i]).toLowerCase();
                        if (counter < mLen){ 
                            metadata_string =  metadata_string + '<a href=\'' + base_url + '/rfc/'.concat(metadata[key][i]) + '\'>' + metadata[key][i].slice(3) + '</a>'+ ', ';
                        }else {
                                //alert (typeof metadata[key][i])
                            metadata_string =  metadata_string + '<a href=\'' + base_url + '/rfc/'.concat(metadata[key][i]) + '\'>' + metadata[key][i].slice(3) + '</a>';
                        }
                        counter++;
                    }
                }
                metadata[key] = metadata_string;
            } else if (key == 'see_also'){
                var seeAlen, see_also_string="",seeAcounter=1;
                seeAlen = metadata[key].length;
                for (let i=0;i<seeAlen;i++){
                    if (metadata[key][i]){
                        metadata[key][i] = String(metadata[key][i]);
                        var see_also_str = metadata[key][i].slice(0,3);
                        var see_also_num = metadata[key][i].slice(3).replace(/^0+/,''); 
                        if (seeAcounter < seeAlen){
                            if (see_also_str != 'RFC') { 
                                 see_also_string = see_also_string + '<a href=\'' + base_url + '/' + 'info' + '/' + see_also_str.toLowerCase().concat(see_also_num.toLowerCase()) + '\'>'+ see_also_str + ' ' +see_also_num + '</a>' + ', ';
                            } else {
                                 see_also_string = see_also_string + '<a href=\'' + base_url + '/' + 'info' + '/' + see_also_str.toLowerCase().concat(see_also_num.toLowerCase()) + '\'>'+ see_also_num + '</a>' + ', ';
                            }
                        }else {
                            if (see_also_str != 'RFC') { 
                                see_also_string = see_also_string + '<a href=\'' + base_url + '/' + 'info' + '/' + see_also_str.toLowerCase().concat(see_also_num.toLowerCase()) + '\'>'+ see_also_str + ' ' +see_also_num + '</a>';
                            }else {
                                see_also_string = see_also_string + '<a href=\'' + base_url + '/' + 'info' + '/' + see_also_str.toLowerCase().concat(see_also_num.toLowerCase()) + '\'>'+ see_also_num + '</a>';
                            }
                        }
                        seeAcounter++;
                    }
                }
                metadata[key] = see_also_string;
            }
            else if (key == 'errata_url'){
                var errata_string=""; 
                if (metadata[key]){
                    errata_string = errata_string + '<a href=\'' +metadata[key] + '\'>' + 'Errata exist' + '</a>' + ' | ' + '<a href=\'' + datatracker_base + '/' + doc_id + '\'>' + 'Datatracker' + '</a>' + '| ' + '<a href=\'' + ipr_base + '/?' + doc_id_str + '='+ doc_id_num + '&submit='+ doc_id_str +'\'>' + 'IPR' +'</a>' + ' | ' + '<a href=\'' + info_page + '/' + doc_id + '\'>' + 'Info page' + '</a>';
                } 
                else {
                    errata_string = '<a href=\'' + datatracker_base + '/' + doc_id + '\'>' + 'Datatracker' + '</a>' + ' | ' + '<a href=\'' + ipr_base + '/?' + doc_id_str + '='+ doc_id_num + '&submit='+ doc_id_str +'\'>' + 'IPR' +'</a>' + ' | ' + '<a href=\'' + info_page + '/' + doc_id + '\'>' + 'Info page' + '</a>';

                }
                metadata[key] = errata_string;
            }




            if (metadata[key] != ""){

                if (label[key] == 'Errata'){
                    metadataHTML += `<dt>More info:</dt><dd>${metadata[key]}</dd>`;
                }else {
                    metadataHTML += `<dt>${label[key]}:</dt><dd>${metadata[key]}</dd>`;
                }
            }else {
                if (label[key] == 'Errata'){
                    metadataHTML += `<dt>More info:</dt><dd>${metadata[key]}</dd>`;
                }
            }
      //}
        })
                metadataHTML += "</dl>";
        div.innerHTML = metadataHTML;

    } catch (e) {
        console.log(e);
    }

    function capitalizeFirstLetter(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    }

}
window.removeEventListener('load', addMetadata);
window.addEventListener('load',addMetadata);
