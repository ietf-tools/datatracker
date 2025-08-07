<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
		xmlns:en="urn:ietf:params:xml:ns:netconf:notification:1.0"
		version="1.0">
  <!-- Compact output? -->
  <xsl:param name="compact" select="0"/>
  <!-- Indentation step -->
  <xsl:param name="ind-step" select="2"/>
  <xsl:variable name="unit-indent">
    <xsl:call-template name="repeat-string">
      <xsl:with-param name="count" select="$ind-step"/>
      <xsl:with-param name="string" select="' '"/>
    </xsl:call-template>
  </xsl:variable>

  <xsl:variable name="DIGITS">0123456789</xsl:variable>

  <xsl:template name="repeat-string">
    <xsl:param name="count"/>
    <xsl:param name="string"/>
    <xsl:choose>
      <xsl:when test="not($count) or not($string)"/>
      <xsl:when test="$count = 1">
	<xsl:value-of select="$string"/>
      </xsl:when>
      <xsl:otherwise>
	<xsl:if test="$count mod 2">
	  <xsl:value-of select="$string"/>
	</xsl:if>
	<xsl:call-template name="repeat-string">
	  <xsl:with-param name="count" select="floor($count div 2)"/>
	  <xsl:with-param name="string" select="concat($string,$string)"/>
	</xsl:call-template> 
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="nl-indent">
    <xsl:param name="level" select="0"/>
    <xsl:if test="$compact = 0">
      <xsl:text>&#xA;</xsl:text>
      <xsl:call-template name="repeat-string">
	<xsl:with-param name="count" select="$level"/>
	<xsl:with-param name="string" select="$unit-indent"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>

  <xsl:template name="value-type">
    <xsl:choose>
      <xsl:when test=". = 'true' or . = 'false'">boolean</xsl:when>
      <xsl:otherwise>
	<xsl:variable name="unsigned">
	  <xsl:choose>
	    <xsl:when test="contains('+-', substring(.,1,1))">
	      <xsl:value-of select="substring(.,2)"/>
	    </xsl:when>
	    <xsl:otherwise>
	      <xsl:value-of select="."/>
	    </xsl:otherwise>
	  </xsl:choose>
	</xsl:variable>
	<xsl:choose>
	  <xsl:when test="contains($unsigned, '.')">
	    <xsl:variable name="whole"
			  select="substring-before($unsigned,'.')"/>
	    <xsl:variable name="fract"
			  select="substring-after($unsigned,'.')"/>
	    <xsl:choose>
	      <xsl:when
		  test="string-length($whole) > 0 and
			string-length($fract) > 0 and
			string-length(translate(
			concat($whole, $fract), $DIGITS, '')) = 0">
	      <xsl:value-of select="concat('decimal@',
				    string-length($fract))"/>
	      </xsl:when>
	      <xsl:otherwise>other</xsl:otherwise>
	    </xsl:choose>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:choose>
	      <xsl:when
		  test="string-length($unsigned) > 0 and
			string-length(translate($unsigned,
			$DIGITS, '')) = 0">integer</xsl:when>
	      <xsl:otherwise>other</xsl:otherwise>
	    </xsl:choose>
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="resolve-union">
    <xsl:param name="options"/>
    <xsl:variable name="res">
      <xsl:call-template name="first-type-match">
	<xsl:with-param name="type">
	  <xsl:call-template name="value-type"/>
	</xsl:with-param>
	<xsl:with-param name="options" select="$options"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="$res = 'other'">string</xsl:when>
      <xsl:otherwise>unquoted</xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="first-type-match">
    <xsl:param name="type"/>
    <xsl:param name="options"/>
    <xsl:choose>
      <xsl:when test="string-length($options) &gt; 0">
	<xsl:variable name="fst" select="substring-before($options,',')"/>
	<xsl:choose>
	  <xsl:when test="($fst='int64' or $fst='uint64') and $type='integer'
			  or (starts-with($fst,'decimal@')
			  and ($type='integer' or
			  starts-with($type,'decimal@') and
			  substring-after($type,'@') &lt;=
			  substring-after($fst,'@')))">
	    <xsl:text>other</xsl:text>
	  </xsl:when>
	  <xsl:when test="$type=$fst">
	    <xsl:value-of select="$fst"/>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:call-template name="first-type-match">
	      <xsl:with-param name="type" select="$type"/>
	      <xsl:with-param name="options"
			      select="substring-after($options,',')"/>
	    </xsl:call-template>
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:when>
      <xsl:otherwise>
	<xsl:message terminate="no">
	  <xsl:text>*** Warning: invalid XML document</xsl:text>
	</xsl:message>
	<xsl:text>other</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="escape-char">
    <xsl:param name="char"/>
    <xsl:param name="echar"/>
    <xsl:param name="text"/>
    <xsl:choose>
      <xsl:when test="contains($text,$char)">
	<xsl:value-of
	    select="concat(substring-before($text,$char),'\',$echar)"/>
	<xsl:call-template name="escape-char">
	  <xsl:with-param name="char" select="$char"/>
	  <xsl:with-param name="echar" select="$echar"/>
	  <xsl:with-param name="text"
			  select="substring-after($text,$char)"/>
	</xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
	<xsl:value-of select="$text"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="escape-text">
    <xsl:param name="tte" select="."/>
    <xsl:call-template name="escape-char">
      <xsl:with-param name="char" select="'&#xD;'"/>
      <xsl:with-param name="echar" select="'r'"/>
      <xsl:with-param name="text">
	<xsl:call-template name="escape-char">
	  <xsl:with-param name="char" select="'&#x9;'"/>
	  <xsl:with-param name="echar" select="'t'"/>
	  <xsl:with-param name="text">
	    <xsl:call-template name="escape-char">
	      <xsl:with-param name="char" select="'&#xA;'"/>
	      <xsl:with-param name="echar" select="'n'"/>
	      <xsl:with-param name="text">
		<xsl:call-template name="escape-char">
		  <xsl:with-param name="char" select="'&quot;'"/>
		  <xsl:with-param name="echar" select="'&quot;'"/>
		  <xsl:with-param name="text">
		    <xsl:call-template name="escape-char">
		      <xsl:with-param name="char" select="'\'"/>
		      <xsl:with-param name="echar" select="'\'"/>
		      <xsl:with-param name="text" select="$tte"/>
		    </xsl:call-template>
		  </xsl:with-param>
		</xsl:call-template>
	      </xsl:with-param>
	    </xsl:call-template>
	  </xsl:with-param>
	</xsl:call-template>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template name="eat-quoted">
    <xsl:param name="text"/>
    <xsl:param name="qch">'</xsl:param>
    <xsl:param name="oldprf"/>
    <xsl:value-of select="concat(substring-before($text,$qch),$qch)"/>
    <xsl:call-template name="eat-unquoted">
      <xsl:with-param name="text" select="substring-after($text,$qch)"/>
      <xsl:with-param name="oldprf" select="$oldprf"/>
    </xsl:call-template>
  </xsl:template>

  <xsl:template name="eat-unquoted">
    <xsl:param name="text"/>
    <xsl:param name="oldprf"/>
    <xsl:if test="string-length($text) &gt; 0">
      <xsl:variable name="first" select="substring($text,1,1)"/>
      <xsl:variable name="quotes">'"</xsl:variable>
      <xsl:value-of select="$first"/>
      <xsl:choose>
	<xsl:when test="$first='/' or $first='[' and
			string-length(substring-before($text,':'))
			&lt;
			string-length(substring-before($text,']'))">
	  <xsl:variable name="prf"
			select="substring-before(substring($text,2),':')"/>
	  <xsl:choose>
	    <xsl:when test="$prf=$oldprf">
	      <xsl:call-template name="eat-unquoted">
		<xsl:with-param name="text"
				select="substring-after($text,':')"/>
		<xsl:with-param name="oldprf" select="$oldprf"/>
	      </xsl:call-template>
	    </xsl:when>
	    <xsl:otherwise>
	      <xsl:call-template name="translate-prefix">
		<xsl:with-param name="prf" select="$prf"/>
	      </xsl:call-template>
	      <xsl:call-template name="eat-unquoted">
		<xsl:with-param name="text"
				select="substring-after($text,':')"/>
		<xsl:with-param name="oldprf" select="$prf"/>
	      </xsl:call-template>
	    </xsl:otherwise>
	  </xsl:choose>
	</xsl:when>
	<xsl:when test="contains($quotes,$first)">
	  <xsl:call-template name="eat-quoted">
	    <xsl:with-param name="text" select="substring($text,2)"/>
	    <xsl:with-param name="qch" select="$first"/>
	    <xsl:with-param name="oldprf" select="$oldprf"/>
	  </xsl:call-template>
	</xsl:when>
	<xsl:otherwise>
	  <xsl:call-template name="eat-unquoted">
	    <xsl:with-param name="text" select="substring($text,2)"/>
	    <xsl:with-param name="oldprf" select="$oldprf"/>
	  </xsl:call-template>
	</xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:template>

  <xsl:template name="translate-prefix">
    <xsl:param name="prf"/>
    <xsl:variable name="modname">
      <xsl:call-template name="nsuri-to-module">
	<xsl:with-param
	    name="uri"
	    select="ancestor-or-self::*/namespace::*[name()=normalize-space($prf)]"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:if test="string-length($modname)=0">
      <xsl:message terminate="yes">
	<xsl:value-of select="concat('Undefined namespace prefix: ', $prf)"/>
      </xsl:message>
    </xsl:if>
    <xsl:value-of select="concat($modname, ':')"/>
  </xsl:template>

  <xsl:template name="json-value">
    <xsl:param name="type">string</xsl:param>
    <xsl:param name="options"/>
    <xsl:choose>
      <xsl:when test="$type='union'">
	<xsl:call-template name="json-value">
	  <xsl:with-param name="type">
	    <xsl:call-template name="resolve-union">
	      <xsl:with-param name="options" select="$options"/>
	    </xsl:call-template>
	  </xsl:with-param>
	</xsl:call-template>
      </xsl:when>
      <xsl:when test="$type='unquoted'">
	<xsl:value-of select="normalize-space(.)"/>
      </xsl:when>
      <xsl:when test="$type='empty'">[null]</xsl:when>
      <xsl:when test="$type='instance-identifier'">
	<xsl:variable name="cont" select="normalize-space(.)"/>
	<xsl:if test="not(starts-with($cont,'/'))">
	  <xsl:message terminate="yes">
	    <xsl:value-of
		select="concat('Wrong instance identifier: ', $cont)"/>
	  </xsl:message>
	</xsl:if>
	<xsl:text>"</xsl:text>
	<xsl:call-template name="escape-text">
	  <xsl:with-param name="tte">
	    <xsl:call-template name="eat-unquoted">
	      <xsl:with-param name="text" select="$cont"/>
	    </xsl:call-template>
	  </xsl:with-param>
	</xsl:call-template>
	<xsl:text>"</xsl:text>
      </xsl:when>
      <xsl:when test="$type='identityref'">
	<xsl:variable name="cont" select="normalize-space(.)"/>
	<xsl:text>"</xsl:text>
	<xsl:choose>
	  <xsl:when test="contains($cont,':')">
	    <xsl:call-template name="translate-prefix">
	      <xsl:with-param name="prf"
			      select="substring-before($cont,':')"/>
	    </xsl:call-template>
	    <xsl:value-of select="substring-after($cont, ':')"/>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:value-of select="$cont"/>
	  </xsl:otherwise>
	</xsl:choose>
	<xsl:text>"</xsl:text>
      </xsl:when>
      <xsl:when test="$type='string'">
	<xsl:text>"</xsl:text>
	<xsl:call-template name="escape-text"/>
	<xsl:text>"</xsl:text>
      </xsl:when>
      <xsl:when test="$type='other'">
	<xsl:value-of select="concat('&quot;', normalize-space(.),'&quot;')"/>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="metadata-object">
    <xsl:param name="name"/>
    <xsl:param name="level"/>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:value-of select="concat($name,'{')"/>
    <xsl:for-each select="@*">
      <xsl:apply-templates select=".">
	<xsl:with-param name="level" select="$level+1"/>
      </xsl:apply-templates>
      <xsl:if test="position() != last()">,</xsl:if>
    </xsl:for-each>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:text>}</xsl:text>
  </xsl:template>

  <xsl:template name="container">
    <xsl:param name="level" select="0"/>
    <xsl:param name="nsid"/>
    <xsl:if test="preceding-sibling::*">,</xsl:if>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:value-of
	select="concat('&quot;', $nsid, local-name(.), '&quot;: {')"/>
    <xsl:if test="@*">
      <xsl:call-template name="metadata-object">
	<xsl:with-param name="name">"@": </xsl:with-param>
	<xsl:with-param name="level" select="$level+1"/>
      </xsl:call-template>
      <xsl:if test="*">,</xsl:if>
    </xsl:if>
    <xsl:apply-templates/>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:text>}</xsl:text>
  </xsl:template>

  <xsl:template name="rpc-input">
    <xsl:param name="nsid"/>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="1"/>
    </xsl:call-template>
    <xsl:value-of
	select="concat('&quot;', $nsid, 'input', '&quot;: {')"/>
    <xsl:apply-templates/>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="1"/>
    </xsl:call-template>
    <xsl:text>}</xsl:text>
  </xsl:template>

  <xsl:template name="leaf">
    <xsl:param name="level" select="0"/>
    <xsl:param name="type"/>
    <xsl:param name="options"/>
    <xsl:param name="nsid"/>
    <xsl:if test="preceding-sibling::*">,</xsl:if>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:value-of
	select="concat('&quot;', $nsid, local-name(.), '&quot;: ')"/>
    <xsl:call-template name="json-value">
      <xsl:with-param name="type" select="$type"/>
      <xsl:with-param name="options" select="$options"/>
    </xsl:call-template>
    <xsl:if test="@*">
      <xsl:text>,</xsl:text>
      <xsl:call-template name="metadata-object">
	<xsl:with-param
	    name="name"
	    select="concat('&quot;@', $nsid, local-name(.), '&quot;: ')"/>
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>

  <xsl:template name="leaf-list">
    <xsl:param name="level" select="0"/>
    <xsl:param name="type"/>
    <xsl:param name="options"/>
    <xsl:param name="nsid"/>
    <xsl:variable name="curname" select="local-name()"/>
    <xsl:variable name="cururi" select="namespace-uri()"/>
    <xsl:if test="not(preceding-sibling::*[local-name()=$curname
		  and namespace-uri()=$cururi])">
      <xsl:variable
	  name="entries"
	  select="../*[local-name()=$curname and namespace-uri()=$cururi]"/>
      <xsl:if test="preceding-sibling::*">,</xsl:if>
      <xsl:call-template name="nl-indent">
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
      <xsl:value-of
	  select="concat('&quot;', $nsid, local-name(.), '&quot;: [')"/>
      <xsl:for-each select="$entries">
	<xsl:call-template name="nl-indent">
	  <xsl:with-param name="level" select="$level+1"/>
	</xsl:call-template>
	<xsl:call-template name="json-value">
	  <xsl:with-param name="type" select="$type"/>
	  <xsl:with-param name="options" select="$options"/>
	</xsl:call-template>
	<xsl:if test="position() != last()">,</xsl:if>
      </xsl:for-each>
      <xsl:call-template name="nl-indent">
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
      <xsl:text>]</xsl:text>
      <xsl:variable
	  name="att-entries"
	  select="$entries[@* or following-sibling::*[@* and
		  local-name()=$curname and namespace-uri()=$cururi]]"/>
      <xsl:if test="$att-entries">
	<xsl:text>,</xsl:text>
	<xsl:call-template name="nl-indent">
	  <xsl:with-param name="level" select="$level"/>
	</xsl:call-template>
	<xsl:value-of
	    select="concat('&quot;@', $nsid, local-name(.), '&quot;: [')"/>
	<xsl:for-each select="$att-entries">
	  <xsl:choose>
	    <xsl:when test="@*">
	      <xsl:call-template name="metadata-object">
		<xsl:with-param name="level" select="$level+1"/>
	      </xsl:call-template>
	    </xsl:when>
	    <xsl:otherwise>
	      <xsl:call-template name="nl-indent">
		<xsl:with-param name="level" select="$level+1"/>
	      </xsl:call-template>
	      <xsl:text>null</xsl:text>
	    </xsl:otherwise>
	  </xsl:choose>
	  <xsl:if test="position() != last()">,</xsl:if>
	</xsl:for-each>
	<xsl:call-template name="nl-indent">
	  <xsl:with-param name="level" select="$level"/>
	</xsl:call-template>
	<xsl:text>]</xsl:text>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <xsl:template name="list">
    <xsl:param name="level" select="0"/>
    <xsl:param name="nsid"/>
    <xsl:if
	test="not(preceding-sibling::*[local-name()=local-name(current())
	      and namespace-uri()=namespace-uri(current())])">
      <xsl:if test="preceding-sibling::*">,</xsl:if>
      <xsl:call-template name="nl-indent">
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
      <xsl:value-of
	  select="concat('&quot;', $nsid, local-name(.), '&quot;: [')"/>
      <xsl:for-each
	  select="../*[local-name()=local-name(current())
		  and namespace-uri()=namespace-uri(current())]">
	<xsl:call-template name="nl-indent">
	  <xsl:with-param name="level" select="$level+1"/>
	</xsl:call-template>
	<xsl:text>{</xsl:text>
	<xsl:if test="@*">
	  <xsl:call-template name="metadata-object">
	    <xsl:with-param name="name">"@": </xsl:with-param>
	    <xsl:with-param name="level" select="$level+2"/>
	  </xsl:call-template>
	  <xsl:if test="*">,</xsl:if>
	</xsl:if>
	<xsl:apply-templates/>
	<xsl:call-template name="nl-indent">
	  <xsl:with-param name="level" select="$level+1"/>
	</xsl:call-template>
	<xsl:text>}</xsl:text>
	<xsl:if test="position() != last()">,</xsl:if>
      </xsl:for-each>
      <xsl:call-template name="nl-indent">
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
      <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>

  <xsl:template name="anyxml">
    <xsl:param name="level" select="0"/>
    <xsl:param name="nsid"/>
    <xsl:if test="preceding-sibling::*">,</xsl:if>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:value-of
	select="concat('&quot;', $nsid, local-name(.), '&quot;: {')"/>
    <xsl:apply-templates mode="anyxml">
      <xsl:with-param name="level" select="$level+1"/>
    </xsl:apply-templates>
    <xsl:call-template name="nl-indent">
      <xsl:with-param name="level" select="$level"/>
    </xsl:call-template>
    <xsl:text>}</xsl:text>
    <xsl:if test="@*">
      <xsl:text>,</xsl:text>
      <xsl:call-template name="metadata-object">
	<xsl:with-param
	    name="name"
	    select="concat('&quot;@', $nsid, local-name(.), '&quot;: ')"/>
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>

  <xsl:template match="*" mode="anyxml">
    <xsl:param name="level" select="0"/>
    <xsl:if test="not(preceding-sibling::*[name()=name(current())])">
      <xsl:if test="preceding-sibling::*">,</xsl:if>
      <xsl:call-template name="nl-indent">
	<xsl:with-param name="level" select="$level"/>
      </xsl:call-template>
      <xsl:value-of
	  select="concat('&quot;', name(.), '&quot;: ')"/>
      <xsl:choose>
	<xsl:when test="following-sibling::*[name()=name(current())]">
	  <xsl:text>[</xsl:text>
	  <xsl:for-each select="../*[name()=name(current())]">
	    <xsl:call-template name="nl-indent">
	      <xsl:with-param name="level" select="$level+1"/>
	    </xsl:call-template>
	    <xsl:choose>
	      <xsl:when test="*">
		<xsl:text>{</xsl:text>
		<xsl:apply-templates mode="anyxml">
		  <xsl:with-param name="level" select="$level+2"/>
		</xsl:apply-templates>
		<xsl:call-template name="nl-indent">
		  <xsl:with-param name="level" select="$level+1"/>
		</xsl:call-template>
		<xsl:text>}</xsl:text>
	      </xsl:when>
	      <xsl:otherwise>
		<xsl:call-template name="json-value"/>
	      </xsl:otherwise>
	    </xsl:choose>
	    <xsl:if test="position() != last()">,</xsl:if>
	  </xsl:for-each>
	  <xsl:call-template name="nl-indent">
	    <xsl:with-param name="level" select="$level"/>
	  </xsl:call-template>
	  <xsl:text>]</xsl:text>
	</xsl:when>
	<xsl:when test="*">
	  <xsl:text>{</xsl:text>
	  <xsl:apply-templates mode="anyxml">
	    <xsl:with-param name="level" select="$level+1"/>
	  </xsl:apply-templates>
	  <xsl:call-template name="nl-indent">
	    <xsl:with-param name="level" select="$level"/>
	  </xsl:call-template>
	  <xsl:text>}</xsl:text>
	</xsl:when>
	<xsl:otherwise>
	  <xsl:call-template name="json-value"/>
	</xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:template>

  <xsl:template match="@*|text()|comment()|processing-instruction()" mode="anyxml"/>

  <xsl:template match="/">
    <xsl:apply-templates
	select="nc:data|nc:config|nc:rpc|nc:rpc-reply|en:notification"/>
  </xsl:template>

  <xsl:template match="nc:rpc-reply[nc:data or nc:config]">
    <xsl:apply-templates select="nc:data|nc:config"/>
  </xsl:template>

  <xsl:template match="nc:data|nc:config|nc:rpc|nc:rpc-reply|en:notification">
    <xsl:text>{</xsl:text>
    <xsl:apply-templates select="*"/>
    <xsl:call-template name="nl-indent"/>
    <xsl:text>}&#xA;</xsl:text>
  </xsl:template>

  <xsl:template match="/en:notification/en:eventTime">
    <xsl:call-template name="leaf">
      <xsl:with-param name="level" select="1"/>
      <xsl:with-param name="type">other</xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template match="/nc:rpc-reply/nc:ok">
    <xsl:call-template name="leaf">
      <xsl:with-param name="level" select="1"/>
      <xsl:with-param name="type">empty</xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template match="*">
    <xsl:message terminate="yes">
      <xsl:value-of select="concat('Aborting, bad element: ', name())"/>
    </xsl:message>
  </xsl:template>

</xsl:stylesheet>
