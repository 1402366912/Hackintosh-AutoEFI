# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
"""Meaningful fixtures: physical vs logical cores, PCI root UID, HDA IDs, efivar bytes."""
from pathlib import Path
import importlib.util
import tempfile
import struct
import unittest

P = Path(__file__).parent/'package/HardwareCollector/collect.py'
spec = importlib.util.spec_from_file_location('collector',P)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, value):
        p = self.root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(value if isinstance(value,bytes) else value.encode())
        return p

    def test_physical_core_count_is_not_logical_threads(self):
        for i in range(8):
            self.put(f'devices/system/cpu/cpu{i}/topology/core_id',str(i//2))
            self.put(f'devices/system/cpu/cpu{i}/topology/physical_package_id','0')
        self.assertEqual(c.physical_topology(self.root),(4,1))

    def test_missing_topology_does_not_invent_count(self):
        self.assertEqual(c.physical_topology(self.root),(0,0))

    def test_efivar_uses_attribute_header(self):
        name='firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c'
        self.put(name,b'\x07\x00\x00\x00\x01')
        self.assertEqual(c.firmware_secureboot(self.root),'Enabled')
        self.put(name,b'\x07\x00\x00\x00\x00')
        self.assertEqual(c.firmware_secureboot(self.root),'Disabled')
        self.put(name,b'')
        self.assertIsNone(c.firmware_secureboot(self.root))

    def test_pci_root_uid_is_not_segment(self):
        self.put('devices/pci0000:00/firmware_node/uid','128')
        p=self.put('devices/pci0000:00/0000:00:02.0/firmware_node/path','\\_SB_.PCI0.GFX0').parent.parent
        self.assertEqual(c.pci_location(p,self.root),{'PCI Path':'PciRoot(0x80)/Pci(0x2,0x0)','ACPI Path':'\\_SB.PCI0.GFX0'})

    def test_missing_root_uid_does_not_assume_zero(self):
        p=self.put('devices/pci0000:00/0000:00:02.0/vendor','0x8086').parent
        self.assertNotIn('PCI Path',c.pci_location(p,self.root))

    def test_hda_codec_is_distinct_from_controller(self):
        # On Linux this hdaudio class entry is a symlink into the PCI device.
        controller=self.root/'devices/pci0000:00/0000:00:1f.3'
        codec=controller/'hdaudioC0D0'
        codec.mkdir(parents=True)
        (codec/'vendor_id').write_text('0x10ec0256')
        (codec/'subsystem_id').write_text('0x10431ab1')
        (codec/'chip_name').write_text('ALC256')
        base=self.root/'bus/hdaudio/devices'
        base.mkdir(parents=True)
        (base/'hdaudioC0D0').symlink_to(codec,target_is_directory=True)
        evidence=[]
        found=c.collect_audio(self.root,self.root/'proc',[{'sysfs':str(controller),'Device ID':'8086-A348'}],evidence)
        val=next(iter(found.values()))
        self.assertEqual(val['Device ID'],'10EC-0256')
        self.assertEqual(val['Controller Device ID'],'8086-A348')
        self.assertEqual(val['Subsystem ID'],'10431AB1')

    def test_controller_alone_does_not_become_codec(self):
        self.assertEqual(c.collect_audio(self.root,self.root/'proc',[{'sysfs':str(self.root/'pci'),'Device ID':'8086-A348'}],[]),{})

    def test_rebar_is_not_inferred_from_large_memory_address(self):
        config=bytearray(4096)
        self.assertEqual(c.rebar_state(config)[0],'Disabled')
        struct.pack_into('<I',config,0x100,0x10015)
        struct.pack_into('<I',config,0x108,12<<8)
        self.assertEqual(c.rebar_state(config)[0],'Enabled')
        struct.pack_into('<I',config,0x108,8<<8)
        self.assertIsNone(c.rebar_state(config)[0])

    def test_short_pci_config_does_not_claim_rebar_disabled(self):
        self.assertIsNone(c.rebar_state(bytes(256))[0])


if __name__=='__main__':
    unittest.main()
