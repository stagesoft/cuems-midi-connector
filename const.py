

import pickle
from os import path
from collections import namedtuple

def local_path(name):
    #fix for cx_freeze
    current = path.dirname(path.abspath(__file__))
    if current.endswith('\\library.zip\\bigglesworth'):
        current = current.replace('\\library.zip', '')
    elif current.endswith('/library.zip/bigglesworth'):
        current = current.replace('/library.zip', '')
    return path.join(current, name)

#with open('blofeld_params', 'rb') as _params_file:
#    sound_params = pickle.load(_params_file)


ALSA, RTMIDI = 0, 1

MIDFILE, SYXFILE = 1, 2

QWIDGETSIZE_MAX = ((1 << 24) - 1)
INPUT, OUTPUT = 0, 1
LEGATO = 0
RANDOM = 0
RANGE, VALUE, NAME, SHORTNAME, FAMILY, VARNAME = range(6)
SRC_LIBRARY, SRC_BLOFELD, SRC_EXTERNAL = range(3)
EMPTY, STORED, DUMPED, MOVED, EDITED = [0, 1, 3, 4, 8]

PGMRECEIVE, MIDIRECEIVE, PGMSEND, MIDISEND = range(4)
MOVEUP, MOVEDOWN, MOVELEFT, MOVERIGHT, MOVE = range(5)

DUMP_ALL = -1
SMEB = 0x7f, 0x00
MIEB = True

MoveCursor, UpCursor, DownCursor, LeftCursor, RightCursor = range(5)
cursor_list = []
status_dict = {
               EMPTY: 'Empty', 
               STORED: 'Stored', 
               DUMPED: 'Dumped', 
               EDITED: 'Edited', 
               MOVED: 'Moved', 
               }

INIT = 0xf0
END = 0xf7
BROADCAST = 0x7f
CHK = 0x7f
IDW = 0x3e
IDE = 0x13
SNDR = 0
SNDD = 0x10
SNDP = 0x20
GLBR = 0x4
GLBD = 0x14
WTBD = 0x12

CURSOR_NORMAL, CURSOR_INSERT = range(2)


class InvalidException(Exception):
    def __init__(self, params=None):
        self.params = params

    def __str__(self):
        return repr(self.params)


class AdvParam(object):
    def __init__(self, fmt, **kwargs):
        self.fmt = fmt
        self.indexes = {}
        self.indexes_range = {}
        self.addr = {}
        self.order = []
#        self.forbidden = 0
        self.allowed = 0
#        delta_shift = 1
        for i, l in enumerate(reversed(fmt)):
            if l == '0':
#                self.forbidden |= 1<<i
                continue
            self.allowed |= 1<<i
            if l in self.indexes:
                self.indexes[l] |= (self.indexes[l]<<1)
#                self.indexes_range[l][1] += (1<<delta_shift)
#                delta_shift += 1
            else:
#                delta_shift = 1
                self.indexes[l] = 1 << i
                self.indexes_range[l] = [i, None]
                self.addr[l] = i
                self.order.append(l)
        self.kwargs = {}
        self.kwargs_dict = {}
        self.named_kwargs = []
        for attr in self.order:
            values = kwargs[attr][1]
            setattr(self, kwargs[attr][0], values)
            self.kwargs[attr] = values
            self.kwargs_dict[attr] = kwargs[attr][0]
            self.named_kwargs.append(kwargs[attr][0])
            self.indexes_range[attr][1] = len(values) - 1
#        print self.kwargs, self.named_kwargs
        self.order.reverse()
        #TODO: reverse named_kwargs!

    def is_valid(self, value):
        invalid = []
        for key, (shift, max_value) in self.indexes_range.items():
            bl = max_value.bit_length()
            trim_value = (value >> shift) & (2**bl-1)
            if trim_value > max_value:
                invalid.append((self.kwargs_dict[key], key, trim_value, self.kwargs[key]))
        return True if not invalid else invalid

    def get_indexes(self, data):
#        if data&self.forbidden:
#            raise IndexError
        data = data & self.allowed
        res = []
        for k in self.order:
            res.append((data&self.indexes[k])>>self.addr[k])
        return res

    def normalized(self, *values):
        res = 0
        for k, v in enumerate(values):
            res += v<<self.addr[self.order[k]]
        return res

    def get(self, data):
#        if data&self.forbidden:
#            raise IndexError
        data = data & self.allowed
        res = []
        for k in self.order:
            try:
                res.append(self.kwargs[k][(data&self.indexes[k])>>self.addr[k]])
            except:
                res.append(self.kwargs[k][0])
        return res

    def __getitem__(self, data):
        try:
            return self.get(data)
        except Exception as e:
            print(e)
            print('Parameters malformed (format: {}): {} ({:08b})').format(self.fmt, data, data)

arp_step_types = [
                  'normal', 
                  'pause', 
                  'previous', 
                  'first', 
                  'last', 
                  'first+last', 
                  'chord', 
                  'random', 
                  ]

arp_step_accents = [
                    'silent', 
                    '/4', 
                    '/3', 
                    '/2', 
                    '*1', 
                    '*2', 
                    '*3', 
                    '*4', 
                    ]

arp_step_timings = [
                    'random', 
                    '-3', 
                    '-2', 
                    '-1', 
                    '+0', 
                    '+1', 
                    '+2', 
                    '+3', 
                    ]

arp_step_lengths = [
                    'legato', 
                    '-3', 
                    '-2', 
                    '-1', 
                    '+0', 
                    '+1', 
                    '+2', 
                    '+3', 
                    ]

efx_short_names = {
               'Lowpass': 'LP', 
               'Highpass': 'HP', 
               'Diffusion': 'Diff.', 
               'Damping': 'Damp', 
               }



ctrl2sysex = {
              5: 57,                                                        #glide
              12: 316, 13: 323, 14: 311,                                    #arp
              15: 160, 16: 161, 17: 163, 18: 166,                           #lfo 1
              19: 172, 20: 173, 21: 175, 22: 178,                           #lfo 2
              23: 184, 24: 185, 25: 187, 26: 190,                           #lfo 3
              27: 1, 28: 2, 29: 3, 30: 7, 31: 8, 33: 9, 34: 11,             #osc 1
              35: 17, 36: 18, 37: 19, 38: 23, 39: 24, 40: 25, 41: 27,       #osc 2
              42: 33, 43: 34, 44: 35, 45: 39, 46: 40, 47: 41, 48: 43,       #osc 3
              49: 49,                                                       #sync
              50: 51,                                                       #pitchmod
              51: 56,                                                       #glide mode
              52: 61, 53: 62,                                               #osc 1 lev/bal
              54: 71, 55: 72,                                               #ringmod lev/bal
              56: 63, 57: 64,                                               #osc 2 lev/bal
              58: 65, 59: 66,                                               #osc 3 lev/bal
              60: 67, 61: 68, 62: 69,                                       #noise lev/bal/col
              65: 53,                                                       #glide active
              #66: sostenuto?
              67: 117,                                                      #filter routing
              68: 77, 69: 78, 70: 80, 71: 81, 72: 86, 73: 87,               #filter 1
              74: 88, 75: 90, 76: 92, 77: 93, 78: 95, 
              79: 97, 80: 98, 81: 100, 82: 101, 83: 106, 84: 107,           #filter 2
              85: 108, 86: 110, 87: 112, 88: 113, 89: 115, 
              90: 121, 91: 122, 92: 124, 93: 129, 94: 145, 95: 199,         #fil env
              96: 201, 97: 202, 98: 203, 99: 204, 100: 205,             
              101: 211, 102: 213, 103: 214, 104: 215, 105: 216, 106: 217,   #amp env
              107: 223, 108: 225, 109: 226, 110: 227, 111: 228, 112: 229,   #env3 env
              113: 235, 114: 237, 115: 238, 116: 239, 117: 240, 118: 241,   #env4 env
              }

INDEX, BANK, PROG, NAME, CATEGORY, STATUS, SOUND = range(7)
sound_headers = ['Index', 'Bank', 'Id', 'Name', 'Category', 'Status']

categories = [
              'Init', 
              'Arp', 
              'Atmo', 
              'Bass', 
              'Drum', 
              'FX', 
              'Keys', 
              'Lead', 
              'Mono', 
              'Pad', 
              'Perc', 
              'Poly', 
              'Seq', 
              ]

UserRole = 0
ValuesRole = UserRole + 1
IndexRole = UserRole + 1
BankRole = IndexRole + 1
ProgRole = BankRole + 1
SoundRole = ProgRole + 1
CatRole = SoundRole + 1
EditedRole = CatRole + 1
PortRole = EditedRole + 1
ClientRole = PortRole + 1

roles_dict = {
              INDEX: IndexRole, 
              BANK: BankRole, 
              PROG: ProgRole, 
              CATEGORY: CatRole, 
              }

note_scancodes = [
                  52, 39, 53, 40, 54, 55, 42, 56, 43, 57, 44, 58,
                  59, 46, 60, 47, 61, 24, 11, 25, 12, 26, 13, 27, 
                  28, 15, 29, 16, 30, 31, 18, 32, 19, 33, 20, 34, 
                  35, 
                  ]

note_keys = [
             'Z', 'S', 'X', 'D', 'C', 'V', 'G', 'B', 'H', 'N', 'J', 'M', 
             ',', 'L', '.', 'Ò', '-', 'Q', '2', 'W', '3', 'E', '4', 'R', 
             'T', '6', 'Y', '7', 'U', 'I', '9', 'O', '0', 'P', '\'', 'È', 
             '+', 
             ]

note_keys = [(key) for key in note_keys]

init_sound_data = [0, 0, 
                   1, 64, 64, 64, 66, 96, 0, 0, 2, 127, 1, 64, 0, 0, 0, 0, 0, 64, 64, 64, 66, 
                   96, 0, 0, 0, 127, 3, 64, 0, 0, 0, 0, 0, 52, 64, 64, 66, 96, 0, 0, 0, 127, 
                   5, 64, 0, 0, 0, 0, 0, 0, 2, 64, 0, 0, 0, 0, 0, 20, 0, 0, 0, 127, 0, 127, 
                   0, 127, 0, 0, 0, 64, 0, 0, 0, 0, 1, 0, 0, 1, 127, 64, 0, 0, 0, 0, 0, 0, 
                   64, 64, 64, 1, 64, 0, 0, 64, 1, 64, 0, 0, 127, 64, 0, 0, 0, 0, 0, 0, 64, 
                   64, 64, 0, 64, 0, 0, 64, 3, 64, 0, 0, 3, 0, 0, 127, 114, 5, 64, 0, 0, 0, 
                   1, 0, 20, 64, 64, 0, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 8, 
                   0, 53, 64, 100, 0, 64, 100, 0, 100, 110, 0, 15, 64, 127, 127, 0, 50, 64, 
                   0, 0, 0, 0, 64, 0, 0, 64, 0, 0, 40, 64, 0, 0, 0, 0, 64, 0, 0, 64, 0, 0, 
                   30, 64, 0, 0, 0, 0, 64, 0, 0, 64, 1, 0, 64, 0, 0, 127, 50, 0, 0, 127, 0, 
                   0, 0, 0, 64, 0, 0, 127, 52, 127, 0, 127, 0, 0, 0, 0, 64, 0, 0, 64, 64, 64, 
                   64, 64, 64, 0, 0, 0, 64, 0, 0, 64, 64, 64, 64, 64, 64, 0, 0, 1, 0, 0, 0, 
                   64, 0, 0, 0, 64, 0, 0, 0, 64, 0, 0, 0, 64, 1, 1, 64, 0, 0, 64, 0, 0, 64, 
                   0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 
                   0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 0, 0, 64, 16, 100, 0, 0, 
                   15, 8, 5, 0, 0, 0, 1, 12, 0, 0, 15, 0, 0, 55, 4, 4, 4, 4, 4, 4, 4, 4, 4, 
                   4, 4, 4, 4, 4, 4, 4, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 
                   68, 68, 68, 68, 0, 0, 0, 73, 110, 105, 116, 32, 32, 32, 32, 32, 32, 32, 
                   32, 32, 32, 32, 32, 0, 0, 0, 0]


