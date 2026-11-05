"""Conservative local integration demo: REAL 342 announcements, NO invented eligibility.

Keyword retrieval ≠ RAG. No green/yellow/red judgments without extracted conditions.
Results intentionally use '확인 필요' and meta.dataSource='mock', even though
program names and summaries come from the real database.
"""
from datetime import date
import re
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.models import Announcement, AnnouncementFile
from app.schemas import SupportMatchRequest

LOCAL_DEMO_NOTICE = '실제 공고 검색(단순 키워드) 데모입니다. 공고별 자격 조건 판정 AI가 아직 연결되지 않아 신청 가능 여부는 모두 확인 필요입니다.'
REGIONS = [('서울','서울특별시'),('인천','인천광역시'),('경기','경기도'),('부산','부산광역시'),('대구','대구광역시'),('대전','대전광역시'),('광주','광주광역시'),('울산','울산광역시'),('세종','세종특별자치시'),('강원','강원특별자치도'),('충북','충청북도'),('충남','충청남도'),('충청북','충청북도'),('충청남','충청남도'),('전북','전북특별자치도'),('전남','전라남도'),('경북','경상북도'),('경남','경상남도'),('제주','제주특별자치도')]
IGNORE = {'서울','경기','인천','부산','대구','대전','광주','울산','세종','제주','강원','경북','경남','충북','충남','전북','전남','준비','지원','사업','신청','창업','예비창업','하려고','그리고','있어요','해주세요','합니다','부탁해','저는','제가','되어','받고','원해','하려','이제','있는','싶어요','부족해요'}
TYPES = ('융자','보조금','보증','교육','멘토링','공간','사업화','기타')

def _extracted(value, evidence=None):
    return {'value':value,**({'evidence':evidence} if evidence and value is not None else {})}

def get_profile(text: str, overrides: dict | None):
    txt=re.sub(r'\[[^\]]*\]',' ',text)
    m=re.search(r'(?:만\s*)?(\d{2})\s*[살세]',txt)
    age=int(m.group(1)) if m and 14<=int(m.group(1))<=100 else None
    sido=next((s for k,s in REGIONS if k in txt),None)
    sigungu=(re.search(r'([가-힣]{1,6}(?:시|구|군))(?=[에서의은는이가도\s,.]|$)',txt) or [None])[0]
    if sigungu and sigungu in ['서울시','인천시','부산시','대전시','대구시','광주시','울산시','세종시','경기도']:
        sigungu=None
    stage='예비창업' if re.search(r'예비창업|창업\s*전|미창업|창업\s*예정',txt) else None
    if stage is None and re.search(r'(창업|개업)\s*[1-3]\s*년|업력\s*[1-3]\s*년',txt): stage='업력3년이하'
    category='카페' if re.search('카페|커피|디저트|베이커리',txt) else '음식점' if re.search('음식점|식당|분식|치킨|피자|고깃집',txt) else None
    needs=[]
    if re.search('모자라|부족|자금|대출|지원금|융자',txt): needs+=['융자','보조금']
    for k in ('교육','멘토링','공간','사업화','보증'):
        if k in txt:needs.append(k)
    fund=None
    m_money=re.search(r'(\d+(?:\.\d+)?)\s*억',txt)
    if m_money:fund=round(float(m_money.group(1))*10000)
    else:
        m_money=re.search(r'(\d+(?:\.\d+)?)\s*천\s*만',txt)
        if m_money:fund=round(float(m_money.group(1))*1000)
        else:
            m_money=re.search(r'(\d[\d,]*)\s*만\s*원?',txt)
            if m_money:fund=int(m_money.group(1).replace(',',''))
    o=overrides or {}
    # Frontend ProfileChips sends raw primitives; also accept Extracted-shaped values.
    def override(key, value):
        if key not in o: return value
        val=o[key]
        return val.get('value') if isinstance(val,dict) and 'value' in val else val
    age=override('age',age)
    sido_new=override('sido',sido)
    if sido_new!=sido:sigungu=None
    # The new profile chip editor can replace age; derived groups must use the
    # edited value, not the originally parsed one.
    groups=['청년'] if age is not None and age<=39 else []
    if re.search('소상공인|자영업',txt):groups.append('소상공인')
    if re.search('여성',txt):groups.append('여성')
    profile={
       'age':_extracted(age,'사용자 문장/수정' if age is not None else None),
       'sido':_extracted(sido_new),'sigungu':_extracted(override('sigungu',sigungu)),
       'bizStage':_extracted(override('bizStage',stage)),
       'industryCategory':_extracted(override('industryCategory',category)),
       'industryText':_extracted(None),'targetGroups':groups,'needs':needs,
       'fundingGapManwon':_extracted(fund),'budgetManwon':_extracted(None),
       'experienceYears':_extracted(None),'freeText':text
    }
    missing=[k for k in ('age','sido','bizStage','industryCategory') if profile[k]['value'] is None]
    return profile,missing

def _terms(text):
    terms=re.findall(r'[가-힣A-Za-z0-9]{2,}',text.lower())
    return list(dict.fromkeys(t for t in terms if t not in IGNORE and not t.isnumeric() and len(t)>1))[:18]

def _support_types(a):
    text=f'{a.title} {a.category_large or ""} {a.category_medium or ""} {a.summary or ""}'
    result=[]
    if re.search('융자|대출|정책자금',text):result.append('융자')
    if re.search('보조금|지원금|사업비|사업화자금',text):result.append('보조금')
    if re.search('보증|특례보증',text):result.append('보증')
    if re.search('교육|강좌|아카데미|세미나|교육생',text):result.append('교육')
    if re.search('멘토링|멘토|컨설팅',text):result.append('멘토링')
    if re.search('입주|공유오피스|사무실|창업공간',text):result.append('공간')
    if re.search('사업화|시제품|판로',text):result.append('사업화')
    return list(dict.fromkeys(result)) or ['기타']

def _score(a, terms, profile):
    title=a.title.lower();summary=(a.summary or '').lower();cats=f'{a.category_large or ""} {a.category_medium or ""}'.lower()
    hits_title=sum(t in title for t in terms)
    hits_other=sum(t in summary for t in terms)
    hits_cat=sum(t in cats for t in terms)
    val=hits_title*12+hits_other*3+hits_cat*5
    # Region mentioned is a ranking clue, never an eligibility pass/fail.
    sido=profile['sido']['value'];
    if sido:
        short=next((k for k,s in REGIONS if s==sido),None)
        tagged=re.match(r'^\s*\[([^]]+)\]', a.title)
        if (short and short in a.title) or sido in a.title:val+=14
        elif tagged:
            region_tag=tagged.group(1)
            if any(k in region_tag for k,_ in REGIONS):
                val-=12   # geographic relevance only; not an eligibility exclusion
    for n in profile['needs']:
        if n in _support_types(a):val+=3
    if profile['industryCategory']['value'] and profile['industryCategory']['value'].lower() in title:val+=5
    return max(0,int(val))

def _program(a, today):
    raw=a.raw_fields or {}
    fields={
      '공고명':a.title,'사업개요':a.summary or '',
      '지원대상':a.target_name or '',
      '신청기간':a.application_period_raw or '',
      '신청방법':a.application_method or '',
    }
    # Exact source fields available for verification; don't manufacture rule quotes.
    for k,v in raw.items():
        if isinstance(v,str) and v:fields[k]=v
    status = ('마감' if a.apply_end and a.apply_end < today else
              '모집예정' if a.apply_start and a.apply_start>today else '모집중')
    files=[{'name':f.file_name or '첨부파일','url':f.file_url} for f in sorted(a.files,key=lambda f:(f.file_role,f.sequence))]
    data={
      'id':a.announcement_id,'source':'bizinfo','portal':'기업마당',
      'sourceId':a.announcement_id,'title':a.title,'agency':a.agency or '기관 정보 미상',
      'supportTypes':_support_types(a),'support_types':a.support_types or [],'rolling':a.rolling,'status':status,
      'duplicatePolicy':{'status':'미확인'},
      'summary':a.summary or a.title,'url':a.announcement_url or '',
      'fields':fields,'fetchedAt':(a.fetched_updated_at or a.fetched_created_at or today.isoformat())[:10],
      'reviewed':False,'attachmentFiles':files,
    }
    if a.operator:data['operator']=a.operator
    if a.apply_start:data['applyStart']=a.apply_start.isoformat()
    if a.apply_end:data['applyEnd']=a.apply_end.isoformat()
    if a.contact:data['contact']=a.contact
    if a.application_url:data['applyUrl']=a.application_url
    return data

def get_match_response(request: SupportMatchRequest, session: Session, limit=12, as_of=None, extracted=None):
    today=as_of or date.today()
    profile,missing=get_profile(request.text,request.overrides)
    # Keep original UI profile shape; let AI fill available values when enabled.
    ai_terms = ''
    if extracted is not None:
        search = extracted['검색정보']
        extra = extracted['추가추출값']
        user = extracted['사용자프로필']
        def put(key, value):
            if value is not None and not (request.overrides and key in request.overrides):
                profile[key] = _extracted(value, 'AI 추출')
        put('age', extra.get('나이_언급'))
        put('sido', search.get('검색시도'))
        put('sigungu', search.get('검색지역'))
        stage = extra.get('창업단계_언급')
        put('bizStage', '예비창업' if stage=='예비' else '업력3년이하' if stage=='개업' and (extra.get('업력_개월') or 0)<=36 else None)
        put('industryText', search.get('업종원문표현'))
        needs = [x for x in search.get('필요지원',[]) if x!='미지정']
        if needs: profile['needs']=needs
        if user.get('성별') == '여성' and '여성' not in profile['targetGroups']:
            profile['targetGroups'].append('여성')
        age = profile['age']['value']
        if age is not None and age <= 39 and '청년' not in profile['targetGroups']:
            profile['targetGroups'].append('청년')
        missing = [k for k in ('age','sido','bizStage','industryCategory') if profile[k]['value'] is None]
        ai_terms = ' '.join([*search.get('필요지원키워드',[]),*search.get('상황키워드',[])])
    terms=_terms(request.text + ' ' + ai_terms)
    announcements=session.scalars(select(Announcement).options(selectinload(Announcement.files))).all()
    # For the demo, show listings with an explicit future close date or explicit all-year receipt.
    # No inference from '예산 소진시까지' that the window is still open.
    active=[]
    for a in announcements:
        # Filter only after a reviewed region_map.csv has populated the columns.
        # Unmapped/unknown region never gets guessed from the title.
        if a.region == '타지역':
            continue
        if a.region == '서울' and profile['sido']['value'] not in (None, '서울특별시', '서울'):
            continue
        if a.seoul_gu and a.seoul_gu.strip():
            allowed_gu = {g.strip() for g in a.seoul_gu.split(',') if g.strip()}
            user_gu = profile['sigungu']['value']
            # Unknown district must not be treated as a known mismatch.
            if user_gu is not None and user_gu not in allowed_gu:
                continue
        if a.apply_end is not None:
            if a.apply_start and a.apply_start>today:continue
            if a.apply_end < today:continue
        elif not (a.rolling and a.application_period_raw and re.search(r'상시\s*접수|연중|수시',a.application_period_raw)):
            continue
        s=_score(a,terms,profile)
        active.append((s,a))
    active.sort(key=lambda pair:(pair[0], pair[1].apply_end or date.max),reverse=True)
    # Return meaningful matches, but also allow general requests to see examples.
    candidates=[(score,a) for score,a in active if score>0]
    if not candidates:candidates=active
    results=[]
    for score,a in candidates[:limit]:
        program=_program(a,today)
        # Score is a *display relevance* score, NOT an eligibility confidence probability.
        percent=max(1,min(80,20+score))
        days=(a.apply_end-today).days if a.apply_end else None
        results.append({
          'program':program,'verdict':'확인 필요','score':percent,'searchScore':float(score),'judgmentScore':None,'rules':[],
          'headline':'관련 공고 검색됨 · 신청자격 확인 필요',
          'reasons':[],'cautions':[], 'exceptions':[], 'daysLeft':days
        })
    return {
      'profile':profile,'missing':missing,'results':results,'conditional':[],'excluded':[],
      'nextSteps':[],
      'summary':{'eligibleCount':0,'checkCount':len(results),
                 'conditional':{'bizStage':0,'sigungu':0},'urgent':None,'caution':None},
      'coverage':{'sources':[{'portal':'기업마당','count':len(announcements)}],
                  'total':len(announcements),'asOf':today.isoformat(),'regions':[]},
      'meta':{'dataSource':'mock','parser':('schema-v0.4-extraction' if extracted is not None else 'rule'),'indexBuiltAt':today.isoformat(),
              'totalPrograms':len(announcements),'droppedClaims':0},
      # Additive field; current frontend ignores it. Local patched frontend shows its own notice.
      'demoNotice':LOCAL_DEMO_NOTICE,
    }
