#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
from pathlib import Path
import json
import sys

base = Path(__file__).resolve().parent
sys.path.insert(0,str(base/'vendor/OpCore-Simplify'))
from Scripts.report_validator import ReportValidator

valid, errors, warnings, cleaned = ReportValidator().validate_report(sys.argv[1])
Path(sys.argv[2]).write_text(json.dumps({'valid':valid,'errors':errors,'warnings':warnings,'cleaned':cleaned},ensure_ascii=False,indent=2),encoding='utf-8')
