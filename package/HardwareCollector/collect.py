#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
"""Offline upstream Hardware-Sniffer runner with explicit Linux parity corrections.

Never changes an installed OS, NVRAM, PCI registers, or internal filesystems.
Raw upstream output and raw hardware evidence accompany the normalized report.
"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent


def text(p):
    try:
        return Path(p).read_text(errors='replace').strip()
    except OSError:
        return ''


def number(value):
    try:
        return int(value, 16 if value.lower().startswith('0x') else 10)
    except (ValueError, AttributeError):
        return None


def dump(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + '.partial')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(p)


def insert(mapping, name, value):
    name = name or 'Unnamed measured device'
    key = name
    index = 1
    while key in mapping:
        key = f'{name}_#{index}'
        index += 1
    mapping[key] = value
    return key


def acpi_path(value):
    return value.replace('\\_SB_.', '\\_SB.')


def physical_topology(sysroot):
    pairs, packages = set(), set()
    for cpu in (Path(sysroot) / 'devices/system/cpu').glob('cpu[0-9]*'):
        package = text(cpu / 'topology/physical_package_id')
        core = text(cpu / 'topology/core_id')
        if package and core and package != '-1' and core != '-1':
            pairs.add((package, core))
            packages.add(package)
    return len(pairs), len(packages)


def firmware_secureboot(sysroot):
    p = Path(sysroot) / 'firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c'
    try:
        raw = p.read_bytes()
    except OSError:
        return None
    # efivarfs files start with a four-byte attributes field, not ASCII digits.
    return {0: 'Disabled', 1: 'Enabled'}.get(raw[4]) if len(raw) >= 5 else None


def pci_location(device, sysroot):
    result = {}
    real = device.resolve()
    parts = real.parts
    roots = [i for i, s in enumerate(parts) if re.fullmatch(r'pci[0-9a-f]{4}:[0-9a-f]{2}', s)]
    if roots:
        root_dir = Path(*parts[:roots[0] + 1])
        # PCI segment is NOT the ACPI root bridge's _UID.
        uid = number(text(root_dir / 'firmware_node/uid'))
        if uid is not None:
            segments = [f'PciRoot(0x{uid:x})']
            for part in parts[roots[0] + 1:]:
                match = re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:([0-9a-f]{2})\.([0-7])', part)
                if match:
                    segments.append(f'Pci(0x{int(match[1],16):x},0x{int(match[2],16):x})')
            if len(segments) > 1:
                result['PCI Path'] = '/'.join(segments)
    value = text(device / 'firmware_node/path')
    if value:
        result['ACPI Path'] = acpi_path(value)
    return result


def rebar_state(config):
    """Report observable PCIe ReBAR state without guessing from BAR addresses."""
    if len(config) < 0x104:
        return None, 'extended PCI configuration unreadable'
    offset, visited = 0x100, set()
    while offset and offset not in visited:
        if offset < 0x100 or offset % 4 or offset + 4 > len(config):
            return None, 'truncated or invalid PCIe capability chain'
        visited.add(offset)
        header = struct.unpack_from('<I',config,offset)[0]
        if header in [0,0xffffffff]:
            return 'Disabled', 'no ReBAR capability exposed'
        if header & 0xffff == 0x15:
            if offset + 12 > len(config):
                return None, 'truncated ReBAR control'
            control = struct.unpack_from('<I',config,offset+8)[0]
            entries = ((control>>5)&7)+1
            controls=[]
            for i in range(entries):
                if offset + 12 + 8*i > len(config):
                    return None, 'truncated ReBAR entries'
                controls.append(struct.unpack_from('<I',config,offset+8+8*i)[0])
            if any(((c>>8)&0x3f)>8 for c in controls):
                return 'Enabled', 'ReBAR control selects an aperture larger than 256 MiB'
            return None, 'ReBAR supported with <=256 MiB aperture; Windows driver enable state not inferred'
        offset = (header>>20)&0xfff
    if offset in visited:
        return None, 'cyclic PCIe capability chain'
    return 'Disabled', 'complete capability chain contains no ReBAR capability'


def pci_inventory(sysroot):
    found = []
    for p in sorted((Path(sysroot) / 'bus/pci/devices').glob('*')):
        vendor, ident = text(p / 'vendor'), text(p / 'device')
        if not vendor or not ident:
            continue
        cls = text(p / 'class').removeprefix('0x').zfill(6).upper()
        d = {'slot': p.name, 'class': cls, 'sysfs': str(p.resolve()),
             'Bus Type': 'PCI', 'Device ID': f'{int(vendor,16):04X}-{int(ident,16):04X}'}
        sv, sd = text(p / 'subsystem_vendor'), text(p / 'subsystem_device')
        if sv and sd:
            d['Subsystem ID'] = f'{int(sd,16):04X}{int(sv,16):04X}'
        d.update(pci_location(p, sysroot))
        try:
            d['driver'] = (p / 'driver').resolve(strict=True).name
        except OSError:
            d['driver'] = None
        found.append(d)
    return found


def report_pci(device):
    return {k: device[k] for k in ['Bus Type','Device ID','Subsystem ID','PCI Path','ACPI Path'] if k in device}


def parent_pci(path, devices):
    matches = [d for d in devices if Path(path).resolve().is_relative_to(Path(d['sysfs']))]
    return max(matches, key=lambda d: len(d['sysfs']), default=None)


def collect_audio(sysroot, procroot, devices, evidence):
    codecs = {}
    for p in sorted((Path(sysroot) / 'bus/hdaudio/devices').glob('*')):
        value = number(text(p / 'vendor_id'))
        if value is None:
            continue
        d = {'Bus Type': 'HDAUDIO', 'Device ID': f'{value>>16:04X}-{value&0xffff:04X}'}
        subsystem = number(text(p / 'subsystem_id'))
        if subsystem is not None:
            d['Subsystem ID'] = f'{subsystem:08X}'
        parent = parent_pci(p, devices)
        if parent:
            d['Controller Device ID'] = parent['Device ID']
        name = ' '.join(filter(None, [text(p / 'vendor_name'), text(p / 'chip_name')])) or p.name
        insert(codecs, name, d)
        evidence.append({'field': 'Sound/' + name, 'source': str(p), 'kind': 'measured HDA codec ID'})
    # Some drivers expose the codec proc dump but no hdaudio sysfs class.
    for p in sorted((Path(procroot) / 'asound').glob('card*/codec#*')):
        content = text(p)
        vid = re.search(r'^Vendor Id:\s*0x([0-9a-f]+)', content, re.M | re.I)
        if not vid:
            continue
        value = int(vid[1],16)
        ident = f'{value>>16:04X}-{value&0xffff:04X}'
        parent = parent_pci(Path(sysroot)/'class/sound'/p.parent.name/'device', devices)
        if any(v.get('Device ID') == ident and (not parent or v.get('Controller Device ID') == parent['Device ID']) for v in codecs.values()):
            continue
        name = re.search(r'^Codec:\s*(.+)', content, re.M)
        d = {'Bus Type': 'HDAUDIO', 'Device ID': ident}
        sub = re.search(r'^Subsystem Id:\s*0x([0-9a-f]+)', content, re.M | re.I)
        if sub:
            d['Subsystem ID'] = f'{int(sub[1],16):08X}'
        if parent:
            d['Controller Device ID'] = parent['Device ID']
        insert(codecs, name[1] if name else p.name, d)
    return codecs


def collect_monitors(sysroot, gpu_by_slot, evidence):
    monitors = {}
    for p in sorted((Path(sysroot) / 'class/drm').glob('card*-*')):
        if text(p/'status') != 'connected':
            continue
        card = p.name.split('-')[0]
        slot = (p.parent/card/'device').resolve().name
        gpu = gpu_by_slot.get(slot)
        modes = [tuple(map(int, m.split('x'))) for m in text(p/'modes').splitlines() if re.fullmatch(r'\d+x\d+', m)]
        if not gpu or not modes:
            evidence.append({'field': 'Monitor/'+p.name, 'source': str(p), 'issue': 'connected display lacks GPU mapping or readable modes'})
            continue
        width, height = max(modes, key=lambda v:v[0]*v[1])
        connector = p.name[len(card)+1:].rsplit('-',1)[0]
        connector = {'DisplayPort':'DP','HDMI-A':'HDMI','HDMI-B':'HDMI','DVI-D':'DVI','DVI-I':'DVI','DVI-A':'DVI'}.get(connector, connector)
        if connector not in ['VGA','DVI','HDMI','LVDS','DP','eDP','Internal']:
            connector = 'Uninitialized'
        edid = b''
        try:
            edid = (p/'edid').read_bytes()
        except OSError:
            pass
        name = p.name
        if len(edid) >= 128:
            manufacturer = int.from_bytes(edid[8:10],'big')
            name = ''.join(chr(64+((manufacturer>>s)&31)) for s in [10,5,0])+f'{int.from_bytes(edid[10:12],"little"):04X}'
        insert(monitors, name, {'Connector Type':connector,'Resolution':f'{width}x{height}','Connected GPU':gpu})
        evidence.append({'field': 'Monitor/'+name,'source':str(p),'edid_hex':edid.hex(),
                         'edid_checksum_valid':len(edid)>=128 and len(edid)%128==0 and all(sum(edid[i:i+128])%256==0 for i in range(0,len(edid),128))})
    return monitors


def collect_acpi_inventory(sysroot):
    result = []
    for p in sorted((Path(sysroot)/'bus/acpi/devices').glob('*')):
        result.append({'sysfs':str(p.resolve()),'name':p.name,'hid':text(p/'hid'),
                       'cid':text(p/'modalias'),'path':acpi_path(text(p/'path')),'status':text(p/'status'),
                       'physical_nodes':[str(x.resolve()) for x in p.glob('physical_node*')]})
    return result


def collect_inputs(sysroot, acpi, evidence):
    result, seen = {}, set()
    for p in sorted((Path(sysroot)/'class/input').glob('input[0-9]*')):
        real = p.resolve()
        name, bus = text(p/'name'), text(p/'id/bustype')
        if not name or bus not in ['0011','0018','0019','0003','0005']:
            continue
        if any(t in name.lower() for t in ['power button','sleep button','lid switch','pc speaker','wireless radio controls']):
            continue
        if bus in ['0011','0018','0019']:
            matches = [d for d in acpi if d['hid'] and any(real.is_relative_to(Path(n)) for n in d['physical_nodes'])]
            # Walk only actual firmware_node links. Do not manufacture HIDs from names.
            for ancestor in [real, *real.parents]:
                hid = text(ancestor/'firmware_node/hid')
                if hid:
                    matches.append({'hid':hid,'path':text(ancestor/'firmware_node/path')})
                    break
            if not matches:
                evidence.append({'field':'Input/'+name,'source':str(real),'issue':'ACPI HID not resolved','bus':bus})
                continue
            d = {'Bus Type':'ACPI','Device':matches[0]['hid'],'Device Type':{'0011':'PS/2','0018':'I2C HID','0019':'Host input'}[bus]}
        else:
            vid, pid = text(p/'id/vendor'), text(p/'id/product')
            if not vid or not pid:
                continue
            d = {'Bus Type':'USB','Device ID':f'{int(vid,16):04X}-{int(pid,16):04X}'}
        key = tuple(sorted(d.items()))
        if key not in seen:
            seen.add(key)
            insert(result,name,d)
    return result


def commands(output):
    for name, argv in {
        'lspci':['lspci','-nnk'], 'lsusb':['lsusb'], 'dmidecode':['dmidecode'],
        'lsblk':['lsblk','-J','-o','NAME,TYPE,SIZE,TRAN,MODEL,SERIAL'],
        'dmesg':['dmesg'], 'aplay':['aplay','-l'], 'rfkill':['rfkill','list'],
    }.items():
        if not shutil.which(argv[0]):
            continue
        try:
            p = subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=20)
            (output/(name+'.txt')).write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
        except Exception as exc:
            (output/(name+'.txt')).write_text(str(exc),encoding='utf-8')


def validate_report(report_path, output):
    # A separate process avoids the two upstream projects' Scripts package collision.
    verifier = BASE/'validate_report.py'
    p = subprocess.run([sys.executable,str(verifier),str(report_path),str(output/'Validation.json')],capture_output=True,text=True,timeout=30)
    if p.returncode:
        raise RuntimeError(p.stderr or p.stdout)
    return json.loads((output/'Validation.json').read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--sys-root',default='/sys')
    parser.add_argument('--proc-root',default='/proc')
    args = parser.parse_args()
    if args.sys_root != '/sys' or args.proc_root != '/proc':
        raise SystemExit('Fixture-only unit tests use individual functions; full collection requires native Linux')
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    evidence, failures, upstream = [], [], {}
    sys.path.insert(0,str(BASE/'vendor/Hardware-Sniffer'))
    from Scripts.platforms.linux import LinuxHardwareInfo
    from Scripts.datasets import pci_data
    from Scripts import utils
    utils.Utils.head = lambda *a, **k:None
    h = LinuxHardwareInfo(rich_format=False)
    steps = [('pci_devices',None),('motherboard','Motherboard'),('bios','BIOS'),('cpu','CPU'),('gpu','GPU'),
             ('monitor','Monitor'),('network','Network'),('sound','Sound'),('usb_controllers','USB Controllers'),
             ('input','Input'),('storage_controllers','Storage Controllers'),('biometric','Biometric'),
             ('bluetooth','Bluetooth'),('sd_controller','SD Controller'),('system_devices','System Devices')]
    h.result = upstream
    with (output/'upstream.log').open('w',encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        for method, category in steps:
            try:
                value = getattr(h,method)()
                if category:
                    upstream[category] = value or {}
            except Exception:
                failures.append({'method':method,'traceback':traceback.format_exc()})
                if category:
                    upstream[category] = {}
    dump(output/'Report.upstream.json',upstream)
    report = json.loads(json.dumps(upstream))
    pci = pci_inventory(args.sys_root)
    acpi = collect_acpi_inventory(args.sys_root)
    missing = []

    cores, packages = physical_topology(args.sys_root)
    if cores and packages:
        report.setdefault('CPU',{}).update({'Core Count':str(cores).zfill(2),'CPU Count':str(packages).zfill(2)})
        evidence.append({'field':'CPU/Core Count','source':'/sys/devices/system/cpu/cpu*/topology/{physical_package_id,core_id}','physical_cores':cores})
    else:
        report.setdefault('CPU',{}).pop('Core Count',None)
        missing.append('CPU physical core topology unavailable')
    # Linux calls the SSE3 flag pni. Preserve upstream CPU codename lookup.
    flags = text(Path(args.proc_root)/'cpuinfo')
    if re.search(r'\bpni\b',flags) and 'SSE3' not in report.get('CPU',{}).get('SIMD Features','').split(', '):
        report['CPU']['SIMD Features'] = ', '.join(filter(None,[report['CPU'].get('SIMD Features',''),'SSE3']))
    chassis = number(text(Path(args.sys_root)/'class/dmi/id/chassis_type'))
    dmi = Path(args.sys_root)/'class/dmi/id'
    manufacturer = text(dmi/'sys_vendor') or text(dmi/'board_vendor')
    model = text(dmi/'product_name') or text(dmi/'board_name')
    # Empty optional board DMI strings crash the upstream motherboard method.
    # Keep the measured system DMI even when those board strings are missing.
    report.setdefault('Motherboard',{})['Name'] = ' '.join(filter(None,[manufacturer,model])).upper() or 'Unknown'
    from Scripts.datasets import chipset_data
    chipset = next((chipset_data.chipset_controllers[d['Device ID']] for d in pci if d['Device ID'] in chipset_data.chipset_controllers),None)
    report['Motherboard']['Chipset'] = chipset or report['Motherboard'].get('Chipset') or 'Unknown'
    if report['Motherboard']['Chipset']=='Unknown':
        missing.append('Chipset not recognized by upstream PCI database')
    if chassis is not None:
        report.setdefault('Motherboard',{})['Platform'] = 'Laptop' if chassis in [8,9,10,14,30,31,32] else 'Desktop'
    secure = firmware_secureboot(args.sys_root)
    if secure:
        report.setdefault('BIOS',{})['Secure Boot'] = secure
    else:
        report.setdefault('BIOS',{}).pop('Secure Boot',None)
        missing.append('SecureBoot firmware variable unreadable')
    report.get('BIOS',{}).pop('Above 4G Decoding',None)

    gpu, gpu_slots = {}, {}
    networks, storage, usb, system = {}, {}, {}, {}
    for d in pci:
        # Names never decide whether a PCI function exists; numeric class IDs do.
        name, _ = h.get_pci_device_name_and_class(d['slot'])
        if name == 'Unknown':
            name = d['Device ID']
        prop = report_pci(d)
        if d['class'].startswith('03'):
            info = h.classify_gpu(d['Device ID'])
            info.update({k:v for k,v in prop.items() if k!='Bus Type'})
            # Active ReBAR state cannot be inferred merely from a large BAR.
            config = Path(d['sysfs'])/'config'
            try:
                raw_config = config.read_bytes()
                evidence.append({'field':'GPU/'+name+'/PCI configuration','source':str(config),'hex':raw_config.hex()})
                state, reason = rebar_state(raw_config)
                evidence.append({'field':'GPU/'+name+'/Resizable BAR','state':state,'reason':reason})
                if state:
                    info['Resizable BAR'] = state
                else:
                    missing.append('Resizable BAR state requires review: '+name)
            except OSError:
                missing.append('GPU PCI configuration unreadable: '+name)
            gpu_slots[d['slot']] = insert(gpu,name,info)
            if not prop.get('PCI Path') or not prop.get('ACPI Path'):
                missing.append('GPU location incomplete: '+name)
        elif d['class'].startswith('02'):
            insert(networks,name,prop)
        elif d['class'].startswith(('0108','0106','0104','0101')):
            if d['class'].startswith('0108') and 'NVMe' not in name and 'NVM Express' not in name:
                name += ' (NVMe)'
            if d['class'].startswith('010601') and 'AHCI' not in name:
                name += ' (AHCI)'
            insert(storage,name,prop)
        elif d['class'].startswith('0C03'):
            insert(usb,name,prop)
        # Controllers (including HDA) also belong in System Devices so the
        # generator can resolve a codec's Controller Device ID to its PCI path.
        insert(system,name,prop)
    report['GPU'] = dict(sorted(gpu.items(),key=lambda v:v[1].get('Device Type','')))
    report['Monitor'] = collect_monitors(args.sys_root,gpu_slots,evidence)
    for key,val in upstream.get('Network',{}).items():
        if val.get('Bus Type') == 'USB':
            insert(networks,key,val)
    report['Network'], report['Storage Controllers'], report['USB Controllers'] = networks, storage, usb
    for d in acpi:
        if d['hid']:
            prop = {'Bus Type':'ACPI','Device':d['hid']}
            if re.fullmatch(r'\\?_SB(\.[A-Z0-9_]+)+',d['path']):
                prop['ACPI Path'] = d['path']
            insert(system,d['name'],prop)
    report['System Devices'] = system
    report['Input'] = collect_inputs(args.sys_root,acpi,evidence)
    for e in evidence:
        if e.get('field','').startswith('Input/') and e.get('issue'):
            missing.append(e['field']+': '+e['issue'])
    measured_audio = collect_audio(args.sys_root,args.proc_root,pci,evidence)
    # Preserve real USB/Bluetooth audio from upstream; PCI controllers are not codecs.
    for name,value in upstream.get('Sound',{}).items():
        if value.get('Bus Type') == 'USB':
            insert(measured_audio,name,value)
    report['Sound'] = measured_audio
    for d in pci:
        if d['class'].startswith('0403') and not any(v.get('Controller Device ID')==d['Device ID'] for v in measured_audio.values()):
            missing.append('No measured codec for HDA controller '+d['slot']+' ('+d['Device ID']+'): review audio/AMFIPass selection')
        if d['class'].startswith(('02','0108','0106','0104','0101','0C03')) and not d.get('PCI Path'):
            missing.append('PCI path unresolved: '+d['slot']+' ('+d['Device ID']+')')
    if any(d['class'].startswith('0401') for d in pci) and not measured_audio:
        missing.append('Non-HDA audio controller detected; codec identification requires review')
    if report.get('Motherboard',{}).get('Platform')=='Laptop' and not report['Monitor']:
        missing.append('Laptop panel/connected GPU unresolved; EDID and connector need review')
    # Recover disabled/unbound USB Bluetooth adapters using measured VID/PID.
    bluetooth = dict(report.get('Bluetooth',{}))
    usb_devices = []
    for p in sorted((Path(args.sys_root)/'bus/usb/devices').glob('*')):
        vid,pid = text(p/'idVendor'),text(p/'idProduct')
        if not vid or not pid:
            continue
        ident = f'{int(vid,16):04X}-{int(pid,16):04X}'
        usb_devices.append({'sysfs':str(p.resolve()),'Device ID':ident,'product':text(p/'product')})
        if ident in pci_data.BluetoothIDs and not any(v.get('Device ID')==ident for v in bluetooth.values()):
            insert(bluetooth,text(p/'product') or ident,{'Bus Type':'USB','Device ID':ident})
    report['Bluetooth'] = bluetooth
    for category in ['Motherboard','BIOS','CPU','GPU','Network','USB Controllers','Storage Controllers','Input']:
        if not report.get(category):
            missing.append(category+' not collected')
    if report.get('CPU',{}).get('Codename') in [None,'Unknown']:
        missing.append('CPU codename not recognized by upstream lookup')

    dump(output/'Report.raw.json',report)
    dump(output/'Evidence.json',{'pci':pci,'usb':usb_devices,'acpi_devices':acpi,'fields':evidence,'upstream_errors':failures})
    acpi_dir = output/'ACPI'
    acpi_dir.mkdir()
    for source in sorted((Path(args.sys_root)/'firmware/acpi/tables').glob('*')):
        if source.is_file():
            try:
                shutil.copyfile(source,acpi_dir/(source.name+'.aml'))
            except OSError as exc:
                missing.append('ACPI '+source.name+': '+str(exc))
    dynamic = Path(args.sys_root)/'firmware/acpi/tables/dynamic'
    for source in sorted(dynamic.glob('*')):
        if source.is_file():
            shutil.copyfile(source,acpi_dir/('dynamic-'+source.name+'.aml'))
    if not any(p.read_bytes()[:4]==b'DSDT' for p in acpi_dir.glob('*.aml')):
        missing.append('DSDT not captured')
    validation = validate_report(output/'Report.raw.json',output)
    if not validation['valid']:
        missing.extend(validation['errors'])
    (output/'Report.json').write_text(json.dumps(validation['cleaned'],ensure_ascii=False,indent=2),encoding='utf-8')
    readiness = {'format':'opcore-hardware-collection-v1','collector_os':'Linux',
                 'hardware_sniffer_commit':'403cc25bc14be65c45a1e0ea9cfd3567103e9a73',
                 'opcore_commit':'f0e1e441bb455c33e9695a9c9c50e8ca931d4de8',
                 'schema_valid':validation['valid'],'missing_or_review':sorted(set(missing)),
                 'generation_ready':validation['valid'] and not missing,
                 'windows_equivalence_verified':False,
                 'note':'Schema validity does not prove physical completeness or equivalence to a Windows capture. Original output and corrections are preserved.'}
    dump(output/'Readiness.json',readiness)
    rawdir=output/'Raw'
    rawdir.mkdir()
    for p in sorted((Path(args.proc_root)/'asound').glob('card*/codec#*')):
        try:
            shutil.copyfile(p,rawdir/(p.parent.name+'-'+p.name+'.txt'))
        except OSError:
            pass
    for name in ['DMI','smbios_entry_point']:
        p=Path(args.sys_root)/'firmware/dmi/tables'/name
        if p.is_file():
            try:
                shutil.copyfile(p,rawdir/name)
            except OSError:
                pass
    commands(output)
    manifest = {str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    dump(output/'SHA256.json',manifest)
    print('REPORT SAVED: '+str(output))
    print('Schema: '+('PASS' if validation['valid'] else 'FAIL'))
    print('Review required: '+str(len(set(missing))))
    for item in sorted(set(missing)):
        print('  - '+item)
    print('COLLECTION_COMPLETE')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
