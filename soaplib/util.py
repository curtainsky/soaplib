import httplib
import datetime
import cElementTree as ElementTree

from urllib import quote

def create_relates_to_header(relatesTo,attrs={}):
    '''Creates a 'relatesTo' header for async callbacks'''
    relatesToElement = ElementTree.Element('RelatesTo')
    relatesToElement.set('xmlns','http://schemas.xmlsoap.org/ws/2003/03/addressing')
    for k,v in attrs.items():
        relatesToElement.set(k,v)
    relatesToElement.text = relatesTo
    return relatesToElement

def create_callback_info_headers(messageId,replyTo):
    '''Creates MessageId and ReplyTo headers for initiating an async function'''
    messageIdElement = ElementTree.Element('wsa:MessageID')
    messageIdElement.text = messageId

    replyToElement = ElementTree.Element('wsa:ReplyTo')
    addressElement = ElementTree.SubElement(replyToElement,'wsa:Address')
    addressElement.text = replyTo

    return messageIdElement, replyToElement

def get_callback_info():
    '''Retrieves the messageId and replyToAddress from the message header.
    This is used for async calls.'''
    messageId = None
    replyToAddress = None
    from soaplib.wsgi_soap import request


    headerElement = request.header
    if headerElement:
        headers = headerElement.getchildren()
        for header in headers:
            if header.tag.lower().endswith("messageid"):
                messageId = header.text
            if header.tag.lower().find("replyto") != -1:
                replyToElems = header.getchildren()
                for replyTo in replyToElems:
                    if replyTo.tag.lower().endswith("address"):
                        replyToAddress = replyTo.text
    return messageId, replyToAddress

def create_passthru_headers():
    msgid,replyto = get_callback_info()
    return create_callback_info_headers(msgid,replyto)

def get_relates_to_info():
    '''Retrives the relatesTo header. This is used for callbacks'''
    from soaplib.wsgi_soap import request

    headerElement = request.header
    if headerElement:
        headers = headerElement.getchildren()
        for header in headers:
            if header.tag.lower().find('relatesto') != -1:
                return header.text

def split_url(url):
    '''Splits a url into (host:port, path)'''
    wsdlstr = url.split('://')[-1]
    parts = wsdlstr.split('/')
    host = parts[0]
    path = '/'+'/'.join(parts[1:])
    hostport = host.split(':')
    if len(hostport) > 1:
        host =  hostport[0]
        port = hostport[1]
    else:
        port = 80
    return '%s:%s'%(host,port), path

def get_service_locations(wsdl_url):
    '''
    This method returns a map of services and portypes to their soap service locations.
    Ex.

    service_map = get_service_locations('http://myserver:8080/service.wsdl')
    service_location = service_map[service_name][port_type]
    '''
    host, path = split_url(wsdl_url)
    conn = httplib.HTTPConnection(host)
    conn.request('GET',path)
    resp = conn.getresponse()
    if resp.status != 200:
        raise Exception("Recieved code [%s] from url [%s], expected 200"%(resp.status,wsdl_url))
    data = resp.read()
    element = ElementTree.fromstring(data)

    service_map = {}
    for definitionNode in element.getchildren():
        if definitionNode.tag.find("service") != -1:
            serviceName = definitionNode.get('name')
            if not service_map.has_key(serviceName):
                service_map[serviceName] = {}

            for serviceNode in definitionNode.getchildren():
                port_name = serviceNode.get('name')
                location = serviceNode.getchildren()[0].get('location')
                service_map[serviceName][port_name] = location
    return service_map

def reconstruct_url(environ):
    '''
    Rebuilds the calling url from values found in the
    environment.

    This algorithm was found via PEP 333, the wsgi spec and
    contributed by Ian Bicking.
    '''
    url = environ['wsgi.url_scheme']+'://'
    if environ.get('HTTP_HOST'):
        url += environ['HTTP_HOST']
    else:
        url += environ['SERVER_NAME']

        if environ['wsgi.url_scheme'] == 'https':
            if environ['SERVER_PORT'] != '443':
               url += ':' + environ['SERVER_PORT']
        else:
            if environ['SERVER_PORT'] != '80':
               url += ':' + environ['SERVER_PORT']

    if quote(environ.get('SCRIPT_NAME','')) == '/' and quote(environ.get('PATH_INFO',''))[0:1] == '/':
        #skip this if it is only a slash
        pass
    elif quote(environ.get('SCRIPT_NAME',''))[0:2] == '//':
        url += quote(environ.get('SCRIPT_NAME',''))[1:]
    else:
        url += quote(environ.get('SCRIPT_NAME',''))

    url += quote(environ.get('PATH_INFO',''))
    if environ.get('QUERY_STRING'):
        url += '?' + environ['QUERY_STRING']
    return url
    

###################################################################
# Deprecated Functionality
###################################################################
from warnings import warn
def deprecate(name):
    warn("Method [%s] will be removed at the end of this iteration"%name,DeprecationWarning)    

def convertDateTime(date):
    deprecate('convertDateTime')
    date = date.replace("T"," ")
    d, t = date.split(' ')
    y,mo,da = d.split('-')
    h,mi,s = t.split(':')
    ms = 0
    try: s,ms = s.split('.')
    except: pass
    return datetime.datetime(int(y),int(mo),int(da),int(h),int(mi),int(s),int(ms))

converters = {
    'datetime':convertDateTime,
    'integer':int,
    'float':float,
    'boolean':bool,
}

def element2dict(element):
    deprecate('element2dict')
    if type(element) == str:
        element = ElementTree.fromstring(element)

    children = element.getchildren()
    tag = element.tag.split('}')[-1] 
    return {tag:_element2dict(children)}

def _get_element_value(element):
    deprecate('_get_element_value')
    xsd_type = None
    for k in element.keys():
        if k.lower().endswith('type'):
            xsd_type = element.get(k)
    if element.text == None:
        return None
    if xsd_type:
        t = xsd_type.lower().split(':')[-1]
        conv = converters.get(t)
        if conv: return conv(element.text)
        else: return element.text
    return element.text

def _element2dict(child_elements):
    deprecate('_element2dict')
    d = {}
    for child in child_elements:

        tag = child.tag.split('}')[-1] 
        children = child.getchildren()
        if children:
            typ = None
            for k in child.keys():
                if k.lower().endswith('type'):
                    typ = child.get(k)
            if typ and typ.lower().endswith('array'):
                d[tag] = []
                for c in child.getchildren():
                    if c.getchildren():
                        d[tag].append(_element2dict(c.getchildren()))
                    else:
                        d[tag].append(_get_element_value(c))
            else:
                d[tag] = _element2dict(children) 
        else:
            typ = None
            for k in child.keys():
                if k.lower().endswith('type'):
                    typ = child.get(k)
            value = _get_element_value(child)
            d[tag] = _get_element_value(child)
    return d


def dict2element(*args,**kwargs):
    deprecate('dict2element')
    if len(kwargs) == 1:
        dictionary = kwargs
    else:
        dictionary = args[0]
    if not len(dictionary.keys()):
        return ElementTree.Element('none')
    root = dictionary.keys()[0] 
    element =  _dict2element(dictionary[root],root)
    element.set('xmlns:optio','http://www.optio.com/schemas')
    return element

def _dict2element(data,tag):
    deprecate('_dict2element')
    d = {   datetime.datetime:'xs:dateTime',
            int:'xs:integer',
            bool:'xs:boolean',
            float:'xs:float',
           } 
    root = ElementTree.Element(tag)
    if type(data) == dict:
        for k,v in data.items():
            root.append(_dict2element(v,k))
    elif type(data) == list or type(data) == tuple:
        root.set('type','optio:array')
        for item in data:
            root.append(_dict2element(item,'item'))
    elif data is not None:
        t = d.get(type(data),'xs:string')
        root.text = str(data)
        root.set('type',t)
    return root
