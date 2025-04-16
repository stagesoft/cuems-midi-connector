
# we need to use system pyalsa package to virtualenv
# ln -s /usr/lib/python3/dist-packages/pyalsa $HOME/.pyenv/versions/3.11.2/envs/cuems/lib/python3.11/site-packages/
from const import ALSA
from midiutils import *
import time
from cuemsutils.log import logged, Logger


CUEMS_CONTROLLER_LOCK_FILE = 'master.lock'
CUEMS_CONF_PATH = '/etc/cuems/'

NETWORK_PORT_NAME = 'Midi Through-Midi Through Port-0'


class CuemsMidiConnector:
    def __init__(self):
            self.seq = alsaseq.Sequencer(clientname='CuemsMidiConnector')
            self.controller = False
            #self.controller= self.check_amicontroller()
            self.keep_going = True
            self.connector = GenericConnection()
            input_id = self.seq.create_simple_port(
                name='input', 
                type=alsaseq.SEQ_PORT_TYPE_MIDI_GENERIC|alsaseq.SEQ_PORT_TYPE_APPLICATION, 
                caps=alsaseq.SEQ_PORT_CAP_WRITE|alsaseq.SEQ_PORT_CAP_SUBS_WRITE|
                alsaseq.SEQ_PORT_CAP_SYNC_WRITE)

            self.seq.connect_ports((alsaseq.SEQ_CLIENT_SYSTEM, alsaseq.SEQ_PORT_SYSTEM_ANNOUNCE), (self.seq.client_id, input_id))
            self.id = self.seq.client_id

    def new_client(self, data):
        Logger.debug(f"new client: {data}")
        client_id = data.get('addr.client')
    #    time.sleep(2)  # wait for connection to establish before processing
        self.process_connections(client_id)


    def port_unsusubscribed(self, data):
        client_id = data.get('connect.sender.client')
        self.process_connections(client_id)
        client_id = data.get('connect.dest.client')
        self.process_connections(client_id)

    def list_clients(self):
        Logger.debug('List of clients on startup:')
        conection_list = self.seq.connection_list()
        for client in conection_list:
            client_name, client_id, ports = client
            print(f"client: {client_name}, id : {client_id}")
            self.process_connections(client_id)
            
            # for port in ports:
            #     port_name, port_id, connections = port
            #     print(f"port name: {port_name}, port id: {port_id}")
            #     read, write = connections
            #     print(f"connections:  read: {read}, write: {write}")
        print("----startup processing complete.---")
    
    def process_connections(self,client_id):

        client_info =self.seq.get_client_info(client_id)
        client_name = client_info.get('name')
        Logger.debug(f"processing conections for : {client_name}")


        if ("xjadeo" or "audioplayer" or "dmxplayer") in client_name:
            Logger.debug(f"Processing xjadeo connections for : {client_name}")
            # do xjadeo specific stuff
            self.connector.connect_from_through_port(self.seq, client_id)

        if "MtcMaster" in client_name:
            Logger.debug(f"Processing MtcMaster connections for : {client_name}")
            # do MtcMaster specific stuff
            self.connector.connect_to_through_port(self.seq, client_id)

        if "rtpmidid" in client_name:
            if self.controller:
                Logger.debug(f"Processing Master rtpmidid connections for : {client_name}")
                # do rtpmidid specific stuff
                self.connector.connect_from_through_port(self.seq, client_id)
            else:
                Logger.debug(f"Processing node rtpmidid connections for : {client_name}")
                # do rtpmidid specific stuff
                self.connector.connect_network_to_through_port(self.seq, client_id)

            


    def run(self):
        self.active = True
        self.list_clients()
        while self.keep_going:
            try:
                event_list = self.seq.receive_events(timeout=1024, maxevents=1)
                for event in event_list:
                    data = event.get_data()
                    if event.type == alsaseq.SEQ_EVENT_CLIENT_START:
                        #self.graph.client_created(data)
                        Logger.debug(f'client started{data}')
                        self.new_client(data)
                    elif event.type == alsaseq.SEQ_EVENT_CLIENT_EXIT:
                        #self.graph.client_destroyed(data)
                        Logger.debug(f'client exited{data}')
                    elif event.type == alsaseq.SEQ_EVENT_PORT_START:
                        #self.graph.port_created(data)
                        Logger.debug(f'port started{data}')
                        self.new_client(data)
                    elif event.type == alsaseq.SEQ_EVENT_PORT_EXIT:
                        #self.graph.port_destroyed(data)
                        Logger.debug(f'port exited{data}')
                    elif event.type == alsaseq.SEQ_EVENT_PORT_SUBSCRIBED:
                        #self.graph.conn_created(data)
                        Logger.debug(f'port subscribed{data}')
                    elif event.type == alsaseq.SEQ_EVENT_PORT_UNSUBSCRIBED:
                        #self.graph.conn_destroyed(data)
                        Logger.debug(f'port unsubscribed{data}')
                        self.port_unsusubscribed(data)
                    elif event.type in [alsaseq.SEQ_EVENT_NOTEON, alsaseq.SEQ_EVENT_NOTEOFF, 
                                        alsaseq.SEQ_EVENT_CONTROLLER, alsaseq.SEQ_EVENT_PGMCHANGE,
                                        ]:
                        try:
                            newev = MidiEvent.from_alsa(event)
                            self.midi_event.emit(newev)
                            Logger.debug(newev)
                        except Exception as e:
                            Logger.error('event {} unrecognized').format(event)
                            Logger.error(e)
                    elif event.type in [alsaseq.SEQ_EVENT_CLOCK, alsaseq.SEQ_EVENT_SENSING]:
                        pass
                    elif event.type == alsaseq.SEQ_EVENT_SYSEX:
                        self.check(event)
            except Exception as e:
                Logger.error(e)
                Logger.error('something is wrong')
        Logger.debug('exit')
        del self.seq
        self.stopped.emit()


    def check_amicontroller(self):
        if path.exists(path.join(CUEMS_CONF_PATH, CUEMS_CONTROLLER_LOCK_FILE)):
            return True
        else:
            return False


class GenericConnection():
    def __init__(self):
        self.through_port_id = 14
        self.through_port_port_id = 0
        self.through_port = (self.through_port_id, self.through_port_port_id)


    def connect_from_through_port(self,seq, client_id):

        port_info = seq.get_port_info(0, client_id)

        client_port = (client_id, 0)
        Logger.debug(f"connecting from through port: {port_info}")
        try:
            seq.connect_ports(self.through_port, client_port)
        except Exception as e:
            Logger.warning(f"Error connecting from through port: {e}")
            return False


    def connect_to_through_port(self, seq, client_id):

        port_info = seq.get_port_info(0, client_id)

        client_port = (client_id, 0)
        Logger.debug(f"connecting to through port: {port_info}")
        try:
            seq.connect_ports(client_port, self.through_port)
        except Exception as e:
            Logger.warning(f"Error connecting to through port: {e}")

    def connect_network_to_through_port(self, seq, client_id):
        clients = seq.connection_list()
        first_client_match = next((client for client in clients if client[1] ==  client_id), None)
        if first_client_match is None:
            Logger.warning(f"Client with id {client_id} not found")
            return False
        client_name, client_id, ports = first_client_match
        first_port_match = next((port for port in ports if port[0] ==  NETWORK_PORT_NAME), None)
        if first_port_match is None:
            Logger.warning(f"Port with name {NETWORK_PORT_NAME} not found")
            return False
        port_name, port_id, conections_list = first_port_match
        client_port = (client_id, port_id)
        Logger.debug(f"connecting network to through port: '{first_port_match[0]}'")
        try:
            seq.connect_ports(client_port, self.through_port)
        except Exception as e:
            Logger.warning(f"Error connecting to through port: {e}")

        

class NodeConnection(GenericConnection):
    pass    

class PlayerConecction(GenericConnection):
    
    pass

class MtcMasterConnection(GenericConnection):

    pass
        
class RtpMidiConnection_Master(GenericConnection):

    pass

class RtpMidiConnection_Slave(GenericConnection):
    pass

class VideoConecction(PlayerConecction):
    pass

if __name__ == '__main__':

    keeper = CuemsMidiConnector()
    keeper.run()