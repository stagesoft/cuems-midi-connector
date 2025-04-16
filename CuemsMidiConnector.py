
# we need to use system pyalsa package to virtualenv
# ln -s /usr/lib/python3/dist-packages/pyalsa $HOME/.pyenv/versions/3.11.2/envs/cuems/lib/python3.11/site-packages/
from const import ALSA
from midiutils import *
import time
from cuemsutils.log import logged, Logger





class CuemsMidiConnector:
    def __init__(self):
            self.seq = alsaseq.Sequencer(clientname='PyASeqKeeper')
            self.master = self.iam_master()
            self.keep_going = True
            input_id = self.seq.create_simple_port(
            name='input', 
            type=alsaseq.SEQ_PORT_TYPE_MIDI_GENERIC|alsaseq.SEQ_PORT_TYPE_APPLICATION, 
            caps=alsaseq.SEQ_PORT_CAP_WRITE|alsaseq.SEQ_PORT_CAP_SUBS_WRITE|
            alsaseq.SEQ_PORT_CAP_SYNC_WRITE)
            output_id = self.seq.create_simple_port(name='output', 
                                                type=alsaseq.SEQ_PORT_TYPE_MIDI_GENERIC|alsaseq.SEQ_PORT_TYPE_APPLICATION, 
                                                caps=alsaseq.SEQ_PORT_CAP_READ|alsaseq.SEQ_PORT_CAP_SUBS_READ|
                                                alsaseq.SEQ_PORT_CAP_SYNC_READ)
            
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


        if "xjadeo" in client_name:
            Logger.debug(f"Processing xjadeo connections for : {client_name}")
            # do xjadeo specific stuff
            PlayerConecction.connect_from_through_port(self.seq, client_id)

        if "MtcMaster" in client_name:
            Logger.debug(f"Processing MtcMaster connections for : {client_name}")
            # do MtcMaster specific stuff
            MtcMasterConnection.connect_to_through_port(self.seq, client_id)

        if "rtpmidid" in client_name:
            print(f"Processing rtpmidid connections for : {client_name}")
                Logger.debug(f"Processing Master rtpmidid connections for : {client_name}")
            if self.master:
                RtpMidiConnection_Master.connect_from_through_port(self.seq, client_id)
            else:
                Logger.debug(f"Processing node rtpmidid connections for : {client_name}")
        


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
        print('exit')
        del self.seq
        self.stopped.emit()


    def iam_master(self):
        return True



class PlayerConecction():
    
    @staticmethod
    def connect_from_through_port(seq, client_id):
        through_port_id = 14
        through_port_port_id = 0
        through_port = (through_port_id, through_port_port_id)

        port_info = seq.get_port_info(0, client_id)

        client_port = (client_id, 0)
        Logger.debug(f"connecting from through port: {port_info}")
        try:
            seq.connect_ports(through_port, client_port)
        except Exception as e:
            Logger.warning(f"Error connecting from through port: {e}")
            return False
        


class MtcMasterConnection():

    @staticmethod
    def connect_to_through_port(seq, client_id):
        through_port_id = 14
        through_port_port_id = 0
        through_port = (through_port_id, through_port_port_id)

        port_info = seq.get_port_info(0, client_id)

        client_port = (client_id, 0)
        Logger.debug(f"connecting to through port: {port_info}")
        try:
            seq.connect_ports(client_port, through_port)
        except Exception as e:
            print(f"Error connecting to through port: {e}")
            Logger.warning(f"Client with id {client_id} not found")
            return False
            Logger.warning(f"Port with name {NETWORK_PORT_NAME} not found")
        Logger.debug(f"connecting network to through port: '{first_port_match[0]}'")
            Logger.warning(f"Error connecting to through port: {e}")
        
class RtpMidiConnection_Master():

    @staticmethod
    def connect_from_through_port(seq, client_id):
        through_port_id = 14
        through_port_port_id = 0
        through_port = (through_port_id, through_port_port_id)

        port_info = seq.get_port_info(0, client_id)

        client_port = (client_id, 0)
        print(f"connecting to through port: {port_info}")
        try:
            seq.connect_ports(through_port, client_port)
        except Exception as e:
            print(f"Error connecting to through port: {e}")
            return False


class RtpMidiConnection_Slave():
    pass

class VideoConecction(PlayerConecction):
    pass

if __name__ == '__main__':

    keeper = CuemsMidiConnector()
    keeper.run()