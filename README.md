# XSIDirParser

Broadsoft XSI Directory parser and converter.

XSIDirParser is a Python module scripr that connects to an XSI server, download a directory and convert the content into another format.

XSIDirParser can be used as a Python module in your code. The parser is easy to extended.

## Command line usage

As a script the XSIDirParser can be lauched from the command line:

```
pietro$ python XSIDirParser.py -h

Usage:

-H --host            set the XSI server
-u --user            set the authentication username, MANDATORY
-p --password        set the authentication password, MANDATORY
-n --name            set the directory name (supported only 'Group' and 'Personal'), default: Group
-t --type            set the output type (supported: 'JSON', 'SNOM_TBOOK', 'SNOM_MB', 'XCAP'), default: JSON
```

### Examples

#### Convert an XSI 'Personal' directory in a snom tbook xml format:

```
pietro$ python ./XSIDirParser.py -H xsi.test.server -u user@testdomain.com -p mypass -n Personal -t SNOM_TBOOK

<?xml version="1.0" encoding="utf-8"?>
<tbook e="2" complete="False">
	<item context="active" type="" fav="false" mod="true" index="1">
		<number>1034</number>
		<name>User1</name>
	</item>
	<item context="active" type="" fav="false" mod="true" index="2">
		<number>1035</number>
		<name>User2</name>
	</item>
</tbook>
```

#### Convert an XSI 'Group' directory in a JSON format:

```
pietro$ python ./XSIDirParser.py -H xsi.test.server -u user@testdomain.com -p mypass -n Group -t JSON

[
    {
        "extension": "123",
        "firstName": "Test",
        "lastName": "Test1",
        "userId": "test1",
        "number": "+123456",
        "hiranganaLastName": "1",
        "roomId": "1234",
        "hiranganaFirstName": "Test1",
        "bridgeId": "TEST1-Default",
        "impId": "test1@domain.com",
        "groupId": "TEST",
        "additionalDetails": ""
    },
    {
        "extension": "124",
        "firstName": "Test",
        "lastName": "Test2",
        "userId": "test2",
        "number": "+123457",
        "hiranganaLastName": "1",
        "roomId": "1235",
        "hiranganaFirstName": "Test2",
        "bridgeId": "TEST2-Default",
        "impId": "test2@domain.com",
        "groupId": "TEST",
        "additionalDetails": ""
    },   
    [...]
]
```