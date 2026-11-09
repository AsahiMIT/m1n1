# SPDX-License-Identifier: MIT
from collections import deque
from types import SimpleNamespace

import pytest

from proxyclient.m1n1.fw.asc import StandardASC
from proxyclient.m1n1.hw import asc as asc_module
from proxyclient.m1n1.hw.asc import ASC, R_INBOX1
from proxyclient.m1n1.utils import Register64


class Backend:
    def __init__(self):
        self.proxy = object()
        self.iface = object()
        self.values = {}
        self.events = []
        self.adt = {}

    def read(self, address, width):
        self.events.append(("read", address, width))
        value = self.values[address]
        if isinstance(value, deque):
            return value.popleft()
        return value

    def write(self, address, value, width):
        assert 0 <= value < 1 << width
        self.events.append(("write", address, width, value))
        self.values[address] = value


class Node:
    def __init__(self, props=None, compatible="iop,ascwrap-v8", size=0x20000):
        self._properties = {} if props is None else props
        self.compatible = [compatible]
        self.regs = [(0x100000, 0x74000), (0x200000, 8), (0x300000, size)]

    def get_reg(self, index):
        return self.regs[index]


@pytest.fixture
def backend():
    return Backend()


@pytest.mark.parametrize("messagebox_base", [None, 0x300100])
def test_cpu_control_uses_cpu_registers(backend, messagebox_base):
    asc = ASC(backend, 0x100000, messagebox_base=messagebox_base)
    assert not backend.events
    backend.values[0x100044] = 0x42
    asc.boot()
    asc.shutdown()
    assert backend.events == [
        ("read", 0x100044, 32), ("write", 0x100044, 32, 0x52),
        ("read", 0x100044, 32), ("write", 0x100044, 32, 0x42),
    ]


@pytest.mark.parametrize("messagebox_base,address,value,expected", [
    (None, 0x100048, 2, False), (None, 0x100048, 0, True),
    (0x300100, 0x100044, 0x10, True), (0x300100, 0x100044, 0, False),
])
def test_running_uses_wrapper_register(backend, messagebox_base, address, value, expected):
    asc = ASC(backend, 0x100000, messagebox_base=messagebox_base)
    backend.values[address] = value
    assert asc.is_running() is expected
    assert backend.events == [("read", address, 32)]


def test_legacy_receive(backend):
    asc = ASC(backend, 0x100000)
    backend.values.update({0x108114: 0, 0x108830: 0x123456789abcdef0, 0x108838: 0xabc00007})
    msg0, msg1 = asc.recv()
    assert (msg0, int(msg1), msg1.EP) == (0x123456789abcdef0, 0xabc00007, 7)
    assert backend.events == [
        ("read", 0x108114, 32), ("read", 0x108830, 64), ("read", 0x108838, 64),
    ]


def test_legacy_send(backend):
    asc = ASC(backend, 0x100000)
    backend.values[0x108110] = deque([1 << 16, 0])
    asc.send(Register64(0x123456789abcdef0), R_INBOX1(EP=7))
    assert backend.events == [
        ("write", 0x108800, 64, 0x123456789abcdef0),
        ("write", 0x108808, 64, 7),
        ("read", 0x108110, 32), ("read", 0x108110, 32),
    ]


@pytest.mark.parametrize("messagebox_base,status_address,status", [
    (None, 0x108114, 1 << 17), (0x300100, 0x300120, 0x100),
])
def test_empty_receive_does_not_pop(backend, messagebox_base, status_address, status):
    asc = ASC(backend, 0x100000, messagebox_base=messagebox_base)
    backend.values[status_address] = status
    assert asc.recv() == (None, None)
    assert backend.events == [("read", status_address, 32)]


def test_messagebox_receive_pops_after_payload(backend):
    asc = ASC(backend, 0x100000, messagebox_base=0x300100)
    backend.values.update({0x300120: 0x101, 0x300100: 0x9abcdef0,
                           0x300104: 0x12345678, 0x300108: 0xabc00007, 0x30010c: 0})
    msg0, msg1 = asc.recv()
    assert (msg0, int(msg1), msg1.EP) == (0x123456789abcdef0, 0xabc00007, 7)
    assert backend.events == [
        ("read", 0x300120, 32), ("read", 0x300100, 32),
        ("read", 0x300104, 32), ("read", 0x300108, 32), ("read", 0x30010c, 32),
    ]


def test_messagebox_send_waits_for_space_then_commits(backend):
    asc = ASC(backend, 0x100000, messagebox_base=0x300100)
    backend.values[0x300120] = deque([1, 0x100])
    asc.send(Register64(0x123456789abcdef0), R_INBOX1(EP=7))
    assert backend.events == [
        ("read", 0x300120, 32), ("read", 0x300120, 32),
        ("write", 0x300110, 32, 0x9abcdef0), ("write", 0x300114, 32, 0x12345678),
        ("write", 0x300118, 32, 7), ("write", 0x30011c, 32, 0),
    ]


def test_messagebox_full_times_out_without_writes(backend, monkeypatch):
    asc = ASC(backend, 0x100000, messagebox_base=0x300100)
    backend.values[0x300120] = 0
    ticks = iter([5.0, 5.1, 5.2])
    monkeypatch.setattr(asc_module, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    with pytest.raises(TimeoutError, match="full for 200ms"):
        asc.send(0x123456789abcdef0, 7)
    assert backend.events == [("read", 0x300120, 32), ("read", 0x300120, 32)]


def test_messagebox_work_dispatches_endpoint(backend):
    asc = ASC(backend, 0x100000, messagebox_base=0x300100)
    backend.values.update({0x300120: 1, 0x300100: 0x1234,
                           0x300104: 0, 0x300108: 7, 0x30010c: 0})
    messages = []

    def handle(msg0, msg1):
        messages.append((msg0, int(msg1)))
        return True

    asc.epmap[7] = SimpleNamespace(handle_msg=handle)
    assert asc.work()
    assert messages == [(0x1234, 7)]
    assert sum(address == 0x30010c for _, address, _ in backend.events) == 1


@pytest.mark.parametrize("mailbox,alias,postoffice,offset", [
    (1, 1, "true", 0x100), (2, 1, b"true\0", 0x200),
    (1, 2, 0, 0x180), (2, 0, 1, 0x10200), (2, 0, 0, 0x10280),
])
def test_from_adt_selects_aperture(backend, mailbox, alias, postoffice, offset):
    backend.adt["/arm-io/test"] = Node({"msgbox-mailbox-num": mailbox,
        "msgbox-using-alias": alias, "msgbox-using-postoffice": postoffice})
    asc = ASC.from_adt(backend, "/arm-io/test")
    assert asc.asc.CPU_CONTROL.addr == 0x100044
    assert asc.msgbox.STATUS.addr == 0x300020 + offset
    assert not backend.events


def test_from_adt_missing_flags_match_legacy_defaults(backend):
    backend.adt["/arm-io/test"] = Node()
    asc = ASC.from_adt(backend, "/arm-io/test")
    assert asc.msgbox.STATUS.addr == 0x3100a0
    assert not backend.events


@pytest.mark.parametrize("mailbox", [-1, 1 << 32, "1", b"\x01\0"])
def test_from_adt_rejects_bad_mailbox(backend, mailbox):
    backend.adt["/arm-io/test"] = Node({"msgbox-mailbox-num": mailbox})
    with pytest.raises(ValueError, match="mailbox number"):
        ASC.from_adt(backend, "/arm-io/test")
    assert not backend.events


def test_from_adt_checks_complete_aperture(backend):
    node = Node({"msgbox-mailbox-num": 1, "msgbox-using-alias": 1,
                 "msgbox-using-postoffice": 1}, size=0x17f)
    backend.adt["/arm-io/test"] = node
    with pytest.raises(ValueError, match="aperture exceeds"):
        ASC.from_adt(backend, "/arm-io/test")
    node.regs[2] = (0x300000, 0x180)
    assert ASC.from_adt(backend, "/arm-io/test").msgbox.STATUS.addr == 0x300120
    assert not backend.events


@pytest.mark.parametrize("compatible", ["iop,ascwrap-v4", "iop,ascwrap-v8"])
def test_standard_asc_from_adt_preserves_arguments(backend, compatible):
    backend.adt["/arm-io/test"] = Node(compatible=compatible)
    dart = object()
    asc = StandardASC.from_adt(backend, "/arm-io/test", dart=dart, stream=3)
    assert asc.dart is dart
    assert asc.stream == 3
    assert 0 in asc.epmap
    assert (asc.msgbox is not None) == (compatible == "iop,ascwrap-v8")
    assert not backend.events
