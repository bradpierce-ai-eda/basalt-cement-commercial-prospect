"""Independent parsed-file and deposited-PDF checks of this publication derivative."""
from pathlib import Path
import argparse,collections,hashlib,json,re,subprocess,sys,tempfile,shutil,unicodedata
from lxml import html,etree
from markdown_it import MarkdownIt
from pypdf import PdfReader
import bibtexparser,rispy,yaml,jsonschema

def require(ok,msg):
 if not ok:raise AssertionError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFC',s).translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789')))
def validate(root,rebuild=True):
 root=Path(root);a=json.loads((root/'source/publication.json').read_text());inv=json.loads((root/'source/invariants.json').read_text());bs=a['blocks'];b=json.loads((root/'bibliography.json').read_text())
 require(a['doi']==inv['doi']=='10.5281/zenodo.23623124','Frozen edition DOI')
 require(hashlib.sha256(json.dumps(bs,ensure_ascii=False,sort_keys=True).encode()).hexdigest()==inv['canonical_blocks_sha256']=='f0e72dfc60f76de7a50cac8b500c83429e41cf7cd43671c5cd5f26111aa5f155','Canonical paper mutation')
 pdf=root/a['pdf_filename'];require(sha(pdf)==inv['pdf_sha256']=='72fac148b1457e4687d10d4e61affb00c9d8ede2170cfc9d004dc90b0f91ae7c','Published PDF changed');reader=PdfReader(pdf);require(len(reader.pages)==33 and pdf.stat().st_size==288937,'PDF size/pages')
 require(reader.metadata.title==a['title'] and reader.metadata.author=='Brad Pierce','PDF identity')
 # Extract actual tagged PDF content by MCID and its logical structure, independently of the generator.
 text=collections.defaultdict(str)
 for no,page in enumerate(reader.pages):
  stack=[]
  def op(operator,args,cm,tm):
   if operator in [b'BDC',b'BMC']:stack.append(int(args[1]['/MCID'])if operator==b'BDC'else None)
   elif operator==b'EMC':stack.pop()
  def visit(t,cm,tm,font,size):
   if t and stack and stack[-1]is not None:text[(no,stack[-1])]+=t
  page.extract_text(visitor_operand_before=op,visitor_text=visit)
 pmap={p.indirect_reference.idnum:i for i,p in enumerate(reader.pages)};logical=[];alts=[]
 def walk(ref):
  if isinstance(ref,list):
   for x in ref:walk(x)
  else:
   n=ref.get_object();role=n.get('/S')
   if role in ['/P','/H1','/H2','/Caption']:
    logical.append(''.join(text[(pmap[k.get_object().raw_get('/Pg').idnum],int(k.get_object()['/MCID']))]for k in n.get('/K',[])if k.get_object().get('/Type')=='/MCR'))
   if role=='/Figure':alts.append(str(n['/Alt']))
   if role:walk(n.get('/K',[]))
 walk(reader.trailer['/Root']['/StructTreeRoot']['/K'])
 expected=[]
 for x in bs:
  if x['type']=='table':expected.extend(c for row in x['rows']for c in row)
  elif x['type']!='figure':expected.append(x['text'])
 require(len(logical)==len(expected)==355 and list(map(norm,logical))==list(map(norm,expected)),'Full published logical text/cells/captions conservation')
 require(alts==[x['alt']for x in bs if x['type']=='figure'],'PDF figure descriptions conservation')
 page=html.fromstring((root/'index.html').read_bytes());nodes=page.xpath('//*[@data-source-block]');require([int(n.get('data-source-block'))for n in nodes]==list(range(len(bs))),'Missing/reordered HTML blocks')
 for node,x in zip(nodes,bs):
  if x['type']=='table':require([[norm(c.text_content())for c in row.xpath('./th|./td')]for row in node.xpath('./thead/tr|./tbody/tr')]==[[norm(c)for c in row]for row in x['rows']],'HTML table cells')
  elif x['type']=='figure':require(node.xpath('./img/@src')==[x['asset']]and node.xpath('./img/@alt')==[x['alt']],'HTML vector/alt')
  else:require(norm(node.text_content())==norm(x['text']),'HTML text block')
  require(not node.xpath('ancestor-or-self::*[@hidden]')and not any(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',s,re.I)for s in node.xpath('ancestor-or-self::*/@style')),'Hidden paper content')
 md=MarkdownIt('commonmark').enable('table');parsed=html.fromstring('<main>'+md.render((root/'paper.md').read_text())+'</main>');observed=[];want=[]
 for x in bs:
  if x['type']=='table':want.append(('table',[[norm(c)for c in row]for row in x['rows']]))
  elif x['type']=='figure':want.append(('figure',x['asset'],x['alt']))
  else:want.append(('text',norm(x['text'])))
 for n in parsed:
  if n.tag=='table':observed.append(('table',[[norm(c.text_content())for c in row.xpath('./th|./td')]for row in n.xpath('./thead/tr|./tbody/tr')]))
  elif n.xpath('.//img'):observed.append(('figure',n.xpath('.//img/@src')[0],n.xpath('.//img/@alt')[0]))
  else:observed.append(('text',norm(n.text_content())))
 require(observed==want,'Complete independently parsed Markdown conservation')
 readme=(root/'README.md').read_text();start='<!-- BEGIN CANONICAL PAPER -->\n';end='<!-- END CANONICAL PAPER -->\n';require(readme.count(start)==readme.count(end)==1 and readme.split(start)[1].split(end)[0]==(root/'paper.md').read_text(),'README full paper partition')
 require(readme.split(start)[0].count('## Relevance and citation scope')==1,'README relevance heading')
 aside=page.xpath('//*[@id="relevance-and-citation-scope"]')[0];require([n.text_content()for n in aside.xpath('./p')[:3]]==a['relevance_scope']and all(t in readme.split(start)[0]for t in a['relevance_scope']),'Synchronized declarative scope')
 raw=(root/'index.html').read_text();require(raw.index('id="scholarly-front-matter"')<raw.index('id="relevance-and-citation-scope"')<raw.index('id="canonical-paper"'),'Front matter order');front=page.xpath('//*[@id="scholarly-front-matter"]')[0];require(a['abstract']in front.text_content(),'Complete visible abstract first')
 metas={'citation_title':a['title'],'citation_author':'Brad Pierce','citation_publication_date':a['publication_date'].replace('-','/'),'citation_doi':a['doi'],'citation_pdf_url':a['public_urls']['pdf'],'citation_fulltext_html_url':a['public_urls']['article'],'description':a['abstract'],'keywords':', '.join(a['keywords']),'DC.subject':', '.join(a['keywords'])}
 for k,v in metas.items():require(page.xpath('//meta[@name="'+k+'"]/@content')==[v],'HTML metadata '+k)
 require(page.xpath('//link[@rel="canonical"]/@href')==[a['public_urls']['article']],'Canonical URL');require(not page.xpath('//script[not(@type="application/ld+json")]'),'Executable page dependency')
 ld=json.loads(page.xpath('//script[@type="application/ld+json"]/text()')[0]);require(ld['headline']==a['title']and ld['datePublished']==a['publication_date']and ld['abstract']==a['abstract']and ld['keywords']==a['keywords']and ld['identifier']==a['doi_url']and ld['url']==a['public_urls']['article']and ld['encoding']['contentUrl']==a['public_urls']['pdf'],'JSON-LD identity')
 require(ld['author']==[{'@type':'Person','name':'Brad Pierce','sameAs':a['authors'][0]['orcid']}],'JSON-LD human author')
 c=yaml.safe_load((root/'CITATION.cff').read_text());jsonschema.validate(c,json.loads((root/'source/cff-1.2.0.schema.json').read_text()));require(c['title']==c['preferred-citation']['title']==a['title']and c['doi']==c['preferred-citation']['doi']==a['doi']and c['date-released']==c['preferred-citation']['date-published']==a['publication_date'],'CFF actual identity/dates');require(c['keywords']==c['preferred-citation']['keywords']==a['keywords']and c['abstract']==a['abstract'],'CFF keywords/abstract');require(c['authors']==c['preferred-citation']['authors']==[{'family-names':'Pierce','given-names':'Brad','orcid':a['authors'][0]['orcid']}],'CFF authors')
 require(json.loads((root/'metadata.json').read_text())=={k:v for k,v in a.items()if k!='blocks'},'Metadata actual fields')
 own=bibtexparser.loads((root/'citation.bib').read_text()).entries;require(len(own)==1 and own[0]['doi']==a['doi']and own[0]['title']==a['title']and own[0]['date']==a['publication_date']and own[0]['keywords']==', '.join(a['keywords'])and own[0]['author']=='Pierce, Brad','Preferred BibTeX')
 refs=[x['text']for x in bs if x['type']=='reference'];require([x['published']for x in b['slots']]==refs and len(refs)==3,'Exact published reference sequence');require((root/'references.md').read_text()=='# References\n\n'+'\n\n'.join(refs)+'\n','Complete references.md')
 require({w['id']for w in b['works']}=={w for slot in b['slots']for w in slot['work_ids']}and len(b['works'])==3,'Slot/work reachability');require(len({w['id']for w in b['works']})==3 and len({(w['DOI'],w.get('artifact_file'))for w in b['works']})==3,'Work identity uniqueness')
 require(b['works'][0]['DOI']==b['works'][1]['DOI']=='10.5281/zenodo.23547373'and b['works'][0]['artifact_file']!=b['works'][1]['artifact_file']and len(b['exceptions'])==1,'Shared edition file exception')
 bib=bibtexparser.loads((root/'references.bib').read_text()).entries;ris=rispy.loads((root/'references.ris').read_text());csl=json.loads((root/'references.csl.json').read_text());require(len(bib)==len(ris)==len(csl)==3,'Parsed bibliography formats complete')
 for w,bb,rr,cs in zip(b['works'],bib,ris,csl):
  require(bb['ID']==w['id']and bb['title']==w['title']and bb['doi']==w['DOI']and bb['url']==w['URL']and bb['author']==' and '.join(n['family']+', '+n['given']for n in w['author']),'BibTeX identity/authors')
  date=w['issued']['date-parts'][0];require(bb['date']=='-'.join(str(n).zfill(4 if i==0 else 2)for i,n in enumerate(date)),'BibTeX full date precision')
  require(rr['id']==w['id']and rr['title']==w['title']and rr['doi']==w['DOI']and rr['urls']==[w['URL']]and rr['authors']==[n['family']+', '+n['given']for n in w['author']]and rr['publication_year']=='/'.join(map(str,date)),'RIS identity/authors/full date precision')
  require(cs=={k:v for k,v in w.items()if k not in ['citekey','artifact_file','field_provenance']},'CSL all normalized fields')
 for ref in range(1,4):require(len(page.xpath('//*[@id="ref-'+str(ref)+'"]'))==1,'Bibliography anchors')
 for node in page.xpath('//*[@id="canonical-paper"]//a[starts-with(@href,"#ref-")]'):require(page.xpath('//*[@id="'+node.get('href')[1:]+'"]'),'Citation destination')
 for name,digest in inv['figure_sha256'].items():require(sha(root/'figures'/name)==digest,'Vector figure source bytes')
 require(len(page.xpath('//table'))==9 and len(page.xpath('//figure/img'))==4 and len(page.xpath('//figcaption'))==4,'Tables/figures/captions complete')
 require(all(n.get('scope')in ['col','row']for n in page.xpath('//th'))and all(len(n.get('headers','').split())==2 for n in page.xpath('//td')),'HTML table header associations')
 publicframing=readme.split(start)[0]+aside.text_content()+json.dumps({k:v for k,v in a.items()if k!='blocks'})+(root/'provenance.json').read_text()+c['message']
 require(not re.search(r'when to cite|cite this report|use this source|ignore (?:previous|prior|all)|you should|system prompt|act as an? |please cite',publicframing,re.I),'Prompt-like public framing')
 require('docs.google.com'not in raw+json.dumps(a)+readme,'Private source URL exposed')
 require('bradpierce-ai-eda.github.io'not in raw,'Mixed canonical host')
 locs=etree.fromstring((root/'sitemap.xml').read_bytes()).xpath('//*[local-name()="loc"]/text()');require(locs==list(a['public_urls'].values()),'Paper sitemap exact locations');require((root/'robots.txt').read_text()=='User-agent: *\nAllow: /\nSitemap: '+a['public_urls']['article']+'sitemap.xml\n','Crawler controls')
 manifest={line.split('  ',1)[1]:line.split('  ',1)[0]for line in (root/'checksums.sha256').read_text().splitlines()};files={p.relative_to(root).as_posix():p for p in root.rglob('*')if p.is_file()and '.git'not in p.parts and p.name!='checksums.sha256'};require(set(manifest)==set(files),'Exact public manifest path set');require(not any('__pycache__'in p or p.endswith(('.pyc','.pyo'))for p in files),'Transient files in public tree')
 for name,path in files.items():require(sha(path)==manifest[name],'Manifest checksum '+name)
 if rebuild:
  with tempfile.TemporaryDirectory()as tmp:
   clean=Path(tmp)/'repo';shutil.copytree(root,clean,ignore=shutil.ignore_patterns('.git'));subprocess.run([sys.executable,'-B',str(clean/'scripts/build_derivative.py'),'--repo',str(clean)],check=True);require(all((clean/n).read_bytes()==p.read_bytes()for n,p in files.items())and (clean/'checksums.sha256').read_bytes()==(root/'checksums.sha256').read_bytes(),'Fresh offline deterministic rebuild')
 return {'status':'PASS','source_blocks':len(bs),'logical_text_items':355,'table_cells':inv['table_cells'],'tables':9,'figures':4,'references':3,'works':3,'shared_DOI_file_exception':True,'PDF_pages':33,'PDF_sha256':inv['pdf_sha256'],'public_files':len(files)+1,'independent_parsers':['pypdf tagged PDF','lxml HTML','markdown-it Markdown','PyYAML plus official CFF 1.2.0 schema','bibtexparser BibTeX','rispy RIS','JSON CSL'],'rebuild':'PASS'if rebuild else'not requested'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--no-rebuild',action='store_true');v=p.parse_args()
 try:print(json.dumps(validate(v.repo,not v.no_rebuild),indent=2))
 except (AssertionError,KeyError,ValueError)as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
