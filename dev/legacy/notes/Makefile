all: notes.html

%.html: %.rst html4css1.css custom.css
	rst2html --stylesheet html4css1.css,custom.css $< $@

%.pdf:  %.rst 
	rst2pdf $<

