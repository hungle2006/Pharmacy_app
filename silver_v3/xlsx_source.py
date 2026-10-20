"""Read-only, streaming XLSX reader using Python standard-library OpenXML."""
import re,zipfile,xml.etree.ElementTree as ET
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
RN='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def index(ref):
 letters=re.match(r'[A-Z]+',ref.upper()).group();n=0
 for c in letters:n=n*26+ord(c)-64
 return n-1
def stream_rows(filename,sheet=None):
 with zipfile.ZipFile(filename) as z:
  wb=ET.fromstring(z.read('xl/workbook.xml'))
  rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
  links={x.attrib['Id']:x.attrib['Target'] for x in rel}
  sheets=wb.findall(f'{{{NS}}}sheets/{{{NS}}}sheet')
  chosen=next((s for s in sheets if s.attrib.get('name')==sheet),None) if sheet else sheets[0]
  if chosen is None:raise ValueError('Missing worksheet '+str(sheet))
  p=links[chosen.attrib[f'{{{RN}}}id']].lstrip('/')
  if not p.startswith('xl/'):p='xl/'+p
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'));shared=[''.join(x.itertext()) for x in root]
  with z.open(p) as stream:
   headers=None
   for _,e in ET.iterparse(stream,events=('end',)):
    if e.tag!=f'{{{NS}}}row':continue
    cells={}
    for c in e.findall(f'{{{NS}}}c'):
     i=index(c.attrib.get('r','A1'));t=c.attrib.get('t')
     v=c.find(f'{{{NS}}}v');isnode=c.find(f'{{{NS}}}is')
     val=(v.text or '') if v is not None else ''.join(isnode.itertext()) if isnode is not None else ''
     if t=='s' and val:val=shared[int(val)]
     if t not in ('s','inlineStr','str') and re.fullmatch(r'\d+\.0',val):val=val[:-2]
     cells[i]=val
    if headers is None:
     headers=[cells.get(i,'') or f'unnamed_{i+1}' for i in range(max(cells,default=-1)+1)]
     if len(set(headers))!=len(headers):raise ValueError('Duplicate headers')
    else:yield dict(zip(headers,(cells.get(i,'') for i in range(len(headers)))))
    e.clear()
