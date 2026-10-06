"""
Data models and parsers for USBGuard Manager.
"""

import re
from typing import Optional, Dict, Any, List

USB_INTERFACE_CLASSES = {
    "01": "Audio",
    "02": "Communications / CDC",
    "03": "Human Interface (Keyboard/Mouse)",
    "05": "Physical Interface",
    "06": "Still Imaging / Camera",
    "07": "Printer",
    "08": "Mass Storage (Flash Drive/Disk)",
    "09": "USB Hub",
    "0a": "CDC-Data",
    "0b": "Smart Card",
    "0d": "Content Security",
    "0e": "Video / Webcam",
    "dc": "Diagnostic Device",
    "e0": "Wireless Controller (Bluetooth/WiFi)",
    "ef": "Miscellaneous",
    "fe": "Application Specific",
    "ff": "Vendor Specific",
}

def decode_interface_class(iface_str: str) -> str:
    """Translates interface strings like '08:06:50' or '{ 08:06:50 }' to readable names."""
    if not iface_str:
        return "Unknown"
    cleaned = iface_str.replace("{", "").replace("}", "").strip()
    classes = []
    for token in cleaned.split():
        parts = token.split(":")
        if parts:
            cls_code = parts[0].lower()
            name = USB_INTERFACE_CLASSES.get(cls_code, f"Class {cls_code}")
            if name not in classes:
                classes.append(name)
    return ", ".join(classes) if classes else "Unknown"


class USBDevice:
    def __init__(
        self,
        rule_id: int,
        target: str,
        device_id: str,
        name: str = "",
        serial: str = "",
        via_port: str = "",
        interfaces: str = "",
        hash_val: str = "",
        raw: str = "",
        is_trusted: bool = False,
    ):
        self.rule_id = rule_id
        self.target = target.lower()  # 'allow', 'block', 'reject'
        self.device_id = device_id.lower()
        self.name = name.strip() if name else "Unknown Device"
        self.serial = serial.strip()
        self.via_port = via_port.strip()
        self.interfaces = interfaces.strip()
        self.interface_desc = decode_interface_class(self.interfaces)
        self.hash_val = hash_val
        self.raw = raw
        self.is_trusted = is_trusted

    @property
    def is_allowed(self) -> bool:
        return self.target == "allow"

    @property
    def is_blocked(self) -> bool:
        return self.target in ("block", "reject")

    @property
    def display_name(self) -> str:
        if self.name and self.name != "Unknown Device":
            return self.name
        return f"USB Device [{self.device_id}]"

    def __repr__(self):
        return f"<USBDevice id={self.rule_id} dev={self.device_id} target={self.target} name={self.name!r}>"


class USBRule:
    def __init__(
        self,
        rule_id: int,
        target: str,
        device_id: str = "",
        name: str = "",
        serial: str = "",
        raw: str = "",
    ):
        self.rule_id = rule_id
        self.target = target.lower()
        self.device_id = device_id.lower()
        self.name = name.strip()
        self.serial = serial.strip()
        self.raw = raw.strip()

    @property
    def is_allow(self) -> bool:
        return self.target == "allow"

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.device_id:
            return f"Rule for {self.device_id}"
        return f"Rule #{self.rule_id}"

    def __repr__(self):
        return f"<USBRule id={self.rule_id} target={self.target} dev={self.device_id}>"


def parse_device_line(line: str) -> Optional[USBDevice]:
    line = line.strip()
    if not line:
        return None
    m = re.match(r"^(\d+):\s+(allow|block|reject)\s+(.*)$", line, re.IGNORECASE)
    if not m:
        return None

    rule_id = int(m.group(1))
    target = m.group(2).lower()
    rest = m.group(3)

    dev_id = ""
    m_id = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\b", rest)
    if m_id:
        dev_id = m_id.group(1).lower()

    serial = ""
    m_ser = re.search(r'\bserial\s+"([^"]*)"', rest)
    if m_ser:
        serial = m_ser.group(1)

    name = ""
    m_name = re.search(r'\bname\s+"([^"]*)"', rest)
    if m_name:
        name = m_name.group(1)

    via_port = ""
    m_port = re.search(r'\bvia-port\s+"([^"]*)"', rest)
    if m_port:
        via_port = m_port.group(1)

    interfaces = ""
    m_iface = re.search(r"\bwith-interface\s+(\{[^}]*\}|\S+)", rest)
    if m_iface:
        interfaces = m_iface.group(1).strip("{} ")

    hash_val = ""
    m_hash = re.search(r'\bhash\s+"([^"]*)"', rest)
    if m_hash:
        hash_val = m_hash.group(1)

    return USBDevice(
        rule_id=rule_id,
        target=target,
        device_id=dev_id,
        name=name,
        serial=serial,
        via_port=via_port,
        interfaces=interfaces,
        hash_val=hash_val,
        raw=line,
    )


def parse_rule_line(line: str) -> Optional[USBRule]:
    line = line.strip()
    if not line:
        return None
    m = re.match(r"^(\d+):\s+(allow|block|reject)\s*(.*)$", line, re.IGNORECASE)
    if not m:
        return None

    rule_id = int(m.group(1))
    target = m.group(2).lower()
    rest = m.group(3)

    dev_id = ""
    m_id = re.search(r"\bid\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\b", rest)
    if m_id:
        dev_id = m_id.group(1).lower()

    name = ""
    m_name = re.search(r'\bname\s+"([^"]*)"', rest)
    if m_name:
        name = m_name.group(1)

    serial = ""
    m_ser = re.search(r'\bserial\s+"([^"]*)"', rest)
    if m_ser:
        serial = m_ser.group(1)

    return USBRule(
        rule_id=rule_id,
        target=target,
        device_id=dev_id,
        name=name,
        serial=serial,
        raw=line,
    )
