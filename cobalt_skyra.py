import serial

class LaserBox:
    '''
    ***WARNING: THIS SCRIPT CAN FIRE LASER EMISSION! SHUTTER LASERS FIRST***
    Basic device adaptor for a Cobalt Skyra laser box (populated with
    up to 4 lasers). Many more commands are available and have not been
    implemented.
    '''
    def __init__(self,
                 which_port,                # COM port for laser box
                 serial_number,             # serial number to check identity
                 name2num_and_max_power_mw, # dict -> check GUI for values
                 name='Skyra_laser_box',    # optional change name
                 verbose=True,              # False for max speed
                 very_verbose=False):       # True for debug
        self.name = name
        self.verbose = verbose
        self.very_verbose = very_verbose
        # try to open serial port:
        if self.verbose: print('%s: opening...'%name, end='')
        try:
            self.port = serial.Serial(
                port=which_port, baudrate=115200, timeout=5)
        except serial.serialutil.SerialException:
            raise IOError('%s: No connection on port %s'%(name, which_port))
        if self.verbose: print(" done.")
        # check laser box is connected using serial number:
        assert serial_number == self._get_serial_number(), (
            'serial number (%s) does not match user input (%s)'%(
                self.serial_number, serial_number))
        # check key switch status:
        assert self._get_key_switch_status(), 'key switch is off'
        # init attributes and dicts to map laser names to values:
        self.names = name2num_and_max_power_mw.keys()
        self.name2num = {}
        self.max_power_mw = {}
        self.wavelengths_nm = {}
        self.power_mw = {}
        self.on_state = {}
        self.active_state = {}        
        for name in self.names:
            self.name2num[name] = name2num_and_max_power_mw[name][0]
            self.max_power_mw[name] = name2num_and_max_power_mw[name][1]
            self.wavelengths_nm[name] = self._get_wavelength(name)
            self.get_power(name)
            self.get_on_state(name)
            self.get_active_state(name)

    def _send(self, cmd):
        assert isinstance(cmd, str)
        cmd = bytes(cmd + '\r', 'ascii')
        if self.very_verbose: print("%s: sending cmd = "%self.name, cmd)
        self.port.write(cmd)
        response = self.port.readline().decode('ascii').strip('\r\n')
        if response == 'Syntax error: illegal command':
            raise ValueError('Illegal command:', cmd)
        assert self.port.in_waiting == 0
        if self.very_verbose: print("%s: -> response = "%self.name, response)
        return response

    def _get_serial_number(self):
        if self.verbose:
            print("%s: getting serial number"%self.name)
        self.serial_number = self._send('sn?')
        if self.verbose:
            print("%s: -> serial number = %s"%(self.name, self.serial_number))
        return self.serial_number

    def _get_key_switch_status(self):
        if self.verbose:
            print("%s: getting key switch status"%self.name)
        self.key_switch_status = bool(int(self._send('@cobasks?')))
        if self.verbose:
            print("%s: -> key switch status = %s"%(
                self.name, self.key_switch_status))
        return self.key_switch_status

    def _get_wavelength(self, name):
        if self.verbose:
            print("%s(%s): getting wavelength"%(self.name, name))
        wavelength_nm = self._send(self.name2num[name] + 'glw?')
        if self.verbose:
            print("%s(%s): -> wavelength (nm) = %s"%(
                self.name, name, wavelength_nm))
        return wavelength_nm

    def get_power(self, name):
        if self.verbose:
            print("%s(%s): getting power"%(self.name, name))
        assert name in self.name2num.keys(), 'unknown laser name'
        self.power_mw[name] = round(
            1e3 * float(self._send(self.name2num[name] + 'p?')), 1)
        if self.verbose:
            print("%s(%s): -> power (mW) = %s"%(
                self.name, name, self.power_mw[name]))
        return self.power_mw[name]

    def set_power(self, name, power_mw):
        if self.verbose:
            print("%s(%s): setting power = %s"%(self.name, name, power_mw))
        assert name in self.name2num.keys(), 'unknown laser name'
        assert 0 <= power_mw <= self.max_power_mw[name], (
            'power_mw (%s) out of range'%power_mw)
        self._send(self.name2num[name] + 'p ' + str(float(1e-3 * power_mw)))
        assert self.get_power(name) == power_mw
        if self.verbose:
            print("%s(%s): -> done setting power."%(self.name, name))
        return None

    def get_on_state(self, name):
        if self.verbose:
            print("%s(%s): getting on state"%(self.name, name))
        assert name in self.name2num.keys(), 'unknown laser name'
        self.on_state[name] = bool(int(self._send(self.name2num[name] + 'l?')))
        if self.verbose:
            print("%s(%s): -> on state = %s"%(
                self.name, name, self.on_state[name]))
        return self.on_state[name]

    def set_on_state(self, name, state): # ***Turns laser ON!***
        if self.verbose:
            print("%s(%s): setting on state = %s"%(self.name, name, state))
        assert name in self.name2num.keys(), 'unknown laser name'
        self._send(self.name2num[name] + 'l' + str(int(state)))
        assert self.get_on_state(name) == state
        if self.verbose:
            print("%s(%s): -> done setting on state."%(self.name, name))
        return None

    def get_active_state(self, name):
        if self.verbose:
            print("%s(%s): getting active state"%(self.name, name))
        assert name in self.name2num.keys(), 'unknown laser name'
        self.active_state[name] = bool(
            int(self._send(self.name2num[name] + 'gla?')))
        if self.verbose:
            print("%s(%s): -> active state = %s"%(
                self.name, name, self.active_state[name]))
        return self.active_state[name]

    def set_active_state(self, name, state): # ***Turns laser active!***
        if self.verbose:
            print("%s(%s): setting active state = %s"%(self.name, name, state))
        assert name in self.name2num.keys(), 'unknown laser name'
        self._send(self.name2num[name] + 'sla ' + str(int(state)))
        assert self.get_active_state(name) == state
        if self.verbose:
            print("%s(%s): -> done setting active state."%(self.name, name))
        return None

    def close(self):
        if self.verbose: print("%s: closing..."%self.name)
        self.port.close()
        if self.verbose: print("%s: closed."%self.name)
        return None

if __name__ == '__main__':
    import time
    laser_box = LaserBox(which_port='COM4',
                         serial_number='28288',
                         name2num_and_max_power_mw={
                             '405':('4', 110),
                             '488':('3', 110),
                             '561':('1', 55),
                             '633':('2', 55),
                             },
                         verbose=True,
                         very_verbose=False)

    # test all lasers:
    for name in laser_box.names:
        # turn on:
        laser_box.set_on_state(name, True)
        laser_box.set_active_state(name, True)
        if name == '561': time.sleep(3) # 561 is slow to respond...
        # adjust power:
        for power_mw in range(4, 10, 2):
            laser_box.set_power(name, power_mw)
            time.sleep(0.5)
        # turn off:
        laser_box.set_power(name, 0)
        laser_box.set_active_state(name, False)
        laser_box.set_on_state(name, False)

    laser_box.close()
