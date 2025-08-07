<?xml version="1.0" encoding="utf-8"?>

<!-- Program name: gen-relaxng.xsl

Copyright © 2013 by Ladislav Lhotka, CZ.NIC <lhotka@nic.cz>

Creates RELAX NG schema from the hybrid DSDL schema (see RFC 6110).

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

<xsl:stylesheet
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:rng="http://relaxng.org/ns/structure/1.0"
    xmlns:nma="urn:ietf:params:xml:ns:netmod:dsdl-annotations:1"
    xmlns:a="http://relaxng.org/ns/compatibility/annotations/1.0"
    version="1.0">

  <xsl:output method="xml" encoding="utf-8"/>
  <xsl:strip-space elements="*"/>

  <xsl:include href="gen-common.xsl"/>

  <xsl:variable name="gdefs-file">
    <xsl:value-of select="concat($basename,'-gdefs')"/>
    <xsl:choose>
      <xsl:when test="$target='get-config-reply' or $target='config'">
        <xsl:text>-config</xsl:text>
      </xsl:when>
      <xsl:when test="$target='edit-config'">
        <xsl:text>-edit</xsl:text>
      </xsl:when>
    </xsl:choose>
    <xsl:text>.rng</xsl:text>
  </xsl:variable>

  <xsl:template name="ns-attribute">
    <xsl:attribute name="ns">
      <xsl:choose>
        <xsl:when test="$target='get-reply' or
                        $target='get-data-reply' or
                        $target='config' or
                        $target='edit-config' or
                        $target='data' or $target='get-config-reply'
                        or $target='rpc' or $target='rpc-reply'">
          <xsl:text>urn:ietf:params:xml:ns:netconf:base:1.0</xsl:text>
        </xsl:when>
        <xsl:when test="$target='notification'">
          <xsl:text>urn:ietf:params:xml:ns:netconf:notification:1.0</xsl:text>
        </xsl:when>
      </xsl:choose>
    </xsl:attribute>
  </xsl:template>

  <xsl:template name="include-grammar">
    <xsl:param name="file-name"/>
    <xsl:element name="include" namespace="{$rng-uri}">
      <xsl:attribute name="href">
        <xsl:value-of select="$file-name"/>
      </xsl:attribute>
    </xsl:element>
  </xsl:template>

  <xsl:template name="message-id">
    <xsl:element name="ref" namespace="{$rng-uri}">
      <xsl:attribute name="name">message-id-attribute</xsl:attribute>
    </xsl:element>
  </xsl:template>

  <xsl:template name="copy-and-continue">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:apply-templates select="rng:*|text()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/">
    <xsl:choose>
      <xsl:when test="$gdefs-only=1">
        <xsl:apply-templates select="rng:grammar" mode="gdefs"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="check-input-pars"/>
        <xsl:apply-templates select="rng:grammar"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="/rng:grammar" mode="gdefs">
    <xsl:copy>
      <xsl:attribute name="datatypeLibrary">
        <xsl:value-of select="@datatypeLibrary"/>
      </xsl:attribute>
      <xsl:apply-templates select="rng:define"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/rng:grammar">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:call-template name="ns-attribute"/>
      <xsl:call-template name="include-grammar">
        <xsl:with-param name="file-name" select="concat($schema-dir,'/relaxng-lib.rng')"/>
      </xsl:call-template>
      <xsl:apply-templates select="rng:start"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/rng:grammar/rng:start">
    <xsl:copy>
      <xsl:choose>
        <xsl:when test="$target='data'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">data</xsl:attribute>
            <xsl:element name="interleave" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="rng:grammar[descendant::nma:data]"/>
            </xsl:element>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='config'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">config</xsl:attribute>
            <xsl:element name="interleave" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="rng:grammar[descendant::nma:data]"/>
            </xsl:element>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='get-reply' or
                        $target='get-data-reply' or
                        $target='get-config-reply'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">rpc-reply</xsl:attribute>
            <xsl:call-template name="message-id"/>
            <xsl:choose>
              <xsl:when test="$target='get-reply' or
                              $target='get-config-reply'">
                <xsl:element name="element" namespace="{$rng-uri}">
                  <xsl:attribute name="name">data</xsl:attribute>
                  <xsl:element name="interleave" namespace="{$rng-uri}">
                    <xsl:apply-templates
                        select="rng:grammar[descendant::nma:data]"/>
                  </xsl:element>
                </xsl:element>
              </xsl:when>
              <xsl:when test="$target='get-data-reply'">
                <xsl:element name="grammar" namespace="{$rng-uri}">
                  <xsl:attribute name="ns">
                    <xsl:text>urn:ietf:params:xml:ns:yang:ietf-netconf-datastores</xsl:text>
                  </xsl:attribute>
                  <xsl:element name="start" namespace="{$rng-uri}">
                    <xsl:element name="element" namespace="{$rng-uri}">
                      <xsl:attribute name="name">data</xsl:attribute>
                      <xsl:element name="interleave" namespace="{$rng-uri}">
                        <xsl:apply-templates
                            select="rng:grammar[descendant::nma:data]"/>
                      </xsl:element>
                    </xsl:element>
                  </xsl:element>
                </xsl:element>
              </xsl:when>
            </xsl:choose>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='edit-config'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">rpc</xsl:attribute>
            <xsl:call-template name="message-id"/>
            <xsl:element name="element" namespace="{$rng-uri}">
              <xsl:attribute name="name">edit-config</xsl:attribute>
              <xsl:element name="ref" namespace="{$rng-uri}">
                <xsl:attribute name="name">edit-config-parameters</xsl:attribute>
              </xsl:element>
              <xsl:element name="element" namespace="{$rng-uri}">
                <xsl:attribute name="name">config</xsl:attribute>
                <xsl:element name="interleave" namespace="{$rng-uri}">
                  <xsl:apply-templates
                      select="rng:grammar[descendant::nma:data]"/>
                </xsl:element>
              </xsl:element>
            </xsl:element>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='rpc'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">rpc</xsl:attribute>
            <xsl:call-template name="message-id"/>
            <xsl:element name="choice" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="rng:grammar[descendant::nma:rpcs]"/>
            </xsl:element>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='rpc-reply'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">rpc-reply</xsl:attribute>
            <xsl:call-template name="message-id"/>
            <xsl:element name="choice" namespace="{$rng-uri}">
              <xsl:if test="descendant::nma:rpc[not(nma:output)]">
                <xsl:element name="ref" namespace="{$rng-uri}">
                  <xsl:attribute name="name">ok-element</xsl:attribute>
                </xsl:element>
              </xsl:if>
              <xsl:apply-templates
                  select="rng:grammar[descendant::nma:output]"/>
            </xsl:element>
          </xsl:element>
        </xsl:when>
        <xsl:when test="$target='notification'">
          <xsl:element name="element" namespace="{$rng-uri}">
            <xsl:attribute name="name">notification</xsl:attribute>
            <xsl:element name="ref" namespace="{$rng-uri}">
              <xsl:attribute name="name">eventTime-element</xsl:attribute>
            </xsl:element>
            <xsl:element name="choice" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="rng:grammar[descendant::nma:notification]"/>
            </xsl:element>
          </xsl:element>
        </xsl:when>
      </xsl:choose>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="rng:grammar">
    <xsl:variable
        name="subtree"
        select="descendant::nma:data[
                $target='data' or $target='config' or
                $target='edit-config' or $target='get-reply'
                or $target='get-data-reply'
                or $target='get-config-reply']
                |descendant::nma:rpcs[$target='rpc' or
                $target='rpc-reply']
                |descendant::nma:notifications[$target='notification']"/>
    <xsl:if test="$subtree//rng:*">
      <xsl:element name="grammar" namespace="{$rng-uri}">
        <xsl:attribute name="ns">
          <xsl:value-of select="@ns"/>
        </xsl:attribute>
        <xsl:if test="$target='edit-config'">
          <xsl:call-template name="include-grammar">
            <xsl:with-param
                name="file-name"
                select="concat($schema-dir,'/edit-config-attributes.rng')"/>
          </xsl:call-template>
        </xsl:if>
        <xsl:if test="/rng:grammar/rng:define">
          <xsl:call-template name="include-grammar">
            <xsl:with-param name="file-name" select="$gdefs-file"/>
          </xsl:call-template>
        </xsl:if>
        <xsl:element name="start" namespace="{$rng-uri}">
          <xsl:apply-templates select="$subtree"/>
        </xsl:element>
        <xsl:apply-templates select="rng:define"/>
      </xsl:element>
    </xsl:if>
  </xsl:template>

  <xsl:template match="nma:data">
    <xsl:apply-templates select="rng:*"/>
  </xsl:template>

  <xsl:template match="nma:rpcs">
    <xsl:choose>
      <xsl:when test="$target='rpc'">
        <xsl:choose>
          <xsl:when test="count(nma:rpc)>1">
            <xsl:element name="choice" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="descendant::nma:input"/>
            </xsl:element>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates
                select="descendant::nma:input"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:when>
      <xsl:otherwise>
        <xsl:choose>
          <xsl:when test="count(descendant::nma:output)>1">
            <xsl:element name="choice" namespace="{$rng-uri}">
              <xsl:apply-templates
                  select="descendant::nma:output"/>
            </xsl:element>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates
                select="descendant::nma:output"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="nma:notifications">
    <xsl:choose>
      <xsl:when test="count(nma:notification)>1">
        <xsl:element name="choice" namespace="{$rng-uri}">
          <xsl:apply-templates select="nma:notification"/>
        </xsl:element>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="nma:notification"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="nma:input|nma:output">
    <xsl:choose>
      <xsl:when test="count(rng:*)>1">
        <xsl:element name="group" namespace="{$rng-uri}">
          <xsl:apply-templates select="rng:*"/>
        </xsl:element>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="rng:*"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="nma:notification">
    <xsl:choose>
      <xsl:when test="count(rng:*)>1">
        <xsl:element name="interleave" namespace="{$rng-uri}">
          <xsl:apply-templates select="rng:*"/>
        </xsl:element>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="rng:*"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="@nma:*|nma:*|a:*"/>

  <xsl:template match="@*">
    <xsl:copy/>
  </xsl:template>

  <xsl:template match="rng:*">
    <xsl:choose>
      <xsl:when
          test="@nma:config='false' and
                ($target='get-config-reply' or $target='config'
                or $target='edit-config')">
        <xsl:element name="empty" namespace="{$rng-uri}"/>
      </xsl:when>
      <xsl:when
          test="@nma:when and
                not(parent::rng:optional or parent::rng:zeroOrMore)">
        <xsl:element name="choice" namespace="{$rng-uri}">
          <xsl:element name="empty" namespace="{$rng-uri}"/>
          <xsl:apply-templates select="." mode="process"/>
        </xsl:element>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="." mode="process"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="*">
    <xsl:copy-of select="."/>
  </xsl:template>

  <xsl:template match="rng:oneOrMore" mode="process">
    <xsl:choose>
      <xsl:when test="$target='edit-config'">
        <xsl:element name="rng:zeroOrMore">
          <xsl:apply-templates select="@*"/>
          <xsl:apply-templates select="rng:*"/>
        </xsl:element>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="copy-and-continue"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="rng:element" mode="process">
    <xsl:choose>
      <xsl:when test="$target='edit-config'">
        <xsl:choose>
          <xsl:when test="parent::rng:optional or
                          parent::rng:zeroOrMore or
                          parent::rng:oneOrMore or
                          contains(concat(../@nma:key,'
                          '),concat(@name,' '))">
            <xsl:apply-templates select="." mode="edit"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:element name="optional" namespace="{$rng-uri}">
              <xsl:apply-templates select="." mode="edit"/>
            </xsl:element>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="copy-and-continue"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="rng:*" mode="process">
    <xsl:call-template name="copy-and-continue"/>
  </xsl:template>

  <xsl:template match="rng:element" mode="edit">
    <xsl:copy>
      <xsl:apply-templates select="@*|*|text()"/>
      <xsl:if test="not(rng:parentRef[@name='__anyxml__'])">
        <xsl:element name="ref" namespace="{$rng-uri}">
          <xsl:attribute name="name">operation-attribute</xsl:attribute>
        </xsl:element>
        <xsl:choose>
          <xsl:when test="@nma:leaf-list='true' and @nma:ordered-by='user'">
            <xsl:element name="ref" namespace="{$rng-uri}">
              <xsl:attribute name="name">yang-leaf-list-attributes</xsl:attribute>
            </xsl:element>
          </xsl:when>
          <xsl:when test="@nma:key and @nma:ordered-by='user'">
            <xsl:element name="ref" namespace="{$rng-uri}">
              <xsl:attribute name="name">yang-list-attributes</xsl:attribute>
            </xsl:element>
          </xsl:when>
        </xsl:choose>
      </xsl:if>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
