<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="html"/>

    <xsl:template match="form">
      <html>
	<head>
	  <style type="text/css">
	    
	    div.field {
	       border: 1px solid black;
	    }

	    .title {
	       width: 100%;
	       text-align: center;
	       border: thin black solid;
	       font-size: 130%;
	       font-weight: bold;
	    }

	    .line {
	       width: 100%;
	    }

	    span.selected {
	      font-weight: bold;
	    }

	    .element {
	       width: 100%;
	       height: 30;
               font-size: 60%;
	       vertical-align: top;
	       border-spacing: 0px;
	       border-collapse: collapse;
	       border: 1px solid black
	    }

	    .big-header {
	       width: 100%;
	       font-weight: bold;
	       font-size: 85%;
	       background-color: silver;
	       border: 1px solid black;
	       border-spacing: 0px;
	       border-collapse: collapse;
	    }

	    td.element {
	      width: 25%;
	    }
	    
	    .bigelement {
  	       width: 100%;
	       font-size: 60%;
	       vertical-align: top;
	       border: 1px solid black;
	    }

	    table {
	       border-collapse: collapse;
	       border-spacing: 0px;
	       border: none;
	       padding-top: 0px;
	       padding-bottom: 0px;
	       margin: 0px 0px;
	    }

	    td {
	      margin: 0px 0px;
	      padding: 0px 0px;
	    }
	    
	    .form {
	       width: 95%;
	       border-spacing: 0px;
	       border-collapse: collapse;
	       padding-top: 0px;
	       padding-bottom: 0px;
	    }

	    .field-caption {
	       font-weight: normal;
	       vertical-align: top
	    }

	    .hfield-caption {
	       font-weight: bold;
	       background-color: silver;
	       vertical-align: top;
	    }

	    .small-header {
	       width: 100%;
	       font-size: 85%;
	       font-weight: bold;
	       border: 1px solid black;
	    }

	    .field-content {
	       font-family: Arial, Helvetica, sans-serif;
	       white-space: pre;
	    }

	    .fineprint {
	       font-size:40%;
	    }

	  </style>
	</head>
	<body>
	  <div align="center">
	  <table class="form" cellpadding="0" align="center">
	    <tr><td><div class="title"><xsl:value-of select="title"/></div></td></tr>

	    <tr><td>

		<table class="line">
		  <tr>
		    <td width="50%">
		      <xsl:apply-templates select="field[@id='date']"/>
		    </td>
		    <td width="50%">
		      <xsl:apply-templates select="field[@id='unit']"/>
		    </td>
		  </tr>
		</table>

	    </td></tr><tr><td>

		<table class="line">
		  <tr class="group">
		    <td width="33%">
		      <xsl:apply-templates select="field[@id='patient_name']"/>
		    </td><td width="33%">
		      <xsl:apply-templates select="field[@id='patient_age']"/>
		    </td><td width="33%">
		      <xsl:apply-templates select="field[@id='patient_mrnum']"/>
		    </td>
		  </tr>

		</table>
	    </td></tr>
	    <tr><td>
		<table class="line">
		  <tr class="group">
		    <td width="50%">
		      <xsl:apply-templates select="field[@id='diagnosis']"/>
		    </td><td width="50%">
		      <xsl:apply-templates select="field[@id='physician']"/>
		    </td>
		  </tr>
		</table>
	    </td></tr>
	    <tr><td>
		<table class="line">
		  <tr class="group">
		    <td>
		      <xsl:apply-templates select="field[@id='family_notified']"/>
		    </td>
		  </tr>
		</table>
	    </td></tr>
	    <tr><td>
		<table class="line">
		  <tr class="group">
		    <td>
		      <div class="big-header">9.ACCOMPANYING EQUIPMENT</div>
		    </td>
		  </tr>
		</table>
	    </td></tr><tr><td>
		<table class="line">
		  <tr class="group">
		    <td>
		      <xsl:apply-templates select="field[@id='equipment']"/>
		    </td>
		  </tr>
		</table>
	    </td></tr><tr><td>
		<table class="line">
		  <tr>
		    <td width="50%">
		      <div class="big-header">10. DEPARTING LOCATION</div>
		    </td>
		    <td width="50%">
		      <div class="big-header">11. ARRIVING LOCATION</div>
		    </td>
		  </tr>
		</table>
	      </td></tr>
	    <tr><td>
		<table class="line">
		  <tr><td width="50%">
		      <table class="line">
			<tr class="group">
			  <td width="50%">
			    <xsl:apply-templates select="field[@id='depart_room']"/>
			  </td><td width="50%">
			    <xsl:apply-templates select="field[@id='depart_time']"/>
			  </td>
			</tr><tr>
			  <td>
			    <xsl:apply-templates select="field[@id='depart_idband']"/>
			  </td><td>
			    <xsl:apply-templates select="field[@id='depart_idconf']"/>
			  </td>
			</tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='depart_record']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='depart_address']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='depart_belongings']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='depart_valuables']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='depart_medications']"/>
			</td></tr>
		      </table>
		    </td><td width="50%">
		      <table class="line">
			<tr class="group">
			  <td>
			    <xsl:apply-templates select="field[@id='arrive_room']"/>
			  </td><td>
			    <xsl:apply-templates select="field[@id='arrive_time']"/>
			  </td>
			</tr><tr><td>
			    <xsl:apply-templates select="field[@id='arrive_idband']"/>
			  </td><td>
			    <xsl:apply-templates select="field[@id='arrive_idconf']"/>
			</td></tr>
			<tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='arrive_record']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='arrive_address']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='arrive_belongings']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='arrive_valuables']"/>
			</td></tr><tr><td colspan="2">
			    <xsl:apply-templates select="field[@id='arrive_medications']"/>
			</td></tr>
		      </table>
		  </td></tr>
		</table>
	    </td></tr>
	    <tr><td>
		<div class="small-header">PEDS/INFANTS</div>
	    </td></tr>
	    <tr><td>
		<table class="line">
		  <tr class="group">
		    <td width="50%">
		      <xsl:apply-templates select="field[@id='bagmasktubing_sent']"/>
		    </td><td width="50%">
		      <xsl:apply-templates select="field[@id='bagmasktubing_recv']"/>
		    </td>
		  </tr><tr>
		    <td>
		      <xsl:apply-templates select="field[@id='bulb_sent']"/>
		    </td><td>
		      <xsl:apply-templates select="field[@id='bulb_recv']"/>
		    </td>
		  </tr>
		</table>
	    </td></tr>
	    <tr><td>
		<div class="big-header">
		  12. TRANSFERRING TO ANOTHER FACILITY
		</div>
	    </td></tr>
	    <tr><td>
		<table class="line">
		  <tr class="group">
		    <td width="50%">
		      <xsl:apply-templates select="field[@id='time_to_staging']"/>
		    </td><td width="50%">
		      <xsl:apply-templates select="field[@id='time_depart_to_recv']"/>
		    </td>
		  </tr>
		  <tr><td colspan="2">
		      <xsl:apply-templates select="field[@id='destination']"/>
		  </td></tr>
		  <tr><td colspan="2">
		      <xsl:apply-templates select="field[@id='transport']"/>
		  </td></tr>
		  <tr><td colspan="2">
		      <xsl:apply-templates select="field[@id='idband_conf']"/>
		  </td></tr>
		  <tr><td colspan="2">
		      <xsl:apply-templates select="field[@id='fac_depart_time']"/>
		  </td></tr>
		  <tr><td colspan="2">
		      <xsl:apply-templates select="field[@id='depart_facility']"/>
		  </td></tr>
		</table>
	      </td></tr>
	  </table>
 	  </div>
	  <div align="right" class="form">
	    <span class="fineprint">
	      Electronic version: Generated by D-RATS
	    </span>
	  </div>

	</body>
      </html>
    </xsl:template>

    <xsl:template match="choice">
      <xsl:choose>
	<xsl:when test="@set='y'">
	  <input type="checkbox" checked="checked"/>
	</xsl:when>
	<xsl:otherwise>
	  <input type="checkbox"/>
	</xsl:otherwise>
      </xsl:choose>
      <xsl:value-of select="."/>
    </xsl:template>

    <xsl:template match="entry">
      <xsl:choose>
	<xsl:when test="@type = 'choice'">
	  <xsl:value-of select="choice[@set='y']"/>
	</xsl:when>
	<xsl:when test="@type = 'multiselect'">
	  <table width="100%">
	      <xsl:for-each select="choice[(position() mod 4) = 1]">
		<tr>
		  <td class="element"><xsl:apply-templates select="."/></td>
		  <td class="element"><xsl:apply-templates select="following-sibling::choice[position() = 1]"/></td>
		  <td class="element"><xsl:apply-templates select="following-sibling::choice[position() = 2]"/></td>
		  <td class="element"><xsl:apply-templates select="following-sibling::choice[position() = 3]"/></td>
		</tr>
	      </xsl:for-each>
	  </table>
	</xsl:when>
	<xsl:when test="@type='toggle'">
	  <xsl:choose>
	    <xsl:when test=". = 'True'">
	      <input type="checkbox" checked="checked"/>
	      <xsl:text>YES   </xsl:text>
	      <input type="checkbox"/>
	      <xsl:text> NO</xsl:text>
	    </xsl:when>
	    <xsl:otherwise>
	      <input type="checkbox"/>
	      <xsl:text>YES   </xsl:text>
	      <input type="checkbox" checked="checked"/>
	      <xsl:text> NO</xsl:text>
	    </xsl:otherwise>
	  </xsl:choose>
	</xsl:when>
	<xsl:otherwise>
	  <xsl:value-of select="."/>
	</xsl:otherwise>
      </xsl:choose>
    </xsl:template>

    <xsl:template match="field">
      <xsl:variable name="element_class">
	<xsl:choose>
	  <xsl:when test="entry[@type='multiselect']">
	    <xsl:text>bigelement</xsl:text>
	  </xsl:when>
	  <xsl:otherwise>
	    <xsl:text>element</xsl:text>
	  </xsl:otherwise>
	</xsl:choose>
      </xsl:variable>

      <div class="{$element_class}">
	<span class="field-caption">
	  <xsl:value-of select="caption"/>
	</span>
	<xsl:text>   </xsl:text>
	<span class="field-content">
	  <xsl:apply-templates select="entry"/>
	</span>
      </div>
    </xsl:template>

    <xsl:template name="field">
      <xsl:text>No</xsl:text>
    </xsl:template>

    <xsl:template name="header-field">
      <xsl:param name="caption"/>
      <xsl:param name="value"/>
      <table class="element">
	<tr><td>
	    <span class="hfield-caption">
	      <xsl:value-of select="$caption"/>
	    </span>
	    <xsl:text>   </xsl:text>
	    <span class="field-content">
	      <xsl:value-of select="$value"/>
	    </span>
	</td></tr>
      </table>
    </xsl:template>


</xsl:stylesheet>
