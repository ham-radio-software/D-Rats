<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="html"/>

    <xsl:template match="form">
      <html>
	<head>
	  <style type="text/css">
	    .field {
   	       border: 1px solid black
	    }

	    .label {
	       border: 1px solid black;
	       background-color: silver;
	       text-align: center;
	    }

	    .group {
	       width: 80%;
	    }

	    .field-caption {
	       font-size: 60%;
	       font-weight: bold;
	    }

	    .field-content {
	       font-family: Arial, Helvetica, sans-serif;
	    }

	    .title {
	       text-align: center;
	    }

	    .shaded {
	       background-color: silver;
	    }

	    .grouping {
	       border-spacing: 2px;
	    }

	  </style>
	</head>
	<body>

	  <h1 class="title">
	    <xsl:value-of select="title"/>
	  </h1>

	  <div align="center">
	    <table>
	      <tr>
		<td class="field"> From: 
		  <b><xsl:value-of select="path/src"/></b>
		</td>
		<td class="field"> To:
		  <b><xsl:value-of select="path/dst"/></b>
		</td>
	      </tr>
	    </table>
	  </div>

	  <table>
	      <xsl:apply-templates select="field"/>
	  </table>
	  </body>
	</html>
    </xsl:template>
    
    <xsl:template match="field">
      <xsl:variable name="span">
	<xsl:choose>
	  <xsl:when test="entry[@type='label']">
	    <xsl:text>2</xsl:text>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:text>1</xsl:text>
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <xsl:variable name="class">
	<xsl:choose>
	  <xsl:when test="entry[@type='label']">
	    <xsl:text>label</xsl:text>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:text>field</xsl:text>
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:variable>
      <tr class="field">
        <td class="{$class}" colspan="{$span}">
	  <span class="field-caption">
	    <xsl:value-of select="caption"/>
	  </span>
	</td>
	<xsl:if test="entry[@type!='label']">
	  <td class="field" width="100%">
	    <span class="field-content">
	      <xsl:choose>
		<xsl:when test="entry/@type = 'choice'">
		  <xsl:value-of select="entry/choice[@set='y']"/>
		</xsl:when>
		<xsl:when test="entry/@type = 'multiselect'">
		  <table class="grouping"><tr>
		      <xsl:apply-templates select="entry/choice"/>
		  </tr></table>
		</xsl:when>
		<xsl:otherwise>
		  <xsl:value-of select="entry"/>
		</xsl:otherwise>
	      </xsl:choose>
	      <xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text>
	    </span>
	  </td>
	</xsl:if>
      </tr>
    </xsl:template>

    <xsl:template match="choice">
      <td class="shaded">
      <xsl:choose>
	<xsl:when test="@set='y'">
	  <input type="checkbox" checked="checked"/>
	</xsl:when>
	<xsl:otherwise>
	  <input type="checkbox"/>
	</xsl:otherwise>
      </xsl:choose>
      <xsl:value-of select="."/>
      </td>
    </xsl:template>

</xsl:stylesheet>
