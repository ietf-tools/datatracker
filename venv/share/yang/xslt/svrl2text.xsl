<?xml version="1.0" encoding="utf-8"?>

<!-- Program name: svrl2text.xsl

Copyright © 2010 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>

Translates SVRL to simple plain text reports.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:svrl="http://purl.oclc.org/dsdl/svrl"
                version="1.0">
  <xsl:output method="text" encoding="utf-8"/>

  <xsl:variable name="NL">
    <xsl:text>
</xsl:text>
  </xsl:variable>

  <xsl:template match="/">
    <xsl:choose>
      <xsl:when
	  test="not(//svrl:failed-assert|//svrl:successful-report)">
	<xsl:message terminate="no">
	  <xsl:text>No errors found.</xsl:text>
	  <xsl:value-of select="$NL"/>
	</xsl:message>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates
            select="//svrl:failed-assert|//svrl:successful-report"/>
	<xsl:message terminate="yes"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="svrl:failed-assert">
    <xsl:message terminate="no">
      <xsl:text>--- Failed assert at "</xsl:text>
      <xsl:value-of
	  select="preceding-sibling::svrl:fired-rule[1]/@context"/>
      <xsl:value-of select="concat('&quot;:',$NL)"/>
      <xsl:value-of select="concat('    ',svrl:text,$NL)"/>
    </xsl:message>
  </xsl:template>

  <xsl:template match="svrl:successful-report">
    <xsl:message terminate="no">
      <xsl:text>--- Validity error at "</xsl:text>
      <xsl:value-of
	  select="preceding-sibling::svrl:fired-rule[1]/@context"/>
      <xsl:value-of select="concat('&quot;:',$NL)"/>
      <xsl:value-of select="concat('    ',svrl:text,$NL)"/>
    </xsl:message>
  </xsl:template>

</xsl:stylesheet>
