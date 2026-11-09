# SPDX-License-Identifier: MIT
from ..utils import *
import time

class R_MBOX_CTRL(Register32):
    FIFOCNT = 23, 20
    OVERFLOW = 18
    EMPTY = 17
    FULL  = 16
    RPTR = 15, 12
    WPTR = 11, 8
    ENABLE = 0

class R_CPU_CONTROL(Register32):
    RUN    = 4

class R_CPU_STATUS(Register32):
    IDLE            = 5
    FIQ_NOT_PEND    = 3 # guess
    IRQ_NOT_PEND    = 2 # guess
    STOPPED         = 1
    RUNNING         = 0

class R_INBOX1(Register64):
    EP      = 7, 0

class R_OUTBOX1(Register64):
    OUTCNT  = 56, 52
    INCNT   = 51, 48
    OUTPTR  = 47, 44
    INPTR   = 43, 40
    EP      = 7, 0

class ASCCPURegs(RegMap):
    CPU_CONTROL = 0x0044, R_CPU_CONTROL
    CPU_STATUS  = 0x0048, R_CPU_STATUS

class ASCRegs(ASCCPURegs):
    INBOX_CTRL  = 0x8110, R_MBOX_CTRL
    OUTBOX_CTRL = 0x8114, R_MBOX_CTRL
    INBOX0      = 0x8800, Register64
    INBOX1      = 0x8808, R_INBOX1
    OUTBOX0     = 0x8830, Register64
    OUTBOX1     = 0x8838, R_OUTBOX1

class R_MSGBOX_STATUS(Register32):
    RX = 3, 0
    TX = 11, 8

class ASCMessageboxRegs(RegMap):
    RECV   = irange(0x00, 4, 4), Register32
    SEND   = irange(0x10, 4, 4), Register32
    STATUS = 0x20, R_MSGBOX_STATUS

class ASC:
    def __init__(self, u, asc_base, *, messagebox_base=None):
        self.u = u
        self.p = u.proxy
        self.iface = u.iface
        if messagebox_base is None:
            self.asc = ASCRegs(u, asc_base)
            self.msgbox = None
        else:
            self.asc = ASCCPURegs(u, asc_base)
            self.msgbox = ASCMessageboxRegs(u, messagebox_base)
        self.verbose = 0
        self.epmap = {}

    @classmethod
    def from_adt(cls, u, path, **kwargs):
        node = u.adt[path]
        asc_base = node.get_reg(0)[0]
        if "iop,ascwrap-v8" not in node.compatible:
            return cls(u, asc_base, **kwargs)

        def flag(name):
            value = node._properties.get(name)
            return (isinstance(value, int) and value != 0) or value in ("true", b"true\0")

        mailbox = node._properties.get("msgbox-mailbox-num", 0)
        if not isinstance(mailbox, int) or not 0 <= mailbox <= 0xffffffff:
            raise ValueError("Invalid ASC mailbox number")
        aperture = 2 * mailbox + (not flag("msgbox-using-postoffice"))
        offset = aperture * 0x80 + (0 if flag("msgbox-using-alias") else 0x10000)
        base, size = node.get_reg(2)
        if offset + 0x80 > size:
            raise ValueError("ASC mailbox aperture exceeds its register range")
        return cls(u, asc_base, messagebox_base=base + offset, **kwargs)

    def recv(self):
        if not self.has_messages():
            return None, None

        if self.msgbox is None:
            msg0 = self.asc.OUTBOX0.val
            msg1 = R_INBOX1(self.asc.OUTBOX1.val)
        else:
            msg0 = self.msgbox.RECV[0].val | (self.msgbox.RECV[1].val << 32)
            msg1 = R_INBOX1(self.msgbox.RECV[2].val)
            # Reading the fourth word pops the receive FIFO.
            _ = self.msgbox.RECV[3].val
        if self.verbose >= 3:
            print(f"< {msg1.EP:02x}:{msg0:#x}")
        return msg0, msg1

    def send(self, msg0, msg1):
        if self.msgbox is None:
            self.asc.INBOX0.val = msg0
            self.asc.INBOX1.val = msg1
        else:
            deadline = time.monotonic() + 0.2
            while not self.msgbox.STATUS.reg.TX:
                if time.monotonic() >= deadline:
                    raise TimeoutError("ASC messagebox full for 200ms")
            value = int(msg0)
            self.msgbox.SEND[0].val = value & 0xffffffff
            self.msgbox.SEND[1].val = (value >> 32) & 0xffffffff
            self.msgbox.SEND[2].val = int(msg1) & 0xffffffff
            self.msgbox.SEND[3].val = 0

        if self.verbose >= 3:
            if isinstance(msg0, Register):
                print(f"> {msg1.EP:02x}:{msg0}")
            else:
                print(f"> {msg1.EP:02x}:{msg0:#x}")

        if self.msgbox is None:
            while self.asc.INBOX_CTRL.reg.FULL:
                pass

    def is_running(self):
        if self.msgbox is not None:
            return bool(self.asc.CPU_CONTROL.reg.RUN)
        return not self.asc.CPU_STATUS.reg.STOPPED

    def boot(self):
        self.asc.CPU_CONTROL.set(RUN=1)

    def shutdown(self):
        self.asc.CPU_CONTROL.set(RUN=0)

    def add_ep(self, idx, ep):
        self.epmap[idx] = ep
        setattr(self, ep.SHORT, ep)

    def has_messages(self):
        if self.msgbox is not None:
            return bool(self.msgbox.STATUS.reg.RX)
        return not self.asc.OUTBOX_CTRL.reg.EMPTY

    def work_pending(self):
        while self.has_messages():
            self.work()

    def work(self):
        if not self.has_messages():
            return True

        msg0, msg1 = self.recv()

        handled = False

        ep = self.epmap.get(msg1.EP, None)
        if ep:
            handled = ep.handle_msg(msg0, msg1)

        if not handled:
            print(f"unknown message: {msg0:#16x} / {msg1}")

        return handled

    def work_forever(self):
        while self.work():
            pass

    def work_for(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.work()
