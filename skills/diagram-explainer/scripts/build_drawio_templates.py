#!/usr/bin/env python3
"""Convert this skill's generated teaching masters into editable draw.io templates.

Only reads the generated masters named by their index. Never migrates user boards.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

FONT = '나눔손글씨 다행체'


def model(scene):
    graph = ET.Element('mxGraphModel', dx='1200', dy='900', grid='1', gridSize='10',
                       page='1', pageScale='1', pageWidth='1200', pageHeight='900',
                       background='#ffffff')
    root = ET.SubElement(graph, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    elements = [e for e in scene['elements'] if not e.get('isDeleted')]
    ids = {e['id'] for e in elements}
    labels = {e['containerId']: e for e in elements if e['type'] == 'text' and e.get('containerId')}
    for e in elements:
        if e['type'] == 'text' and e.get('containerId'):
            continue
        kind = e['type']
        assert kind in {'rectangle', 'ellipse', 'diamond', 'text', 'line', 'arrow'}, kind
        style = dict(strokeColor=e['strokeColor'], strokeWidth=e['strokeWidth'],
                     fillColor=e['backgroundColor'] if e['backgroundColor'] != 'transparent' else 'none',
                     fontFamily=FONT, html=0)
        if e['strokeStyle'] != 'solid':
            style.update(dashed=1, dashPattern='1 3' if e['strokeStyle'] == 'dotted' else '6 4')
        attrs = dict(id=e['id'], parent='1', value=e.get('text', ''))
        if kind in {'line', 'arrow'}:
            attrs['edge'] = '1'
            style.update(endArrow='classic' if e.get('endArrowhead') else 'none',
                         startArrow='classic' if e.get('startArrowhead') else 'none',
                         rounded=1, endFill=1)
            for binding, terminal, prefix in [('startBinding', 'source', 'exit'),
                                               ('endBinding', 'target', 'entry')]:
                b = e.get(binding)
                if b:
                    assert b['elementId'] in ids
                    attrs[terminal] = b['elementId']
                    pt = b.get('fixedPoint', [.5, .5])
                    style.update({prefix+'X': pt[0], prefix+'Y': pt[1], prefix+'Perimeter': 1})
                    style[terminal+'PerimeterSpacing'] = b.get('gap', 0)
        else:
            attrs['vertex'] = '1'
            if kind == 'rectangle':
                is_cylinder_body = any(t['type'] == 'ellipse' and t['x'] == e['x'] and t['width'] == e['width'] and abs(t['y']-e['y']) <= 30 for t in elements)
                style.update(rounded=0 if is_cylinder_body else 1, arcSize=16)
            elif kind in {'ellipse', 'diamond'}:
                style['shape'] = 'ellipse' if kind == 'ellipse' else 'rhombus'
            else:
                style.update(shape='text', strokeColor='none', fillColor='none',
                             fontSize=e['fontSize'], fontColor=e['strokeColor'],
                             align=e.get('textAlign', 'left'), verticalAlign='top',
                             whiteSpace='nowrap', overflow='visible', spacing=0)
            if e['id'] in labels:
                label = labels[e['id']]
                attrs['value'] = label['text']
                style.update(fontSize=label['fontSize'], align='center', verticalAlign='middle',
                             whiteSpace='nowrap', overflow='visible', spacing=8)
        attrs['style'] = ';'.join(f'{k}={v}' for k, v in style.items())+';'
        cell = ET.SubElement(root, 'mxCell', **attrs)
        if kind in {'line', 'arrow'}:
            geom = ET.SubElement(cell, 'mxGeometry', relative='1', **{'as': 'geometry'})
            points = [(e['x']+p[0], e['y']+p[1]) for p in e['points']]
            for terminal, point in [('source', points[0]), ('target', points[-1])]:
                if terminal not in attrs:
                    ET.SubElement(geom, 'mxPoint', x=str(point[0]), y=str(point[1]), **{'as': terminal+'Point'})
            if len(points) > 2:
                arr = ET.SubElement(geom, 'Array', **{'as': 'points'})
                for x, y in points[1:-1]:
                    ET.SubElement(arr, 'mxPoint', x=str(x), y=str(y))
        else:
            gap = 6 if kind == 'rectangle' and not e.get('roundness') and style.get('rounded') == 1 else 0
            ET.SubElement(cell, 'mxGeometry', x=str(e['x']+gap/2), y=str(e['y']+gap/2),
                          width=str(e['width']-gap), height=str(e['height']-gap), **{'as': 'geometry'})
    return graph


def build(source, destination):
    index = json.loads((source/'index.json').read_text())
    assert isinstance(index, list) and len(index) == 36
    destination.mkdir(parents=True, exist_ok=True)
    library, updated = [], []
    for entry in index:
        name = entry['file']
        assert Path(name).name == name and name.endswith('.excalidraw')
        scene = json.loads((source/name).read_text())
        graph = model(scene)
        xml = ET.tostring(graph, encoding='unicode')
        target = destination/(Path(name).stem+'.drawio')
        mxfile = ET.Element('mxfile', host='diagram-explainer', version='32.4.1')
        page = ET.SubElement(mxfile, 'diagram', id=Path(name).stem, name=entry['title'])
        page.append(graph)
        content = ET.tostring(mxfile, encoding='unicode')
        if target.exists() and target.read_text() != content:
            raise ValueError(f'Preserve existing edited template: {target}')
        target.write_text(content)
        saved = ET.parse(target).getroot()
        cells = saved.findall('.//mxCell')
        assert len({c.get('id') for c in cells}) == len(cells)
        bound_labels = sum(e['type'] == 'text' and bool(e.get('containerId')) for e in scene['elements'])
        assert len(cells) == len(scene['elements'])-bound_labels+2
        library.append(dict(xml=xml, w=1200, h=900, aspect='fixed', title=entry['title']))
        updated.append({**entry, 'file': target.name})
    lib = ET.Element('mxlibrary')
    lib.text = json.dumps(library, ensure_ascii=False)
    (destination/'diagram-explainer.drawio-library.xml').write_text(ET.tostring(lib, encoding='unicode'))
    (destination/'index.json').write_text(json.dumps(updated, ensure_ascii=False, indent=2))
    assert len(json.loads(ET.parse(destination/'diagram-explainer.drawio-library.xml').getroot().text)) == 36
    print(f'Parsed and read back {len(updated)} draw.io templates and 36 library entries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)
