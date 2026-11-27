"""Reconcile generated employee entries; never delete manually maintained files."""
from pathlib import Path
import os
import xml.etree.ElementTree as ET
from uuid import UUID
from pydantic import BaseModel, Field

class DirectoryUser(BaseModel):
    employee_id: UUID
    sip_extension: str = Field(pattern=r'^[0-9]{2,10}$')

def reconcile(directory, users):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if len({u.sip_extension for u in users}) != len(users):
        raise ValueError('Повторяющиеся SIP-номера')
    changed = False
    wanted = set()
    for user in users:
        filename = f'employee-{user.employee_id}.xml'
        wanted.add(filename)
        include = ET.Element('include')
        entry = ET.SubElement(include, 'user', id=user.sip_extension)
        params = ET.SubElement(entry, 'params')
        ET.SubElement(params, 'param', name='password', value='$${default_password}')
        variables = ET.SubElement(entry, 'variables')
        ET.SubElement(variables, 'variable', name='user_context', value='default')
        ET.indent(include)
        content = ET.tostring(include, encoding='unicode')
        target = root / filename
        if not target.exists() or target.read_text() != content:
            temporary = root / (filename + '.tmp')
            temporary.write_text(content)
            os.replace(temporary, target)
            changed = True
    for path in root.glob('employee-*.xml'):
        if path.name not in wanted:
            path.unlink()
            changed = True
    return changed
