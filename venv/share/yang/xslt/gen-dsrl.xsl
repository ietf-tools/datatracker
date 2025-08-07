<?xml version="1.0" encoding="utf-8"?>

<!-- Program name: gen-dsrl.xsl

Copyright © 2014 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>

Creates DSRL schema from the hybrid DSDL schema (see RFC 6110).

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
		xmlns:exsl="http://exslt.org/common"
		extension-element-prefixes="exsl"
		xmlns:rng="http://relaxng.org/ns/structure/1.0"
		xmlns:dsrl="http://purl.oclc.org/dsdl/dsrl"
		xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
		xmlns:en="urn:ietf:params:xml:ns:netconf:notification:1.0"
		xmlns:nma="urn:ietf:params:xml:ns:netmod:dsdl-annotations:1"
		version="1.0">

  <xsl:output method="xml" encoding="utf-8"/>
  <xsl:strip-space elements="*"/>

  <xsl:include href="gen-common.xsl"/>

  <!-- Fast access to named pattern definitions by their name -->
  <xsl:key name="refdef" match="//rng:define" use="@name"/>

  <!-- Named templates -->

  <xsl:template name="nc-namespace">
    <!-- Insert namespace declaration for the top-level NETCONF part
	 of the target document type.  -->
    <xsl:choose>
      <xsl:when test="$target='config' or $target='get-reply' or
		      $target='get-config-reply' or $target='data'
		      or $target='rpc' or $target='rpc-reply'">
	<xsl:variable name="dummy">
	  <nc:dummy/>
	</xsl:variable>
	<xsl:copy-of select="exsl:node-set($dummy)/*/namespace::*"/>
      </xsl:when>
      <xsl:when test="$target='notification'">
	<xsl:variable name="dummy">
	  <en:dummy/>
	</xsl:variable>
	<xsl:copy-of select="exsl:node-set($dummy)/*/namespace::*"/>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="qname">
    <!-- Prepend the current prefix, if it is missing. -->
    <xsl:param name="prefix"/>
    <xsl:param name="name" select="@name"/>
    <xsl:if test="not(contains($name,':'))">
      <xsl:value-of select="concat($prefix,':')"/>
    </xsl:if>
    <xsl:value-of select="$name"/>
  </xsl:template>

  <xsl:template name="subst-variables">
    <!-- Replace $root and $pref with actual values in when -->
    <xsl:param name="prefix"/>
    <xsl:variable name="temp">
      <xsl:call-template name="subst-var">
	<xsl:with-param name="varname">$pref</xsl:with-param>
	<xsl:with-param name="value" select="$prefix"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:call-template name="subst-var">
      <xsl:with-param name="text" select="$temp"/>
      <xsl:with-param name="varname">$root</xsl:with-param>
      <xsl:with-param name="value" select="$netconf-part"/>
    </xsl:call-template>
  </xsl:template>

  <xsl:template name="subst-var">
    <!-- Substitute $value for all occurences of $varname in $text -->
    <xsl:param name="text" select="@nma:when"/>
    <xsl:param name="varname"/>
    <xsl:param name="value"/>
    <xsl:choose>
      <xsl:when test="contains($text,$varname)">
	<xsl:value-of select="substring-before($text,$varname)"/>
	<xsl:value-of select="$value"/>
	<xsl:call-template name="subst-var">
	  <xsl:with-param name="text"
			  select="substring-after($text,$varname)"/>
	  <xsl:with-param name="varname" select="$varname"/>
	  <xsl:with-param name="value" select="$value"/>
	</xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
	<xsl:value-of select="$text"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="parent-path">
    <!-- Slash-separated path from root to the parent node of the
	 context element, with 'when' conditions, if they are present. -->
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:value-of select="$prevpath"/>
    <xsl:for-each select="ancestor::rng:element">
      <xsl:text>/</xsl:text>
      <xsl:call-template name="qname">
	<xsl:with-param name="prefix" select="$prefix"/>
      </xsl:call-template>
      <xsl:if test="@nma:when">
	<xsl:text>[</xsl:text>
	<xsl:call-template name="subst-variables">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:call-template>
	<xsl:text>]</xsl:text>
      </xsl:if>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="yam-namespaces">
    <!-- Copy namespace declarations of all YANG modules. -->
    <xsl:for-each
	select="namespace::*[not(name()='xml' or .=$rng-uri or
		.=$dtdc-uri or .=$dc-uri or .=$nma-uri)]">
      <xsl:copy/>
    </xsl:for-each>
  </xsl:template>

  <xsl:template name="element-map">
    <!-- Construct DSRL 'element-map' with all parameters.

         The 'condition' parameter contains additional condition(s)
	 for the parent context (resulting from the processing of
	 choice's cases.
    -->
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="content"/>
    <xsl:param name="condition"/>
    <xsl:element name="dsrl:element-map">
      <xsl:element name="dsrl:parent">
	<xsl:variable name="ppath">
	  <xsl:call-template name="parent-path">
	    <xsl:with-param name="prevpath" select="$prevpath"/>
	    <xsl:with-param name="prefix" select="$prefix"/>
	  </xsl:call-template>
	</xsl:variable>
	<xsl:choose>
	  <xsl:when test="$ppath=''">/</xsl:when>
	  <xsl:otherwise>
	    <xsl:value-of select="$ppath"/>
	  </xsl:otherwise>
	</xsl:choose>
	<xsl:value-of select="$condition"/>
      </xsl:element>
      <xsl:element name="dsrl:name">
	<xsl:call-template name="qname">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:call-template>
      </xsl:element>
      <xsl:element name="dsrl:default-content">
	<xsl:apply-templates select="$content" mode="copy">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:apply-templates>
      </xsl:element>
    </xsl:element>
  </xsl:template>

  <xsl:template name="no-other-cases">
    <!-- Construct the Xpath expression stating that no nodes from
	 othet cases of a choice exist. -->
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:variable name="cnodes">
      <xsl:apply-templates select="ancestor::rng:choice[1]"
			   mode="case-nodes">
	<xsl:with-param name="prefix" select="$prefix"/>
	<xsl:with-param name="except" select="generate-id()"/>
      </xsl:apply-templates>
    </xsl:variable>
    <xsl:value-of
	select="concat($condition,'[not(',
		substring-after($cnodes,'|'),')]')"/>
  </xsl:template>

  <!-- Root element -->
  <xsl:template match="/">
    <xsl:call-template name="check-input-pars"/>
    <xsl:element name="dsrl:maps">
      <xsl:apply-templates select="rng:grammar"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="/rng:grammar">
    <xsl:call-template name="yam-namespaces"/>
    <xsl:call-template name="nc-namespace"/>
    <xsl:apply-templates select="descendant::rng:grammar"/>
  </xsl:template>

  <xsl:template match="rng:grammar">
    <xsl:variable name="prefix"
		  select="name(namespace::*[.=current()/@ns])"/>
    <xsl:choose>
      <xsl:when test="$target='data' or $target='config' or
		      $target='get-reply' or $target='get-config-reply'">
	<xsl:apply-templates select="descendant::nma:data">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:apply-templates>
      </xsl:when>
      <xsl:when test="$target='rpc'">
	<xsl:apply-templates select="descendant::nma:input">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:apply-templates>
      </xsl:when>
      <xsl:when test="$target='rpc-reply'">
	<xsl:apply-templates select="descendant::nma:output">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:apply-templates>
      </xsl:when>
      <xsl:when test="$target='notification'">
	<xsl:apply-templates select="descendant::nma:notification">
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:apply-templates>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="nma:*">
    <!-- Section of the hybrid schema depending on $target.

         The following two parameters are passed down the chain of
	 templates:
         - 'prevpath': slash-separated path of the current element's
	    parent,
         - 'prefix': namespace prefix of the current module.
    -->
    <xsl:param name="prefix"/>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$netconf-part"/>
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:element[@nma:default]">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:call-template name="element-map">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="content" select="@nma:default"/>
      <xsl:with-param name="condition" select="$condition"/>
    </xsl:call-template>
  </xsl:template>

  <xsl:template match="rng:element[@nma:implicit='true']">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:call-template name="element-map">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="content" select="rng:*"/>
      <xsl:with-param name="condition" select="$condition"/>
    </xsl:call-template>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:parentRef"/>

  <xsl:template match="rng:*">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="condition" select="$condition"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:ref">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:apply-templates select="key('refdef', @name)">
      <xsl:with-param name="prevpath">
	<xsl:call-template name="parent-path">
	  <xsl:with-param name="prevpath" select="$prevpath"/>
	  <xsl:with-param name="prefix" select="$prefix"/>
	</xsl:call-template>
      </xsl:with-param>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="condition" select="$condition"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:apply-templates select="rng:*" mode="choice">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="condition" select="$condition"/>
    </xsl:apply-templates>
  </xsl:template>

  <!-- Mode 'choice': classify the choice's cases and perform the
       corresponding actions. -->

  <xsl:template match="rng:element[@nma:default]" mode="choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:call-template name="element-map">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="content" select="@nma:default"/>
      <xsl:with-param name="condition">
	<xsl:call-template name="no-other-cases">
	  <xsl:with-param name="prefix" select="$prefix"/>
	  <xsl:with-param name="condition" select="$condition"/>
	</xsl:call-template>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template match="rng:element[@nma:implicit='true']" mode="choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:call-template name="element-map">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="content" select="rng:*"/>
      <xsl:with-param name="condition">
	<xsl:call-template name="no-other-cases">
	  <xsl:with-param name="prefix" select="$prefix"/>
	  <xsl:with-param name="condition" select="$condition"/>
	</xsl:call-template>
      </xsl:with-param>
    </xsl:call-template>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template
      match="rng:group[@nma:implicit='true']|
	     rng:interleave[@nma:implicit='true']"
      mode="choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="condition">
	<xsl:call-template name="no-other-cases">
	  <xsl:with-param name="prefix" select="$prefix"/>
	  <xsl:with-param name="condition" select="$condition"/>
	</xsl:call-template>
      </xsl:with-param>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:group[count(rng:*) &gt; 1]|
		       rng:interleave[count(rng:*) &gt; 1]"
		mode="choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:param name="condition"/>
    <xsl:apply-templates select="rng:*">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="condition">
	<xsl:variable name="cnodes">
	  <xsl:apply-templates select="." mode="case-nodes">
	    <xsl:with-param name="prefix" select="$prefix"/>
	  </xsl:apply-templates>
	</xsl:variable>
	<xsl:value-of select="concat($condition, '[',
			      substring-after($cnodes,'|'),']')"/>
      </xsl:with-param>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:*" mode="choice">
    <xsl:param name="prevpath"/>
    <xsl:param name="prefix"/>
    <xsl:apply-templates select=".">
      <xsl:with-param name="prevpath" select="$prevpath"/>
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

  <!-- Mode 'case-nodes': construct a partial XPath expression
       consisting of names of all first-level descendant nodes
       separated by '|', except the node whose id is in the 'except'
       parameter.

       This is used for generating constraints for choice's cases.
  -->

  <xsl:template match="rng:element" mode="case-nodes">
    <xsl:param name="prefix"/>
    <xsl:param name="except"/>
    <xsl:if test="generate-id() != $except">
      <xsl:text>|</xsl:text>
      <xsl:call-template name="qname">
	<xsl:with-param name="prefix" select="$prefix"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>

  <xsl:template match="rng:ref" mode="case-nodes">
    <xsl:param name="prefix"/>
    <xsl:param name="except"/>
    <xsl:apply-templates select="key('refdef', @name)" mode="case-nodes">
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="except" select="$except"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:group|rng:interleave" mode="case-nodes">
    <xsl:param name="prefix"/>
    <xsl:param name="except"/>
    <xsl:if test="generate-id() != $except">
      <xsl:apply-templates select="rng:*" mode="case-nodes">
	<xsl:with-param name="prefix" select="$prefix"/>
	<xsl:with-param name="except" select="$except"/>
      </xsl:apply-templates>
    </xsl:if>
  </xsl:template>

  <xsl:template match="rng:*" mode="case-nodes">
    <xsl:param name="prefix"/>
    <xsl:param name="except"/>
    <xsl:apply-templates select="rng:*" mode="case-nodes">
      <xsl:with-param name="prefix" select="$prefix"/>
      <xsl:with-param name="except" select="$except"/>
    </xsl:apply-templates>
  </xsl:template>

  <!-- Mode 'copy': create the default contents in element-maps from
       the hybrid schema. -->

  <xsl:template
      match="rng:choice/rng:group[not(@nma:implicit='true')]|
	     rng:choice/rng:interleave[not(@nma:implicit='true')]"
      mode="copy"/>

  <xsl:template match="rng:element[@nma:implicit='true']" mode="copy">
    <xsl:param name="prefix"/>
    <xsl:variable name="name">
      <xsl:call-template name="qname">
	<xsl:with-param name="prefix" select="$prefix"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:variable name="act-prefix" select="substring-before($name,':')"/>
    <xsl:element name="{$name}"
		 namespace="{namespace::*[name()=$act-prefix]}">
      <xsl:apply-templates select="rng:*" mode="copy">
	<xsl:with-param name="prefix" select="$act-prefix"/>
      </xsl:apply-templates>
    </xsl:element>
  </xsl:template>

  <xsl:template match="rng:element[@nma:default]" mode="copy">
    <xsl:param name="prefix"/>
    <xsl:variable name="name">
      <xsl:call-template name="qname">
	<xsl:with-param name="prefix" select="$prefix"/>
      </xsl:call-template>
    </xsl:variable>
    <xsl:variable name="act-prefix" select="substring-before($name,':')"/>
    <xsl:element name="{$name}"
		 namespace="{namespace::*[name()=$act-prefix]}">
      <xsl:value-of select="@nma:default"/>
    </xsl:element>
  </xsl:template>

  <xsl:template
      match="rng:element|rng:data|rng:parentRef"
      mode="copy"/>

  <xsl:template match="rng:ref" mode="copy">
    <xsl:param name="prefix"/>
    <xsl:apply-templates select="key('refdef',@name)" mode="copy">
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template match="rng:define[@nma:default]" mode="copy">
    <xsl:value-of select="@nma:default"/>
  </xsl:template>

  <xsl:template match="rng:*" mode="copy">
    <xsl:param name="prefix"/>
    <xsl:apply-templates select="rng:*" mode="copy">
      <xsl:with-param name="prefix" select="$prefix"/>
    </xsl:apply-templates>
  </xsl:template>

</xsl:stylesheet>
