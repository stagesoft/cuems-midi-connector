from cuemsutils.daemon import run_daemon
from cuemsutils.log import Logger
from CuemsMidiConnector import CuemsMidiConnector



def main():
    # Create and run engine
    nodeconf = CuemsMidiConnector()
    Logger.debug('CuemsMidiConnector instance created, going start to daemon')
    run_daemon(nodeconf, 'MidiConnector')

if __name__ == '__main__':
    main()