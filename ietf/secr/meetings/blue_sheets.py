from django.conf import settings

'''
RTF quick reference (from Word2007RTFSpec9.doc):
\fs24       : sets the font size to 24 half points
\header     : header on all pages
\headerf    : header on first page only
\pard       : resets any previous paragraph formatting
\plain      : resets any previous character formatting
\qr         : right-aligned
\tqc        : centered tab
\tqr        : flush-right tab
\tx         : tab position in twips (1440/inch) from the left margin
\nowidctlpar    : no window/orphan control
\widctlpar      : window/orphan control
'''

def create_blue_sheets(meeting, groups):
    file = open(settings.BLUE_SHEET_PATH, 'w')
    
    header = '''{\\rtf1\\ansi\\ansicpg1252\\uc1 \\deff0\\deflang1033\\deflangfe1033
 {\\fonttbl{\\f0\\froman\\fcharset0\\fprq2{\\*\\panose 02020603050405020304}Times New Roman;}}
 {\\colortbl;\\red0\\green0\\blue0;\\red0\\green0\\blue255;\\red0\\green255\\blue255;\\red0\\green255\\blue0;
\\red255\\green0\\blue255;\\red255\\green0\\blue0;\\red255\\green255\\blue0;\\red255\\green255\\blue255;
\\red0\\green0\\blue128;\\red0\\green128\\blue128;\\red0\\green128\\blue0;\\red128\\green0\\blue128;
\\red128\\green0\\blue0;\\red128\\green128\\blue0;\\red128\\green128\\blue128;
\\red192\\green192\\blue192;}
 \\widowctrl\\ftnbj\\aenddoc\\hyphcaps0\\formshade\\viewkind1\\viewscale100\\pgbrdrhead\\pgbrdrfoot
 \\fet0\\sectd \\pgnrestart\\linex0\\endnhere\\titlepg\\sectdefaultcl'''

    file.write(header)
    
    for group in groups:
        group_header = ''' {\\header \\pard\\plain \\s15\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
 { Mailing List: %s \\tab\\tab Meeting # %s  %s (%s) \\par }
 \\pard \\s15\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright
 {\\b\\fs24
 \\par
 \\par \\tab The NOTE WELL statement applies to this meeting.  Participants acknowledge that these attendance records will be made available to the public.
 \\par
 \\par                               NAME                                                ORGANIZATION
 \\par \\tab
 \\par }}
 {\\footer \\pard\\plain \\s16\\qc\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid {\\cs17 Page }
 {\\field{\\*\\fldinst {\\cs17  PAGE }}}
 { \\par }}
  {\\headerf \\pard\\plain \\s15\\qr\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
  {\\b\\fs24 Meeting # %s %s (%s) \\par }}
 {\\footerf \\pard\\plain \\s16\\qc\\nowidctlpar\\widctlpar\\tqc\\tx4320\\tqr\\tx8640\\adjustright \\fs20\\cgrid
  {Page 1 \\par }}
  \\pard\\plain \\qc\\nowidctlpar\\widctlpar\\adjustright \\fs20\\cgrid
  {\\b\\fs32 %s IETF Working Group Roster \\par }
  \\pard \\nowidctlpar\\widctlpar\\adjustright
  {\\fs28 \\par Working Group Session: %s \\par \\par }
{\\b \\fs24 Mailing List: %s \\tx5300\\tab Actual Start Time: __________     \\par \\par Chairperson:_______________________________     Actual End Time: __________ \\par \\par }
 {\\tab \\tab      }
{\\par \\tab The NOTE WELL statement applies to this meeting.  Participants acknowledge that these attendance records will be made available to the public. \\par 
\\par\\b                                    NAME                                                               ORGANIZATION
\\par }
  \\pard \\fi-90\\li90\\nowidctlpar\\widctlpar\\adjustright
 {\\fs16
''' % (group.list_email,
       meeting.number,
       group.acronym,
       group.type,
       meeting.number,
       group.acronym,
       group.type,
       meeting.number,
       group.name,
       group.list_email)
       
        file.write(group_header)
        for x in range(1,117):
            line = '''\\par %s._________________________________________________ \\tab _____________________________________________________
 \\par
 ''' % x
            file.write(line)
            
        footer = '''}
\\pard \\nowidctlpar\\widctlpar\\adjustright
{\\fs16 \\sect }
\\sectd \\pgnrestart\\linex0\\endnhere\\titlepg\\sectdefaultcl
'''
        file.write(footer)

    file.write('\n}')
    file.close()