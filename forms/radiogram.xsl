<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="html"/>

    <xsl:template match="form">
      <html>
	<head>
	  <style type="text/css">
	    .toplevel {
	      width: 80%;
	      border-spacing: 0px;
	      border-collapse: collapse;
	      padding: 0px;
	    }

	    .group {
	       border-spacing: 0px;
	       border-collapse: collapse;
	       border: 1px solid black
	    }

	    .line {
	       width: 100%;
	    }

	    .title {
	       text-align: center;
	    }

	    table {
	       border-collapse: collapse;
 	       padding: 0px;
	    }

	    .field-caption {
	       font-size: 60%;
	       font-weight: bold;
	       text-align: center;
	       text-transform: uppercase;
	    }

	    .field-content {
	       font-family: Arial, Helvetica, sans-serif;
	       white-space: pre;
	       text-align: center;
	    }

	    .label-text {
	       font-size: 60%;
	       font-weight: bold;
	       white-space: pre;
	       text-transform: uppercase;
	    }	    

	    .main-header {
	       background-color: black;
	       color: white;
	    }

	    .banner {
	       text-align: center;
	       font-weight: bold;
	       text-transform: uppercase;
	    }

	    .pre-banner {
	       font-size: 70%;
	    }

	    .post-banner {
	       font-size: 50%;
	    }

	    div.banner, span.banner {
	       font-size: 120%;
	    }

	    .form, .element {
	       border: thin black solid;
	       border-collapse: collapse;
	       border-spacing: 0px;
	       padding: 0px;
	       margin: 0px;
	    }

	    td, .container {
 	       border-collapse: collapse;
	       border-spacing: 0px;
	       padding: 0px;
	    }
	    
	    .spacebox {
	       padding: 2px;
	    }

	    table {
	       border-collapse: collapse;
	    }

	  </style>
	</head>
	<body>

	  <table class="toplevel">
	    <tr>
	      <td class="form">
		<table width="100%" class="container">
		  <tr class="main-header">
		    <td class="logo"></td>
		    <td class="banner">
		      <div class="pre-banner">The American Radio Relay League</div>
		      <div class="banner">Radiogram</div>
		      <div class="post-banner">via Amateur Radio</div>
		    </td>
		    <td class="logo"></td>
		  </tr>
		</table>
	      </td>
	    </tr>
	    <tr class="container">
	      <td class="form">
		<table width="100%" class="container">
		  <tr>
		    <td>
		      <xsl:apply-templates select="field[@id='_auto_number']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='precedence']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='hx']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='station']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='_auto_check']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='place']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='time']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='date']"/>
		    </td>
		  </tr>
		</table>
	      </td>
	    </tr> <!-- End of header row -->
	    <tr>
	      <td class="form">
		<table width="100%"> <!-- Body -->
		  <tr> <!-- Start of body header -->
		    <td class="spacebox">
		      <div class="label-text">To</div>
		      <xsl:apply-templates select="field[@id='recip']/entry"/>
		      <br/><br/>
		      <div class="label-text">Telephone Number</div>
		      <xsl:apply-templates select="field[@id='recip_phone']/entry"/>
		    </td>
		    <td width="300">
		      <div class="form">
			<div class="spacebox">
			  <div class="label-text">
This radio message was received at

Amateur Station
Name
Street Address
City, State, ZIP
			  </div>
			</div>
		      </div>
		    </td>
		  </tr>
		  <tr> <!-- Spacer --> 
		    <td><br/></td>
		  </tr>
		  <tr> <!-- Message -->
		    <td colspan="2" class="spacebox">
		      <xsl:apply-templates select="field[@id='_auto_message']/entry"/>
		      <br/><br/>
		    </td>
		  </tr>
		</table>
	      </td>
	    </tr> <!-- End of body row -->
	    <tr>
	      <td class="form">
		<table width="100%"> <!-- Path info -->
		  <tr>
		    <td>
		      <xsl:apply-templates select="field[@id='received_from']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='recv_d']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='recv_t']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='sent_to']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='sent_d']"/>
		    </td>
		    <td>
		      <xsl:apply-templates select="field[@id='sent_t']"/>
		    </td>
		  </tr>
		</table>
	      </td>
	    </tr>
	  </table>
	</body>
      </html>
    </xsl:template>

    <xsl:template match="entry">
      <xsl:choose>
	<xsl:when test="@type='choice'">
	  <xsl:value-of select="choice[@set='y']"/>
	</xsl:when>
	<xsl:otherwise>
	  <xsl:value-of select="."/>
	</xsl:otherwise>
      </xsl:choose>
    </xsl:template>

    <xsl:template name="_field">
      <xsl:param name="caption"/>
      <xsl:param name="value"/>
      <table class="element" width="100%">
	<tr>
	  <td class="element_comp">
	    <div class="field-caption">
	      <xsl:value-of select="$caption"/>
	    </div>
	  </td>
	</tr><tr>
	  <td class="element_comp">
	    <div class="field-content">
	      <xsl:value-of select="$value"/>
	      <xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text>
	    </div>
	  </td>
	</tr>
      </table>
    </xsl:template>

    <xsl:template match="field">
      <xsl:call-template name="_field">
	<xsl:with-param name="caption" select="caption"/>
	<xsl:with-param name="value">
	  <xsl:apply-templates select="entry"/>
	</xsl:with-param>
      </xsl:call-template>
    </xsl:template>

</xsl:stylesheet>
