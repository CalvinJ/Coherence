# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from twisted.internet import reactor, protocol
from twisted.protocols.basic import LineReceiver

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

import louie

from coherence.extern.logger import Logger
log = Logger('BuzztardStore')

class BzClient(LineReceiver):

    def connectionMade(self):
        print "connected to Buzztard"
        self.factory.clientReady(self)
 
    def lineReceived(self, line):
        print "received:", line

class BzFactory(protocol.ClientFactory):          

    protocol = BzClient
    
    def __init__(self,backend):
        self.backend = backend

    def clientConnectionFailed(self, connector, reason):
        print 'connection failed:', reason.getErrorMessage()

    def clientConnectionLost(self, connector, reason):
        print 'connection lost:', reason.getErrorMessage()

    def startFactory(self):
        self.messageQueue = []
        self.clientInstance = None

    def clientReady(self, instance):
        print "clientReady"
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self.backend)
        self.clientInstance = instance
        for msg in self.messageQueue:
            self.sendMessage(msg)

    def sendMessage(self, msg):
        if self.clientInstance is not None:
            self.clientInstance.sendLine(msg)
        else:
            self.messageQueue.append(msg)

class BuzztardItem:

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id
        if mimetype == 'directory':
            self.name = obj
            self.mimetype = mimetype
        else:
            self.name = obj.get('name')
            self.mimetype = mimetype
            
        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.name)
        self.child_count = 0
        self.children = []
        
        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'
            
        if self.mimetype == 'directory':
            self.url = urlbase + str(self.id)
        else:
            self.url = obj.get('url')
        
        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            self.item.res = Resource(self.url, obj.get('protocol'))
            self.item.res.size = None
            self.item.res = [ self.item.res ]

            
    def __del__(self):
        #print "BuzztardItem __del__", self.id, self.name
        pass

    def remove(self):
        #print "BuzztardItem remove", self.id, self.name, self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item
        
    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1

            
    def remove_child(self, child):
        log.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1
            
    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]
        
    def get_id(self):
        return self.id
    
    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None
        
    def get_path(self):
        return self.url

    def get_name(self):
        return self.name

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item
        
    def get_xml(self):
        return self.item.toString()
        
    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.url

class BuzztardStore:

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','Buzztard')

        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'
            
        self.host = kwargs.get('host','127.0.0.1')
        self.port = int(kwargs.get('port',7654))
        
        self.server = server
        self.update_id = 0
        self.store = {}

        self.buzztard = BzFactory(self)
        reactor.connectTCP( self.host, self.port, self.buzztard)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]
            
    def append( self, obj, parent):
        if isinstance(obj, basestring):
            mimetype = 'directory'
        else:
            protocol,network,content_type,info = obj['protocol'].split(':')
            mimetype = content_type
            
        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = BuzztardItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)
                    
        if mimetype == 'directory':
            return self.store[id]

        return None

    def len(self):
        return len(self.store)
        
    def get_by_id(self,id):
        id = int(id)
        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None
            
    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None
        parent = self.append('Buzztard', None)

        source_protocols = ""
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    source_protocols,
                                                                    default=True)

def test_init_complete(backend):
    
    print "Houston, we have a touchdown!"
    backend.buzztard.sendMessage('browse')

def main():
    
    louie.connect( test_init_complete, 'Coherence.UPnP.Backend.init_completed', louie.Any)

    f = BuzztardStore(None)

    #def got_upnp_result(result):
    #    print "upnp", result

    #f.upnp_init()
    #print f.store
    #r = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
    #                    RequestedCount=0,
    #                    StartingIndex=0,
    #                    ObjectID=0,
    #                    SortCriteria='*',
    #                    Filter='')
    #got_upnp_result(r)


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()