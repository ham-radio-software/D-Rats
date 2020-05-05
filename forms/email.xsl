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

	    td.msg_header_value {
	      text-align: left;
	    }

	    .msg_header_name {
	      font-weight: bold;
	    }

	    .msg_header_value {
	    }

	    .msg_recip {
	      font-size: 120%;
	    }

	  </style>
	</head>
	<body>

	  <table width="90%">
	    <tr>
	      <td>
		<span class="msg_recip">
		  <xsl:value-of select="path/dst"/>
		</span>
	      </td>
	      <td style="text-align: right">
		<xsl:value-of select="title"/>
	      </td>
	    </tr>

	    <tr style="background-color: black;">
	      <td colspan="2"> </td>
	    </tr>

	  </table>
	  <table width="90%">

	    <tr>
	      <td width="10">
		<span class="msg_header_name">From:</span>
	      </td>
	      <td class="msg_header_value">
		<span class="msg_header_value">
		  <xsl:value-of select="path/src"/>
		</span>
	      </td>
	    </tr>
	    <tr>
	      <td>
		<span class="msg_header_name">Subject:</span>
	      </td>
	      <td class="msg_header_value">
		<span class="msg_header_value">
		  <xsl:value-of select="field[@id='subject']/entry"/>
		</span>
	      </td>
	    </tr>
	  </table>

	  <pre>
	    <xsl:value-of select="field[@id='message']/entry" disable-output-escaping="yes"/>
	  </pre>
	</body>
      </html>

    </xsl:template>
</xsl:stylesheet>
