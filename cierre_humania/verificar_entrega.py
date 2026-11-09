"""Auditoría de artefactos HumanIA. Solo lectura.
Ejecutar: python verificar_entrega.py [carpeta_con_los_tres_archivos]
"""
from pathlib import Path
from hashlib import sha256
import re, sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET

base=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
DOCX='borrador_f79d5354cb744d6fa73bbced2d6b712e.docx'
PDF='contrato_aprobado_6.pdf'
CONST='constancia_aprobacion_6.pdf'

def texto_docx(path):
    with ZipFile(path) as z:
        contents=[]
        for name in z.namelist():
            if name in ('word/document.xml','word/header1.xml','word/footer1.xml'):
                xml=ET.fromstring(z.read(name))
                contents.extend(n.text or '' for n in xml.iter() if n.tag.endswith('}t'))
        return ' '.join(contents)

def texto_pdf(path):
    try:
        from pypdf import PdfReader
        return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)
    except ImportError:
        raise RuntimeError('Instalá pypdf con: uv pip install pypdf')

fallos=[]
for file in (DOCX,PDF,CONST):
    if not (base/file).is_file(): fallos.append('Archivo faltante: '+file)
if fallos:
    print('\n'.join('ERROR: '+f for f in fallos));sys.exit(1)

doc=texto_docx(base/DOCX)
pdf=texto_pdf(base/PDF)
const=texto_pdf(base/CONST)
h=sha256((base/DOCX).read_bytes()).hexdigest()
print('=== AUDITORIA DE DOCUMENTOS HUMAnIA (SOLO LECTURA) ===')
print('DOCX SHA256:',h)
print('SHA registrado en constancia:', 'COINCIDE' if h.lower() in re.sub(r'\s+','',const).lower() else 'NO COINCIDE')
if h.lower() not in re.sub(r'\s+','',const).lower():fallos.append('Huella DOCX no coincide con constancia')
for key in ('Pedro Gómez','00.000.005','1.100.000','Formosa'):
    print(f'Dato {key}:', 'OK' if key in doc and key in pdf else 'REVISAR')
    if key not in doc or key not in pdf: fallos.append('Dato ausente o distinto en DOCX/PDF: '+key)
for key in ('cc0512e7-d3e3-43d0-b9ca-7399676554c9','APROBADO'):
    print(f'Constancia {key}:', 'OK' if key in const else 'REVISAR')
    if key not in const: fallos.append('Constancia no contiene '+key)
for label,txt in [('DOCX',doc),('PDF',pdf)]:
    is_draft='BORRADOR - SIN APROBACION FINAL' in txt.upper()
    print(f'LEYENDA PENDIENTE {label}:', 'SI (REQUIERE CORRECCION DEL EXPORTADOR)' if is_draft else 'NO')
    if is_draft: fallos.append(f'{label} aún marcado borrador sin aprobación final')
print('RESULTADO:', 'APTO PARA REVISAR' if not fallos else 'PENDIENTES: '+str(len(fallos)))
for f in fallos: print('-',f)
if fallos: sys.exit(2)
