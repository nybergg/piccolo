import logging

import serial

logger = logging.getLogger(__name__)

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
        logger.debug('%s: opening...', name)
        try:
            self.port = serial.Serial(
                port=which_port, baudrate=115200, timeout=5)
        except serial.SerialException:
            raise IOError('%s: No connection on port %s' % (name, which_port))
        logger.debug('%s: opened.', name)
        # check laser box is connected using serial number:
        actual_sn = self._get_serial_number()
        if serial_number != actual_sn:
            raise ValueError(
                '%s: serial number (%s) does not match expected (%s)' % (
                    name, actual_sn, serial_number))
        # check key switch status:
        if not self._get_key_switch_status():
            raise RuntimeError('%s: key switch is off' % name)
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

    def _check_laser_name(self, name):
        if name not in self.name2num:
            raise ValueError('%s: unknown laser name: %s' % (self.name, name))

    def _send(self, cmd):
        if not isinstance(cmd, str):
            raise TypeError('%s: command must be a string, got %s' % (self.name, type(cmd)))
        cmd = bytes(cmd + '\r', 'ascii')
        logger.debug("%s: sending cmd = %s", self.name, cmd)
        self.port.write(cmd)
        response = self.port.readline().decode('ascii').strip('\r\n')
        if response == 'Syntax error: illegal command':
            raise ValueError('Illegal command:', cmd)
        if self.port.in_waiting != 0:
            raise IOError('%s: unexpected data in serial buffer after command' % self.name)
        logger.debug("%s: response = %s", self.name, response)
        return response

    def _get_serial_number(self):
        logger.debug("%s: getting serial number", self.name)
        self.serial_number = self._send('sn?')
        logger.debug("%s: serial number = %s", self.name, self.serial_number)
        return self.serial_number

    def _get_key_switch_status(self):
        logger.debug("%s: getting key switch status", self.name)
        self.key_switch_status = bool(int(self._send('@cobasks?')))
        logger.debug("%s: key switch status = %s", self.name, self.key_switch_status)
        return self.key_switch_status

    def _get_wavelength(self, name):
        logger.debug("%s(%s): getting wavelength", self.name, name)
        wavelength_nm = self._send(self.name2num[name] + 'glw?')
        logger.debug("%s(%s): wavelength (nm) = %s", self.name, name, wavelength_nm)
        return wavelength_nm

    def get_power(self, name):
        logger.debug("%s(%s): getting power", self.name, name)
        self._check_laser_name(name)
        self.power_mw[name] = round(
            1e3 * float(self._send(self.name2num[name] + 'p?')), 1)
        logger.debug("%s(%s): power (mW) = %s", self.name, name, self.power_mw[name])
        return self.power_mw[name]

    def set_power(self, name, power_mw):
        logger.debug("%s(%s): setting power = %s", self.name, name, power_mw)
        self._check_laser_name(name)
        if not (0 <= power_mw <= self.max_power_mw[name]):
            raise ValueError(
                '%s(%s): power_mw (%s) out of range [0, %s]' % (
                    self.name, name, power_mw, self.max_power_mw[name]))
        self._send(self.name2num[name] + 'p ' + str(float(1e-3 * power_mw)))
        actual = self.get_power(name)
        if actual != power_mw:
            raise RuntimeError(
                '%s(%s): set_power failed, expected %s but got %s' % (
                    self.name, name, power_mw, actual))
        logger.debug("%s(%s): done setting power.", self.name, name)

    def get_on_state(self, name):
        logger.debug("%s(%s): getting on state", self.name, name)
        self._check_laser_name(name)
        self.on_state[name] = bool(int(self._send(self.name2num[name] + 'l?')))
        logger.debug("%s(%s): on state = %s", self.name, name, self.on_state[name])
        return self.on_state[name]

    def set_on_state(self, name, state): # ***Turns laser ON!***
        logger.debug("%s(%s): setting on state = %s", self.name, name, state)
        self._check_laser_name(name)
        self._send(self.name2num[name] + 'l' + str(int(state)))
        actual = self.get_on_state(name)
        if actual != state:
            raise RuntimeError(
                '%s(%s): set_on_state failed, expected %s but got %s' % (
                    self.name, name, state, actual))
        logger.debug("%s(%s): done setting on state.", self.name, name)

    def get_active_state(self, name):
        logger.debug("%s(%s): getting active state", self.name, name)
        self._check_laser_name(name)
        self.active_state[name] = bool(
            int(self._send(self.name2num[name] + 'gla?')))
        logger.debug("%s(%s): active state = %s", self.name, name, self.active_state[name])
        return self.active_state[name]

    def set_active_state(self, name, state): # ***Turns laser active!***
        logger.debug("%s(%s): setting active state = %s", self.name, name, state)
        self._check_laser_name(name)
        self._send(self.name2num[name] + 'sla ' + str(int(state)))
        actual = self.get_active_state(name)
        if actual != state:
            raise RuntimeError(
                '%s(%s): set_active_state failed, expected %s but got %s' % (
                    self.name, name, state, actual))
        logger.debug("%s(%s): done setting active state.", self.name, name)

    def shutdown(self):
        logger.info("%s: shutting down...", self.name)
        for name in self.names:
            self.set_power(name, 0)
            self.set_active_state(name, False)
            self.set_on_state(name, False)
        logger.info("%s: shut down.", self.name)

    def close(self):
        logger.debug("%s: closing...", self.name)
        self.port.close()
        logger.debug("%s: closed.", self.name)

if __name__ == '__main__':
    import time
    logging.basicConfig(level=logging.DEBUG)
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
