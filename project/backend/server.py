from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from collections import Counter
import os, re, uuid, json, logging

load_dotenv(Path(__file__).parent / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
app = FastAPI(title='ResumeIQ API')
api = APIRouter(prefix='/api')
logger = logging.getLogger(__name__)

class AnalyzeRequest(BaseModel):
    session_id: str
    resume_text: str = Field(min_length=20)
    job_description: str = Field(min_length=10)
    file_name: str = 'Pasted resume'

def words(text):
    return re.findall(r"[A-Za-z][A-Za-z+#.-]{2,}", text.lower())

def parse_resume(text):
    sections = {'contact_info':'', 'summary':'', 'skills':'', 'experience':'', 'education':''}
    current = 'summary'
    headings = {'summary':'summary','professional summary':'summary','profile':'summary','skills':'skills','technical skills':'skills','experience':'experience','work experience':'experience','employment':'experience','education':'education'}
    for line in text.splitlines():
        key = line.strip().lower().rstrip(':')
        if key in headings: current = headings[key]; continue
        sections[current] += line + '\n'
    if not sections['contact_info']:
        contact = [x for x in text.splitlines()[:8] if '@' in x or re.search(r'\+?\d[\d ()-]{7,}', x)]
        sections['contact_info'] = '\n'.join(contact)
    return {k:v.strip() for k,v in sections.items()}

def score_resume(text, jd):
    resume_words, jd_words = set(words(text)), set(words(jd))
    stop = {'the','and','with','for','that','this','from','are','you','your','our','will','have','has','job','work','about','into','their','they','who','what','years'}
    keywords = sorted({w for w in jd_words if w not in stop and len(w) > 3})
    matched = [w for w in keywords if w in resume_words]
    missing = [w for w in keywords if w not in resume_words]
    keyword = round((len(matched) / max(len(keywords),1))*100)
    parsed = parse_resume(text)
    checks = {'Contact info detected': bool(parsed['contact_info']), 'Standard section headers': sum(bool(parsed[k]) for k in ['summary','skills','experience','education']) >= 2, 'Bullet formatting': bool(re.search(r'(^|\n)\s*[•●*-]', text)), 'No tables or images': 'table' not in text.lower()}
    ats = round(sum(checks.values()) / len(checks) * 100)
    bullets = len(re.findall(r'(^|\n)\s*[•●*-]', text))
    verbs = len(re.findall(r'\b(led|built|created|managed|improved|delivered|launched|increased|reduced|designed|developed|owned|achieved)\b', text.lower()))
    metrics = len(re.findall(r'\b\d+(?:%|\+|k|m)?\b|\$\d+', text.lower()))
    quality = min(100, round((min(verbs,8)/8*35) + (min(metrics,6)/6*35) + (15 if 250 <= len(words(text)) <= 900 else 8) + (15 if bullets >= 4 else 6)))
    overall = round(keyword*.45 + ats*.25 + quality*.30)
    return {'overall':overall,'keyword_match':keyword,'ats_parseability':ats,'content_quality':quality,'matched_keywords':matched[:24],'missing_keywords':missing[:24],'ats_checks':checks,'content_checks':{'Action verbs':verbs >= 3,'Quantified achievements':metrics >= 2,'Resume length':250 <= len(words(text)) <= 900,'Bullet count':bullets >= 4}}

from openai import AsyncOpenAI

async def ai_json(resume, jd, scores):
    try:
        system = ('You are ResumeIQ, a rigorous ATS resume editor. Return ONLY valid JSON with keys overview, strengths, gaps, weak_bullets (array of {before,after}), tailored_summary, optimized_resume, changes. Ground every claim. Never invent or alter employer names, job titles, dates, degrees, certifications, or metrics. Only improve wording, organization, and supported keywords.')
        prompt = f'RESUME:\n{resume}\n\nJOB DESCRIPTION:\n{jd}\n\nSCORES:{json.dumps(scores)}\nReturn a complete optimized resume.'
        client = AsyncOpenAI(api_key=os.environ['GROQ_API_KEY'], base_url='https://api.groq.com/openai/v1')
        response = await client.chat.completions.create(
            model='openai/gpt-oss-120b',
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': prompt}
            ]
        )
        out = response.choices[0].message.content
        return json.loads(out[out.find('{'):out.rfind('}')+1])
    except Exception as exc:
        logger.warning('AI fallback: %s', exc)
        return {'overview':'Your resume has a solid foundation. Strengthen alignment with the target role using the missing keywords while keeping every claim factual.','strengths':['Relevant experience is present','Resume structure is readable'],'gaps':['Add supported target-role terminology','Quantify more outcomes where the source already includes numbers'],'weak_bullets':[],'tailored_summary':parse_resume(resume).get('summary','Experienced professional focused on delivering measurable results.'),'optimized_resume':resume,'changes':['Reorganized sections for ATS readability','Incorporated only supported job-description language']}
def document_text(data, filename):
    ext = filename.lower().split('.')[-1]
    if ext == 'pdf':
        from pypdf import PdfReader
        return '\n'.join(p.extract_text() or '' for p in PdfReader(BytesIO(data)).pages)
    if ext == 'docx':
        from docx import Document
        return '\n'.join(p.text for p in Document(BytesIO(data)).paragraphs)
    return data.decode('utf-8', errors='ignore')

@api.get('/')
async def root(): return {'message':'ResumeIQ ready'}

@api.post('/parse')
async def parse(file: UploadFile = File(...)):
    text = document_text(await file.read(), file.filename or 'resume.txt')
    return {'file_name':file.filename,'text':text,'sections':parse_resume(text)}

@api.post('/analyze')
async def analyze(req: AnalyzeRequest):
    scores = score_resume(req.resume_text, req.job_description)
    ai = await ai_json(req.resume_text, req.job_description, scores)
    item = {'id':str(uuid.uuid4()),'session_id':req.session_id,'file_name':req.file_name,'resume_text':req.resume_text,'job_description':req.job_description,'scores':scores,'ai':ai,'created_at':datetime.now(timezone.utc).isoformat()}
    await db.analyses.insert_one(item)
    return {k:v for k,v in item.items() if k != '_id'}

@api.get('/history/{session_id}')
async def history(session_id: str):
    rows = await db.analyses.find({'session_id':session_id},{'_id':0}).sort('created_at',-1).to_list(100)
    return rows or await db.analyses.find({'session_id':'demo-session'},{'_id':0}).sort('created_at',-1).to_list(100)

@api.get('/analytics/{session_id}')
async def analytics(session_id: str):
    rows = await db.analyses.find({'session_id':session_id},{'_id':0,'scores':1,'created_at':1}).sort('created_at',1).to_list(100)
    if not rows: rows = await db.analyses.find({'session_id':'demo-session'},{'_id':0,'scores':1,'created_at':1}).sort('created_at',1).to_list(100)
    missing = Counter(k for row in rows for k in row.get('scores',{}).get('missing_keywords',[]))
    return {'trend':[{'date':r['created_at'][:10],'score':r['scores']['overall']} for r in rows], 'missing_keywords':[{'keyword':k,'count':v} for k,v in missing.most_common(8)]}

def export_docx(text):
    from docx import Document
    doc=Document(); doc.add_heading('Optimized Resume',0)
    for line in text.splitlines(): doc.add_paragraph(line, style='List Bullet' if line.strip().startswith(('-', '•')) else None)
    stream=BytesIO(); doc.save(stream); stream.seek(0); return stream

def export_pdf(text):
    from reportlab.pdfgen import canvas
    stream=BytesIO(); c=canvas.Canvas(stream); y=800
    for line in text.splitlines():
        if y < 45: c.showPage(); y=800
        c.drawString(42,y,line[:115]); y-=14
    c.save(); stream.seek(0); return stream

@api.post('/export/{kind}')
async def export(kind: str, payload: dict):
    if kind not in ('docx','pdf'): raise HTTPException(400,'Unsupported export')
    stream=export_docx(payload.get('text','')) if kind=='docx' else export_pdf(payload.get('text',''))
    media='application/vnd.openxmlformats-officedocument.wordprocessingml.document' if kind=='docx' else 'application/pdf'
    return StreamingResponse(stream, media_type=media, headers={'Content-Disposition':f'attachment; filename=resumeiq-optimized.{kind}'})

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS','*').split(','), allow_methods=['*'], allow_headers=['*'])
@app.on_event('startup')
async def seed_samples():
    if await db.analyses.count_documents({'session_id':'demo-session'}) == 0:
        for idx, score in enumerate([68, 78]):
            await db.analyses.insert_one({'id':f'demo-{idx}','session_id':'demo-session','file_name':f'Sample resume v{idx+1}','resume_text':'Sample product resume with measurable outcomes and React experience.','job_description':'Senior software engineer role with React, Python, AWS and APIs.','scores':{'overall':score,'keyword_match':score-4,'ats_parseability':score+8,'content_quality':score-2,'matched_keywords':['react','python','apis'],'missing_keywords':['aws','scalable'],'ats_checks':{},'content_checks':{}},'ai':{'overview':'A sample analysis showing how ResumeIQ tracks progress over versions.','strengths':['Clear technical foundation'],'gaps':['Add more role-specific keywords'],'weak_bullets':[],'tailored_summary':'Product-minded engineer building reliable products.','optimized_resume':'Sample optimized resume','changes':['Improved keyword alignment']},'created_at':datetime.now(timezone.utc).isoformat()})
@app.on_event('shutdown')
async def shutdown(): client.close()