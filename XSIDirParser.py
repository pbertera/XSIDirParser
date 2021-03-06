# -*- coding: utf-8; -*-
#
# (C) 2015 Bertera Pietro <pietro@bertera.it>
#
# XSIDirParser is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# XSIDirParser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with XSIDirParser.  If not, see <http://www.gnu.org/licenses/>.
#
# TODO:
# - PEP-8
# - Python 3
# - Use requests instead of httplib
# - Debug option to dump all the data
# - Derive a generic tool to query XSI actions

import http.client
import base64
import xml.etree.ElementTree as ET
import re
import pprint

XSI_NAMESPACE = '{http://schema.broadsoft.com/xsi}'

class XSIHTTPException(Exception):
    pass
class XSISetupException(Exception):
    pass

class XSIDirectory:
    '''Class representing the XSIDirectory'''
    def __init__(self, host, username, password='', port=None, schema='http', sip_user=None, name='Group', query='', timeout=None, source_address=None, skip_tags=[], select_tags=[], fields_map={}):
        '''Instantiate an XSIDirectory object creating a connection to the XSI Server:

        Keyword arguments:
        - 'host': the XSI serve name
        - 'username': the authentication username
        - 'password': the authentication password
        - 'port': the TCP port to use for the connection. If 'None' 80 is used with 'http' an 443 for 'https'
        - 'schema': protocol schema, can be 'http' or 'https'. If wrong schema is passed a 'XSISetupException' is raised
        - 'sip_user': if Broadworks SIP authentication must be used, this define the SIP username, if not defined normal authentication is used
        - 'name': the directory name (default 'Group')
        - 'query': optional query string (used for filtering or pagination, see the Broadworks XSI documentation)
        - 'timeout': connection timeout
        - 'source_address': the source IP address of the query
        - 'skip_tags': a list of tags to ignore (tags name are case sensitive)
        - 'select_tags': a list of tags to extract
        - 'fields_map': a dictionary containing a tag renamig map (Example: fields_map={'emailAddress': 'email_address'} the tag **emailAddress** will be renamed in **email_address**
        '''

        self.host = host
        self.username = username
        self.password = password
        self.schema = schema
        self.sip_user = sip_user
        self.name = name
        if self.name == 'Group':
            self.parse = self._parseGroup
        elif self.name == "Personal":
            self.parse = self._parsePersonal
        else:
            raise XSISetupException("ERROR: addressbook '%s' not supported" % self.name)
        self.timeout = timeout
        self.source_address = source_address
        self.skip_tags = skip_tags
        self.select_tags = select_tags
        self.fields_map = fields_map

        if query != '':
            self.query = '?' + query
        else:
            self.query = query

        if self.schema == 'http' and port == None:
            self.port = 80
        elif self.schema == 'https' and port == None:
            self.port = 443
        elif port != None and self.schema in ('http','https'):
            self.port = int(port)
        print("Host: %s" % self.host)
        print("Port: %d" % self.port)
        if self.schema == 'http':
            self.connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout, source_address=self.source_address)
        elif self.schema == 'https':
            self.connection = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout, source_address=self.source_address)
        else:
            raise XSISetupException("ERROR: Schema %s not supported" % schema)
        self.directory = []

    def _setupURL(self):
        self.url = '/com.broadsoft.xsi-actions/v2.0/user/{username}/directories/{name}{query}'.format(username=self.username, name=self.name, query=self.query)

    def getDirectory(self):
        """This method sends the request to the server, returns the requested URI. In case the server responds with an error the exception 'XSIHTTPException' is raised.
        If the request succeded with no issues 'self.raw_data' will contains the raw XML and 'self.xml_root' will contains the **xml.etree.ElementTree** object. 
        """

        headers = {}
        if self.password != '':
            if self.sip_user:
                headers["Authorization"] = "BroadWorksSIP basic=\"" + str(base64.b64encode(bytes('%s:%s' % (self.username, self.password), 'utf-8')))[:-1] + \
                        "\",sipUser=\"" + str(base64.b64encode( bytes(self.sip_user, "utf-8") ))[:-1]
            else:
                headers["Authorization"] = "Basic " + str(base64.b64encode(bytes('%s:%s' % (self.username, self.password), 'utf-8')))[:-1]
        print(headers)
        self._setupURL()
        try:
            self.connection.request('GET', self.url, headers=headers)
        except Exception as e:
            raise XSIHTTPException("ERROR: cannot download the XSI directory at %s: %s" % (self.url, e))
        self.response = self.connection.getresponse()
        if self.response.status == 200:
            self.raw_data = self.response.read()
            self.xml_root = ET.fromstring(self.raw_data)
        else:
            raise XSIHTTPException("ERROR: cannot download the XSI directory, Received Response %d %s:\n%s" % (self.response.status, self.response.reason, self.response.read()))
        return self.url

    def _filter_tag(self, tag):
        if tag in self.skip_tags:
            return None
        if len(self.select_tags) > 0 and tag not in self.select_tags:
            return None
        if tag in list(self.fields_map.keys()):
            tag = self.fields_map[tag]
        return tag.encode('utf-8')

    def _parseGroup(self):
        """This method walks into the 'self.xml_root' **xml.etree.ElementTree** object and extract all the tags contained into the **./groupDirectory/directoryDetails** XML path.
        If the **additionalDetails** child tags is found will be parsed too.
        Tags name mentioned into the 'self.skip_tags' list will be ignored.
        If 'self.select_tags' contains some more then one tag name only that tags are extracted.
        The tag renaming map 'self.fields_map' is applied to the tags name.
        """

        start_xpath = "./{ns}groupDirectory/{ns}directoryDetails".format(ns=XSI_NAMESPACE)
        for contact in self.xml_root.findall(start_xpath):
            contact_dict = {}
            for tag in contact.findall('./*'):
                tag_name = re.sub(XSI_NAMESPACE, '', tag.tag, 1)
                # Enter into the additionalDetails tag
                if tag_name == 'additionalDetails':
                    for details_tag in tag.findall('./*'):
                        details_tag_name = re.sub(XSI_NAMESPACE, '', details_tag.tag, 1)
                        details_tag_name = self._filter_tag(details_tag_name)
                        if details_tag_name == None:
                            continue
                        else:
                            if details_tag.text == None:
                                contact_dict[details_tag_name] = ''
                            else:
                                contact_dict[details_tag_name] = details_tag.text.encode('utf-8')
                tag_name = self._filter_tag(tag_name)
                if tag_name == None:
                    continue
                else:
                    if tag.text == None:
                        contact_dict[tag_name] = ''
                    else:
                        contact_dict[tag_name] = tag.text.encode('utf-8')

            self.directory.append(contact_dict)

    def _parsePersonal(self):
        """This method walks into the 'self.xml_root' **xml.etree.ElementTree** object and extract all the tags contained into the **./entry** XML path.
        Tags name mentioned into the 'self.skip_tags' list will be ignored.
        If 'self.select_tags' contains some more then one tag name only that tags are extracted.
        The tag renaming map 'self.fields_map' is applied to the tags name.
        """
        start_xpath = "./{ns}entry".format(ns=XSI_NAMESPACE)

        for contact in self.xml_root.findall(start_xpath):
            contact_dict = {}
            for tag in contact.findall('./*'):
                tag_name = re.sub(XSI_NAMESPACE, '', tag.tag, 1)
                tag_name = self._filter_tag(tag_name)
                if tag_name == None:
                    continue
                else:
                    if tag.text == None:
                        contact_dict[tag_name] = ''
                    else:
                        contact_dict[tag_name] = tag.text.encode('utf-8')
            self.directory.append(contact_dict)
    def __str__(self):
        return pprint.pformat(self.directory)

class XSI2XCAP(XSIDirectory):
    """A class representing an XSI to XCAP contacts parsing"""

    def __init__(self, host, username, password, port=None, schema='http', sip_user=None, name='Group', query='', timeout=None, source_address=None):
        if name == 'Group':
            xsi_select_tags = ['directoryDetails', 'firstName', 'lastName', 'extension', 'number', 'emailAddress', 'mobile', 'pager', 'groupId']
            xsi_fields_map = {
                'groupId': 'company',
                'emailAddress': 'email_address',
                'firstName': 'given_name',
                'lastName': 'surname',
                'mobile': 'mobile_number',
                'extension': 'business_number',
                'number': 'business_number#1'
                }
        elif name == 'Personal':
            xsi_select_tags = ['name', 'number']
            xsi_fields_map = {
                'name': 'surname',
                'number': 'business_number'
                    }
        self.format_dn = '%(surname)s'
        
        XSIDirectory.__init__(self, host, username, password, port=port, schema=schema, sip_user=sip_user, name=name, query=query, timeout=timeout, source_address=source_address, skip_tags=[], select_tags=xsi_select_tags, fields_map=xsi_fields_map)

    def __str__(self):
        ret = '<?xml version="1.0" encoding="UTF-8"?>\n'
        ret += '<resource-lists xmlns="urn:ietf:params:xml:ns:resource-lists" xmlns:cp="counterpath:properties">\n'
        ret += '\t<list name="Contact List">\n'
        
        for contact in self.directory:
            ret += '\t\t<entry>\n'
            ret += '\t\t\t<display-name>%s</display-name>\n' % self._formatDisplayName(contact)
            for prop in list(contact.keys()):
                ret += '\t\t\t<cp:prop name="%s" value="%s"/>\n' % (prop, contact[prop])
            ret += '\t\t</entry>\n'
        
        ret += '\t</list>\n'
        ret += '</resource-lists>\n'
        return ret
    
    def _formatDisplayName(self, contact):
        return self.format_dn % contact

class XSI2SnomMB(XSIDirectory):
    """A class representing an XSI 2 Snom Minibrowser application parser"""

    def __init__(self, host, username, password, port=None, schema='http', sip_user=None, name='Group', query='', timeout=None, source_address=None):
        
        if name == 'Group':
            snom_select_tags = ['firstName', 'lastName', 'extension', 'number', 'emailAddress', 'mobile']
            self.format_dn = '%(firstName)s - %(lastName)s'
        
        if name == 'Personal':
            snom_select_tags = ['name', 'number']
            self.format_dn = '%(name)s'

        XSIDirectory.__init__(self, host, username, password, port=port, schema=schema, sip_user=sip_user, name=name, query=query, timeout=timeout, source_address=source_address, skip_tags=[], select_tags=snom_select_tags)
    
    def __str__(self):
        ret = '<?xml version="1.0" encoding="UTF-8"?>\n'
        ret += '<SnomIPPhoneMenu xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="../minibrowser_test.xsd">\n'
        
        for contact in self.directory:
            ret += '\t<Menu name="%s">\n' % self._formatDisplayName(contact)
            if 'mobile' in list(contact.keys()):
                ret += '\t\t<MenuItem name="Mobile: %s">\n' % contact['mobile']
                ret += '\t\t\t<URL>snom://mb_nop#numberdial=%s</URL>\n' % contact['mobile']
                ret += '\t\t</MenuItem>\n'
            if 'number' in list(contact.keys()):
                ret += '\t\t<MenuItem name="Number: %s">\n' % contact['number']
                ret += '\t\t\t<URL>snom://mb_nop#numberdial=%s</URL>\n' % contact['number']
                ret += '\t\t</MenuItem>\n'
            if 'extension' in list(contact.keys()):
                ret += '\t\t<MenuItem name="Extension: %s">\n' % contact['extension']
                ret += '\t\t\t<URL>snom://mb_nop#numberdial=%s</URL>\n' % contact['extension']
                ret += '\t\t</MenuItem>\n'
            if 'emailAddress' in list(contact.keys()):
                ret += '\t\t<MenuItem name="Email: %s"/>\n' % contact['emailAddress']
            ret += '\t</Menu>\n'
        ret += '</SnomIPPhoneMenu>\n'
        return ret
    
    def _formatDisplayName(self, contact):
        return self.format_dn % contact

class XSI2SnomTbook(XSIDirectory):
    """A class representing an XSI 2 Snom tbook parser (http://wiki.snom.com/Features/Mass_Deployment/Setting_Files/XML/Directory)"""
    
    def __init__(self, host, username, password, complete=True, port=None, schema='http', sip_user=None, name='Group', query='', timeout=None, source_address=None):
       
        self.complete = complete

        if name == 'Personal':
            tbook_select_tags = ['name', 'number']
            self.format_dn = '%(name)s'
        else:
            raise XSISetupException("ERROR: Directory type '%s' not supported" % name)
        
        XSIDirectory.__init__(self, host, username, password, port=port, schema=schema, sip_user=sip_user, name=name, query=query, timeout=timeout, source_address=source_address, skip_tags=[], select_tags=tbook_select_tags)
    
    def __str__(self):
        ret = '<?xml version="1.0" encoding="utf-8"?>\n'
        ret += '<tbook e="2" complete="%r">\n' % self.complete
        index = 1
        for contact in self.directory:
            ret += '\t<item context="active" type="" fav="false" mod="true" index="%d">\n' % index
            ret += '\t\t<number>%s</number>\n' % contact['number']
            ret += '\t\t<name>%s</name>\n' % contact['name']
            ret += '\t</item>\n'
            index = index + 1
        ret += '</tbook>'
        return ret

class XSI2Json(XSIDirectory):
    """A class representing an XSI 2 Json parser"""
    def __init__(self, host, username, password, port=None, schema='http', sip_user=None, name='Group', query='', timeout=None, source_address=None):
        XSIDirectory.__init__(self, host, username, password, port=port, schema=schema, sip_user=sip_user, name=name, query=query, timeout=timeout, source_address=source_address)
    
    def __str__(self):
        import json
        return json.dumps(self.directory, indent=4, separators=(',', ': '))

if __name__ == '__main__':
    import getopt
    import sys

    def usage(msg=None):
        if msg:
            print(("ERROR: %s" % msg))
        print("Usage:\n")
        print("-H --host            set the XSI server")
        print("-P --port            set the HTTP(s) port")
        print("-S --scheme          set the protocol scheme (http or https)")
        print("-u --user            set the authentication username, MANDATORY")
        print("-p --password        set the authentication password, MANDATORY")
        print("-n --name            set the directory name (supported only 'Group' and 'Personal'), default: Group")
        print("-t --type            set the output type (supported: 'JSON', 'SNOM_TBOOK', 'SNOM_MB', 'XCAP'), default: JSON")
        print("-s --sip-auth        set the XSI SIP authentication username, if set the script will authenticate using the BroadWorksSIP hash")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "H:P:S:u:p:n:t:s:", ["host=", "user=", "password=", "name=", "type=", "sip-auth="])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(2)

    host = port = user = password = None
    out_type = 'JSON'
    name = 'Group'
    sip_user = None
    schema = 'http'

    for o, val in opts:
        if o in ('-H', '--host'):
            host = val
        if o in ('-P', '--port'):
            port = val
        if o in ('-S', '--scheme'):
            if val in ('http', 'https'):
                schema = val
            else:
                usage('scheme must be http or https')
                sys.exit(2)
        elif o in ('-u', '--user'):
            user = val
        elif o in ('-p', '--password'):
            password = val
        elif o in ('-s', '--sip-auth'):
            sip_user = val
        elif o in ('-n', '--name'):
            if val in ('Group', 'Personal'):
                name = val
            else:
                usage("name '%s' not supported" % val)
                sys.exit(2)
        elif o in ('-t', '--type'):
            if val in ('JSON', 'SNOM_TBOOK', 'SNOM_MB', 'XCAP'):
                out_type = val
            else:
                usage("output type '%s' not supported" % val)
                sys.exit(2)

    # host, user and password are mandatory
    if host == None:
        usage("host not defined")
        sys.exit(2)
    if user == None:
        usage("user not defined")
    if password == None:
        usage("password not defined")

    if out_type == 'JSON':
        directory = XSI2Json(host, user, password, port=port, schema=schema, name=name, sip_user=sip_user)
    if out_type == 'SNOM_TBOOK':
        # set the complete=false:
        directory = XSI2SnomTbook(host, user, password, name=name, complete=False, sip_user=sip_user)
    if out_type == 'SNOM_MB':
        directory = XSI2SnomMB(host, user, password, name=name, sip_user=sip_user)
    if out_type == 'XCAP':
        directory = XSI2XCAP(host, user, password, name=name, sip_user=sip_user)

    # send the request
    directory.getDirectory()

    # parse the result
    directory.parse()

    # print the parsed output
    print(directory)
