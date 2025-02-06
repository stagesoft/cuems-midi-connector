
from const import *
from pyalsa import alsaseq, alsacontrol
class NamedFlag(int):
    """
    An integer type where each value has a name attached to it.
    """
    def __new__(cls, value, name):
        return int.__new__(cls, value)
    def __init__(self, value, name):
        self.name = name
    def __getnewargs__(self):
        return (int(self), self.name)
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name
    
class NamedBitMask(NamedFlag):
    """
    Like NamedFlag, but bit operations | and ~ are also reflected in the
    resulting value's string representation.
    """
    def __or__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return type(self)(
            int(self) | int(other),
            '%s|%s' % (self.name, other.name)
        )
    def __invert__(self):
        return type(self)(
            ~int(self) & ((1 << 30) - 1),
            ('~%s' if '|' not in self.name else '~(%s)') % self.name
        )


class _EventType(NamedBitMask):
    pass

_event_types_raw = {
#                       id: (alsa, internal)
                        0: ('NONE', 'NONE'),
                        1: ('NOTEON', 'NOTEON'),
                        2: ('NOTEOFF', 'NOTEOFF'),
                        3: ('NOTE', 'NOTE'),
                        4: ('CONTROLLER', 'CTRL'),
                        8: ('PITCHBEND', 'PITCHBEND'),
                        16: ('CHANPRESS', 'AFTERTOUCH'),
                        32: ('KEYPRESS', 'POLY_AFTERTOUCH'),
                        64: ('PGMCHANGE', 'PROGRAM'),
                        128: ('SYSEX', 'SYSEX'),
                        256: ('QFRAME', 'SYSCM_QFRAME'),
                        512: ('SONGPOS', 'SYSCM_SONGPOS'),
                        1024: ('SONGSEL', 'SYSCM_SONGSEL'),
                        2048: ('TUNE_REQUEST', 'SYSCM_TUNEREQ'),
#                        3840: 'SYSCM',
                        4096: ('CLOCK', 'SYSRT_CLOCK'),
                        8192: ('START', 'SYSRT_START'),
                        16384: ('CONTINUE', 'SYSRT_CONTINUE'),
                        32768: ('STOP', 'SYSRT_STOP'),
                        65536: ('SENSING', 'SYSRT_SENSING'),
                        131072: ('RESET', 'SYSRT_RESET'),
#                        258048: 'SYSRT',
                        262016: ('SYSTEM', 'SYSTEM'),
#                        536870912: 'DUMMY',
                        1073741823: ('USR1', 'ANY'), 
                        }

_event_type_names = {}
_event_type_values = {}
_event_type_alsa = {}
_event_type_toalsa = {}
EventTypes = []
for v, (alsa_str, name) in _event_types_raw.items():
    _type_obj = _EventType(v, name)
    globals()[name] = _type_obj
    _event_type_names[name] = _type_obj
    _event_type_values[v] = _type_obj

    _alsa_event = getattr(alsaseq, 'SEQ_EVENT_{}'.format(alsa_str))
    _event_type_alsa[int(_alsa_event)] = _type_obj
    _event_type_toalsa[_type_obj] = _alsa_event
    EventTypes.append(_type_obj)

_bits_to_event = {
                  0x8: NOTEOFF, 
                  0x9: NOTEON, 
                  0xa: POLY_AFTERTOUCH, 
                  0xb: CTRL, 
                  0xc: PROGRAM, 
                  0xd: AFTERTOUCH, 
                  0xe: PITCHBEND, 
                  0xf: SYSEX, 
                  }

_event_to_bits = {v:k<<4 for k, v in _bits_to_event.items()}

def _value_to_bytes(value):
    return (value & 63),  (value >> 7)

def _bytes_to_value(unit, multi):
    return (multi << 7)+unit

def _get_jack_event_type(value):
    found = False
    for bit, event_type in _bits_to_event.items():
        if value >> 4 == bit:
            found = True
            break
    if not found:
        raise Exception('WTF?! value: {}'.format(value))
    return event_type, value & 0xf


_note_names = {0: 'c', 1: 'c#', 2: 'd', 3: 'd#', 4: 'e', 5: 'f', 6: 'f#', 7: 'g', 8: 'g#', 9: 'a', 10: 'a#', 11: 'b',}
def get_note_name(id):
    return _note_names[id%12]
NoteNames = {id:'{}{}'.format(_note_names[id%12], id//12) for id in range(128)}

_sharps = {'c': 'd', 'd': 'e', 'f': 'g', 'g': 'a', 'a': 'b'}
_en = {'c': ('b#', -1), 'e': ('fb', 0), 'f': ('e#', 0), 'b': ('cb', 1)}
NoteIds = {'c0': 0}
for i, n in NoteNames.items():                        
    NoteIds[n] = i
    if n[1] == '#':
        NoteIds['{}b{}'.format(_sharps[n[0]],n[2:])] = i
    elif n[0] in _en:
        en = _en[n[0]]
        NoteIds['{}{}'.format(en[0],str(int(n[1:])+en[1]))] = i


WhiteKeys = []
BlackKeys = []
for n in range(128):
    if n%12 in [1, 3, 6, 8, 10]:
        BlackKeys.append(n)
    else:
        WhiteKeys.append(n)

def _make_property(type, data, name=None):
    def getter(self):
        self._check_type_attribute(type, name)
        return getattr(self, data)
    def setter(self, value):
        self._check_type_attribute(type, name)
        setattr(self, data, value)
    return property(getter, setter)


class MidiEvent(object):
    def __init__(self, event_type=None, port=0, channel=0, data1=0, data2=0, sysex=None, event=None, source=None, dest=None, backend=None):
        self.backend = backend
        if event:
            self._event = event
            self.source = tuple(map(int, event.source))
            self.dest = tuple(map(int, event.dest))
            self.port = self.dest[1]
            self.queue = event.queue
            self._type = _event_type_alsa[int(event.type)]
            data = event.get_data()
            if self._type in [NOTEON, NOTEOFF, POLY_AFTERTOUCH]:
                self.channel = data['note.channel']
                self.data1 = data['note.note']
                self.data2 = data['note.velocity']
                self._sysex = None
            elif self._type == CTRL:
                self.channel = data['control.channel']
                self.data1 = data['control.param']
                self.data2 = data['control.value']
                self._sysex = None
            elif self._type in [PROGRAM, AFTERTOUCH, PITCHBEND]:
                self.channel = data['control.channel']
                self.data1 = 0
                self.data2 = data['control.value']
                self._sysex = None
            elif self._type == SYSEX:
                self.channel = 0
                self.data1 = self.data2 = 0
                self._sysex = data['ext']
            elif self._type == SYSTEM:
                self.channel = 0
                self.data1 = data['result.event']
                self.data2 = data['result.result']
                self._sysex = None
            elif self._type in [SYSRT_START, SYSRT_CONTINUE, SYSRT_STOP]:
                self.channel = 0
                self.data1 = self.data2 = 0
                self.queue = data['queue.queue']
                self._sysex = None
            else:
                self.channel = 0
                self.data1 = self.data2 = 0
                self._sysex = None
        else:
            if not event_type in _event_type_values.values():
                raise ValueError('There\'s no such event type as {}'.format(event_type))
            self._type = event_type
            self.source = source
            self.dest = dest
            #TODO: check for jack destination
            self.port = port if dest is None else dest
            self.channel = channel
            self.data1 = data1
            self.data2 = data2
            self._sysex = sysex
            self.queue = 0
            self._event = None

