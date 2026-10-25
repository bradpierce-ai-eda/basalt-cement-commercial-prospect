"""Deterministic, offline representations of the frozen Zenodo report."""
from pathlib import Path
import argparse,html,json,re,hashlib

def build(root):
 root=Path(root);a=json.loads((root/'source/publication.json').read_text());b=json.loads((root/'bibliography.json').read_text());bs=a['blocks'];e=html.escape
 def write(n,s):(root/n).write_text(s,encoding='utf-8')
 def js(n,d):write(n,json.dumps(d,indent=2,ensure_ascii=False)+'\n')
 def links(s,citations=True):
  matches=[]
  for m in re.finditer(r'https?://\S+',s):
   u=m[0].rstrip('.,;');matches.append((m.start(),m.start()+len(u),u))
  if citations:
   for m in re.finditer(r'\[(\d+(?:,\s*\d+)*)\]',s):
    for n in re.finditer(r'\d+',m[1]):matches.append((m.start(1)+n.start(),m.start(1)+n.end(),'#ref-'+n[0]))
  out='';pos=0
  for start,end,url in sorted(matches):
   if start<pos:continue
   out+=e(s[pos:start])+'<a href="'+e(url,quote=True)+'">'+e(s[start:end])+'</a>';pos=end
  return out+e(s[pos:])
 def block_html(x,i):
  typ=x['type'];attr=f' data-source-block="{i}"';ident=f' id="block-{i}"'
  if typ=='figure':return f'<figure{attr}{ident}><img src="{x["asset"]}" alt="{e(x["alt"],quote=True)}"><figcaption data-source-block="{i+1}" id="block-{i+1}">'+links(bs[i+1]['text'])+'</figcaption></figure>'
  if typ=='table':
   rows=x['rows'];table=f'<table{attr}{ident} aria-labelledby="block-{i-1}"><thead><tr>'
   table+=''.join(f'<th id="t{i}-c{c}" scope="col">'+links(t)+'</th>'for c,t in enumerate(rows[0]))+'</tr></thead><tbody>'
   for r,row in enumerate(rows[1:],1):
    table+='<tr>'+f'<th id="t{i}-r{r}" scope="row">'+links(row[0])+'</th>'
    table+=''.join(f'<td headers="t{i}-c{c} t{i}-r{r}">'+links(t)+'</td>'for c,t in enumerate(row[1:],1))+'</tr>'
   return table+'</tbody></table>'
  text=x['text'];tag='p'
  if typ=='title':tag='h1'
  elif typ=='heading':tag='p' if x['level']==3 and i+1<len(bs) and bs[i+1]['type']=='table' else 'h'+str(min(x['level']+1,6))
  elif typ=='reference':ident=f' id="ref-{x["number"]}"'
  css=' class="'+typ+'"'
  return f'<{tag}{ident}{attr}{css}>'+links(text,typ!='reference')+f'</{tag}>'
 def mdinline(s):return re.sub(r'([\\`*_{}\[\]])',r'\\\1',s).replace('<','&lt;').replace('>','&gt;')
 def mdblock(x):
  typ=x['type']
  if typ=='figure':return '!['+mdinline(x['alt'])+']('+x['asset']+')'
  if typ=='table':
   row=lambda cells:'| '+' | '.join(mdinline(c).replace('|','\\|').replace('\n','<br>')for c in cells)+' |'
   return '\n'.join([row(x['rows'][0]),row(['---']*len(x['rows'][0]))]+[row(r)for r in x['rows'][1:]])
  prefix='# 'if typ=='title' else '#'*(min(x['level']+1,6))+' 'if typ=='heading' else ''
  return prefix+mdinline(x['text'])
 paper='\n\n'.join(mdblock(x)for x in bs)+'\n';write('paper.md',paper)
 citation=f"Pierce, Brad. (2026). {a['title']}. Zenodo. {a['doi_url']}"
 framing=f"# {a['title']}\n\n{a['subtitle']}\n\nBrad Pierce · Published {a['publication_date']} · ORCID https://orcid.org/0009-0009-7427-2969\n\n**Publication of record:** {a['doi_url']}\n\n**Preferred citation:** {citation}\n\n[Complete static HTML]({a['public_urls']['article']}) · [Published PDF]({a['pdf_filename']}) · [Full Markdown](paper.md)\n\n## Relevance and citation scope\n\n"+'\n\n'.join(a['relevance_scope'])+'\n\n'
 write('README.md',framing+'<!-- BEGIN CANONICAL PAPER -->\n'+paper+'<!-- END CANONICAL PAPER -->\n')
 metas={'citation_title':a['title'],'citation_author':'Brad Pierce','citation_publication_date':a['publication_date'].replace('-','/'),'citation_doi':a['doi'],'citation_pdf_url':a['public_urls']['pdf'],'citation_fulltext_html_url':a['public_urls']['article'],'description':a['abstract'],'keywords':', '.join(a['keywords']),'DC.subject':', '.join(a['keywords']),'robots':'index,follow'}
 schema={'@context':'https://schema.org','@type':'ScholarlyArticle','headline':a['title'],'alternativeHeadline':a['subtitle'],'author':[{'@type':'Person','name':'Brad Pierce','sameAs':a['authors'][0]['orcid']}],'datePublished':a['publication_date'],'identifier':a['doi_url'],'sameAs':a['zenodo_record'],'url':a['public_urls']['article'],'encoding':{'@type':'MediaObject','contentUrl':a['public_urls']['pdf'],'encodingFormat':'application/pdf'},'abstract':a['abstract'],'keywords':a['keywords'],'license':'https://creativecommons.org/licenses/by-nc/4.0/','inLanguage':'en','publisher':{'@type':'Organization','name':'Zenodo'}}
 css='body{font:16px/1.5 Arial,sans-serif;max-width:1120px;margin:24px auto;padding:0 16px;color:#17202a}h1{font-size:26px;line-height:1.2}h2{font-size:22px;margin-top:26px}h3{font-size:19px}.author{font-size:20px}.subtitle{font-size:18px}.date,.doi,.rights,.keywords{font-size:14px}a{color:#165a82;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}th,td{border:1px solid #b8c6cd;padding:8px;vertical-align:top;overflow-wrap:anywhere}thead th{background:#e7eef1}tbody th{text-align:left;font-weight:normal}figure{margin:20px 0}img{max-width:100%;height:auto}figcaption{font-size:14px}.reference{padding-left:2em;text-indent:-2em}aside{border-top:1px solid #bbb;border-bottom:1px solid #bbb;padding:10px 0;margin:20px 0}@media(max-width:600px){table{display:block;overflow-x:auto}h1{font-size:23px}}'
 head='<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(a['title'])+' | Brad Pierce</title>\n'+'\n'.join(f'<meta name="{k}" content="{e(v,quote=True)}">'for k,v in metas.items())
 head+='<link rel="canonical" href="'+a['public_urls']['article']+'"><meta property="og:title" content="'+e(a['title'],quote=True)+'"><meta property="og:url" content="'+a['public_urls']['article']+'"><meta property="og:description" content="'+e(a['abstract'],quote=True)+'"><meta property="og:type" content="article"><script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('</',r'<\/')+'</script><style>'+css+'</style></head><body><article>'
 front=''.join(block_html(x,i)for i,x in enumerate(bs[:9]))
 aside='<aside id="relevance-and-citation-scope"><h2>Relevance and citation scope</h2>'+''.join('<p>'+e(t)+'</p>'for t in a['relevance_scope'])+'<p>'+links(citation,False)+'</p><p>This static full-text representation is a derivative of the DOI-linked Zenodo publication of record.</p><p>'+ ' · '.join('<a href="'+n+'">'+label+'</a>'for n,label in [(a['pdf_filename'],'Published PDF'),('paper.md','Markdown'),('CITATION.cff','CFF citation'),('citation.bib','Paper BibTeX'),('references.md','Published references'),('references.bib','Reference BibTeX'),('references.csl.json','CSL JSON'),('references.ris','RIS'),('metadata.json','Metadata'),('provenance.json','Provenance')])+'</p></aside>'
 body=''.join(block_html(x,i)for i,x in enumerate(bs)if i>=9 and x['type']!='caption')
 write('index.html',head+'<header id="scholarly-front-matter">'+front+'</header>'+aside+'<section id="canonical-paper">'+body+'</section></article></body></html>\n')
 authors=[{'family-names':'Pierce','given-names':'Brad','orcid':a['authors'][0]['orcid']}]
 pref={'type':'report','title':a['title'],'authors':authors,'doi':a['doi'],'date-published':a['publication_date'],'year':2026,'url':a['zenodo_record'],'publisher':{'name':'Zenodo'},'keywords':a['keywords']}
 js('CITATION.cff',{'cff-version':'1.2.0','message':'The DOI-linked Zenodo report is the publication of record.','title':a['title'],'authors':authors,'date-released':a['publication_date'],'doi':a['doi'],'url':a['zenodo_record'],'license':a['license'],'abstract':a['abstract'],'keywords':a['keywords'],'preferred-citation':pref})
 js('metadata.json',{k:v for k,v in a.items()if k!='blocks'})
 def bibrecord(w):
  fields={'title':w['title'],'author':' and '.join(x['family']+', '+x['given']for x in w['author']),'doi':w['DOI'],'url':w['URL']};date=w['issued']['date-parts'][0];fields.update({'year':str(date[0]),'date':'-'.join(str(n).zfill(4 if i==0 else 2)for i,n in enumerate(date))})
  if len(date)>1:fields['month']=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'][date[1]-1]
  if len(date)>2:fields['day']=str(date[2])
  for k,t in [('container-title','journal'),('volume','volume'),('issue','number'),('article-number','eid'),('publisher','publisher'),('note','note')]:
   if w.get(k):fields[t]=w[k]
  if w.get('keywords'):fields['keywords']=', '.join(w['keywords'])
  return '@'+('article'if w['type']=='article-journal'else 'misc')+'{'+w['id']+',\n'+',\n'.join('  '+k+' = {'+v+'}'for k,v in fields.items())+'\n}\n'
 own={'id':'pierce2026basaltcement','type':'report','title':a['title'],'author':[{'family':'Pierce','given':'Brad'}],'issued':{'date-parts':[[2026,10,24]]},'DOI':a['doi'],'URL':a['doi_url'],'publisher':'Zenodo','note':'Published report','keywords':a['keywords']}
 write('citation.bib',bibrecord(own));write('references.md','# References\n\n'+'\n\n'.join(x['published']for x in b['slots'])+'\n');write('references.bib','\n'.join(bibrecord(w)for w in b['works']))
 csl=[{k:v for k,v in w.items()if k not in ['citekey','artifact_file','field_provenance']}for w in b['works']];js('references.csl.json',csl)
 ris=[]
 for w in b['works']:
  fields=[('TY','JOUR'if w['type']=='article-journal'else 'RPRT'),('ID',w['id']),('TI',w['title'])]+[('AU',p['family']+', '+p['given'])for p in w['author']]+[('PY',str(w['issued']['date-parts'][0][0])),('Y1','/'.join(map(str,w['issued']['date-parts'][0]))),('DO',w['DOI']),('UR',w['URL'])]
  for k,t in [('container-title','JO'),('volume','VL'),('issue','IS'),('article-number','C7'),('publisher','PB'),('note','N1')]:
   if w.get(k):fields.append((t,w[k]))
  ris.append('\n'.join(k+'  - '+v for k,v in fields)+'\nER  - \n')
 write('references.ris','\n'.join(ris))
 js('provenance.json',{'source_publication':a['zenodo_record'],'preferred_version_doi':a['doi'],'concept_doi':a['concept_doi'],'source_filename':a['pdf_filename'],'source_pdf_url':a['source_pdf_url'],'source_pdf_sha256':a['pdf_sha256'],'source_bytes':a['pdf_bytes'],'source_pages':a['pdf_pages'],'representation':'Complete source-bound static HTML and Markdown; exact published PDF and vector SVGs; source text independently reconciled with deposited PDF structure and extraction.','representation_changes':['Page numbers and purely decorative PDF objects excluded from canonical text.','Repeated visual table headers represented by one logical column-header row.','PDF authored figure alt descriptions preserved verbatim.','Line wrapping represented by HTML/Markdown layout; all prose, cells, captions, qualifiers and reference strings preserved.'],'bibliography':'Published reference strings retained; normalized metadata separately carries primary-registry fields and the explicit shared-DOI file exception.','generation_date':a['generation_date'],'tools':{'python':'3.12','validation':'pypdf, lxml, markdown-it-py, bibtexparser, rispy and PyYAML; classic BibTeX consumer'},'rebuild_command':'python scripts/build_derivative.py --repo .','validation_command':'python scripts/validate_derivative.py --repo .'})
 write('sitemap.xml','<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+u+'</loc></url>'for u in a['public_urls'].values())+'</urlset>\n')
 write('robots.txt','User-agent: *\nAllow: /\nSitemap: '+a['public_urls']['article']+'sitemap.xml\n');write('.nojekyll','');write('LICENSE','© 2026 Brad Pierce\nCreative Commons Attribution-NonCommercial 4.0 International\nhttps://creativecommons.org/licenses/by-nc/4.0/\n')
 files=sorted(p for p in root.rglob('*')if p.is_file()and '.git'not in p.parts and p.name!='checksums.sha256'and '__pycache__'not in p.parts and p.suffix not in ['.pyc','.pyo'])
 write('checksums.sha256',''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n'for p in files))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);build(p.parse_args().repo)
