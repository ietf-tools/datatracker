<?xml version="1.0" encoding="utf-8"?>

<!-- This stylesheet composes base file name for output DSDL schemas. -->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:rng="http://relaxng.org/ns/structure/1.0"
                xmlns:nma="urn:ietf:params:xml:ns:netmod:dsdl-annotations:1"
                version="1.0">
  <xsl:output method="text" encoding="utf-8"/>
  <xsl:include href="gen-common.xsl"/>

  <xsl:template match="/">
      <xsl:value-of select="$basename"/>
  </xsl:template>

</xsl:stylesheet>
