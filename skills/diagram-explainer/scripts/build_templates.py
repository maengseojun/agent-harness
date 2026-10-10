#!/usr/bin/env python3
"""Build editable Excalidraw teaching templates. No network or app automation."""
import argparse
import json
from pathlib import Path
from PIL import ImageFont

FONT = '나눔손글씨 다행체'
FONT_FILE = Path.home() / 'Library/Fonts/NanumDaHaengCe.ttf'
INK = '#20252b'
PAPER = '#ffffff'
BLUE = '#e5eff8'
GREEN = '#e8f1e9'
AMBER = '#fff2d5'


class Scene:
    def __init__(self, slug, title, note):
        self.slug, self.elements = slug, []
        self.text(title, 40, 25, 44)
        self.text(note, 40, 90, 26)

    def element(self, kind, x, y, w, h, **extra):
        index = len(self.elements) + 1
        e = dict(type=kind, id=f'{self.slug}-{index}', x=x, y=y,
                 width=w, height=h, angle=0, strokeColor=INK,
                 backgroundColor='transparent', fillStyle='solid',
                 strokeWidth=2, strokeStyle='solid', roughness=1,
                 opacity=100, groupIds=[], frameId=None,
                 roundness={'type': 3} if kind == 'rectangle' else None,
                 seed=index * 719, version=1, versionNonce=index * 997,
                 isDeleted=False, boundElements=None, updated=0, link=None,
                 locked=False)
        e.update(extra)
        self.elements.append(e)
        return e

    def text(self, value, x, y, size=30, container=None, center=None):
        font = ImageFont.truetype(str(FONT_FILE), size)
        w = max(font.getlength(line) for line in value.split('\n')) + 4
        h = len(value.split('\n')) * size * 1.3
        if center is not None:
            x, y = center[0] - w / 2, center[1] - h / 2
        e = self.element('text', x, y, w, h, text=value,
                         originalText=value, fontSize=size, fontFamily=FONT,
                         textAlign='center' if container else 'left',
                         verticalAlign='middle' if container else 'top',
                         containerId=container['id'] if container else None,
                         autoResize=True, lineHeight=1.3)
        if container:
            container['boundElements'] = [*(container['boundElements'] or []),
                                          {'id': e['id'], 'type': 'text'}]
        return e

    def box(self, label, x, y, w=220, h=110, kind='rectangle', fill=BLUE,
            size=30, dash=False):
        e = self.element(kind, x, y, w, h, backgroundColor=fill,
                         strokeStyle='dashed' if dash else 'solid')
        if label:
            self.text(label, x, y, size, e, (x+w/2, y+h/2))
        return e

    def line(self, x1, y1, x2, y2, dash=False, arrow=False, label=None,
             style=None, points=None):
        points = points or [[0,0],[x2-x1,y2-y1]]
        e = self.element('arrow' if arrow else 'line', x1, y1,
                         max(p[0] for p in points)-min(p[0] for p in points),
                         max(p[1] for p in points)-min(p[1] for p in points), points=points,
                         startBinding=None, endBinding=None,
                         startArrowhead=None, endArrowhead='arrow' if arrow else None,
                         strokeStyle=style or ('dashed' if dash else 'solid'))
        if label:
            self.text(label, (x1+x2)/2, (y1+y2)/2-40, 24)
        return e

    def arrow(self, a, b, label=None, vertical=False, dash=False, routed=False):
        if vertical:
            start, end = [a['x']+a['width']/2,a['y']+a['height']+12], [b['x']+b['width']/2,b['y']-12]
            ap, bp = [.5,1], [.5,0]
        else:
            right = b['x'] >= a['x']
            start = [a['x']+(a['width']+12 if right else -12),a['y']+a['height']/2]
            end = [b['x']+(-12 if right else b['width']+12),b['y']+b['height']/2]
            ap, bp = ([1,.5],[0,.5]) if right else ([0,.5],[1,.5])
        points = None
        if routed:
            dx, dy = end[0]-start[0], end[1]-start[1]
            points = [[0,0],[0,dy/2],[dx,dy/2],[dx,dy]] if vertical else [[0,0],[dx/2,0],[dx/2,dy],[dx,dy]]
        e = self.line(*start,*end,dash=dash,arrow=True,points=points)
        for key, node, point in [('startBinding',a,ap),('endBinding',b,bp)]:
            e[key] = dict(elementId=node['id'], focus=0, gap=12,
                          fixedPoint=point, mode='orbit')
            node['boundElements'] = [*(node['boundElements'] or []), {'id':e['id'],'type':'arrow'}]
        if label:
            cx, cy = (start[0]+end[0])/2, (start[1]+end[1])/2-32
            if routed and not vertical:
                cx, cy = start[0]+(end[0]-start[0])*0.75, end[1]-30
            self.text(label, 0, 0, 24, center=(cx,cy))
        return e

    def actor(self, label, x, y, w=200, h=120):
        node = self.box('',x,y,w,h,fill=GREEN)
        self.box('',x+w/2-13,y+12,26,26,kind='ellipse',fill=PAPER)
        self.line(x+w/2,y+40,x+w/2,y+62)
        self.line(x+w/2-23,y+51,x+w/2+23,y+51)
        self.text(label,0,0,28,node,(x+w/2,y+h-28))
        return node

    def storage(self, label, x, y, w=240, h=130):
        group = f'{self.slug}-store-{len(self.elements)}'
        bottom = self.box('',x,y+h-38,w,38,kind='ellipse',fill=AMBER)
        node = self.box('',x,y+19,w,h-38,fill=AMBER)
        node['roundness'] = None  # The cylindrical silhouette supplies the rounded edge.
        top = self.box('',x,y,w,38,kind='ellipse',fill=AMBER)
        text = self.text(label,0,0,30,node,(x+w/2,y+h/2+8))
        for e in (bottom,node,top,text):e['groupIds']=[group]
        return node

    def record(self, title, rows, x, y, w=290, h=300):
        node = self.box('',x,y,w,h,fill=PAPER)
        self.box(title,x+10,y+10,w-20,65,fill=BLUE,size=30)
        step = (h-95)/len(rows)
        for i,value in enumerate(rows):
            yy=y+95+i*step
            self.text(value,x+20,yy,26)
            if i<len(rows)-1:self.line(x+15,yy+step-12,x+w-15,yy+step-12)
        return node

    def line_key(self, entries, y=765):
        for i,(style,head,label) in enumerate(entries):
            x=60+i*375
            self.line(x,y,x+70,y,style=style,arrow=head)
            self.text(label,x+90,y-16,24)

    def table(self, rows, x=40, y=190, width=1120, height=570):
        cols = len(rows[0])
        cw, rh = width/cols, height/len(rows)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.box(value, x+c*cw+3,y+r*rh+3,cw-6,rh-6,
                         fill=BLUE if r==0 or c==0 else PAPER,size=28)

    def footer(self, value='양식의 예시 문구를 실제 사실로 바꾸고, 출처·가정·미확인을 구분하세요.'):
        self.text(value,40,830,24)

    def data(self):
        return dict(type='excalidraw', version=2, source='diagram-explainer',
                    elements=self.elements, appState=dict(viewBackgroundColor=PAPER,
                    currentItemFontFamily=FONT,currentItemFontSize=30,zoom=dict(value=1)),files={})


TEMPLATES = [
 ('flow','조건 분기 순서도','순서와 조건을 읽습니다. 모든 분기에 조건과 결과를 적으세요.'),
 ('swimlane','역할별 흐름','행은 책임 주체입니다. 화살표가 행을 건너면 인계입니다.'),
 ('sequence','메시지 시퀀스','위에서 아래로 시간이 흐릅니다. 요청·응답을 별도로 표시하세요.'),
 ('state','상태 전이','상태 상자는 작업이 아닙니다. 전이 화살표에 사건과 조건을 적으세요.'),
 ('hierarchy','계층과 조직','선은 소속 관계입니다. 위계와 실행 순서를 혼동하지 마세요.'),
 ('mindmap','마인드맵','주제에서 범주를 펼칩니다. 가지는 원인이나 실행 순서를 뜻하지 않습니다.'),
 ('concept','개념 관계 지도','연결마다 관계를 동사로 적으세요. 소속과 의존을 구별하세요.'),
 ('architecture','시스템 경계 지도','실행 환경·책임 경계와 경계를 넘는 데이터를 표시하세요.'),
 ('dfd','데이터 흐름','외부 주체·처리·저장소를 구별하고 화살표에는 데이터명을 적으세요.'),
 ('er','데이터 관계','엔터티·키·관계 수를 표시하세요. 1:N은 호출 순서가 아닙니다.'),
 ('class','클래스 구조','이름·속성·동작을 나눕니다. 상속·구성·의존은 이름으로 구별하세요.'),
 ('network','네트워크 연결','선은 연결입니다. 실제 전송 순서·보안 보장은 별도로 설명하세요.'),
 ('cycle','반복 주기','주기의 시작·회귀 조건과 종료 조건을 적으세요.'),
 ('feedback','피드백 고리','변수가 변하는 방향과 지연을 표시하세요. 인과관계는 출처가 필요합니다.'),
 ('timeline','사건 타임라인','위치는 시간입니다. 날짜 미확인은 명시하고 순서만으로 인과를 단정하지 마세요.'),
 ('gantt','작업 기간','막대는 기간입니다. 선후 의존·마감·미확정 기간은 별도로 표시하세요.'),
 ('roadmap','목표별 로드맵','기간별 기대 결과를 표시하세요. 예시는 확정 일정이 아닙니다.'),
 ('beforeafter','전후 상태','같은 항목과 단위로 비교하고, 바뀐 값과 불변 조건을 분리하세요.'),
 ('comparison','기준별 비교표','같은 기준으로 비교합니다. 빈칸은 미확인이지 기능 없음이 아닙니다.'),
 ('raci','책임 배분표','R 수행·A 최종 책임·C 협의·I 공유. 미확인 책임자는 추정하지 마세요.'),
 ('matrix','두 축 우선순위','축의 정의와 단위를 먼저 적고, 배치의 근거를 남기세요.'),
 ('swot','SWOT','내부 강점·약점과 외부 기회·위협을 나누세요. 근거 없는 진단은 가정입니다.'),
 ('fishbone','원인 후보 분석','뼈대는 원인 후보입니다. 검증된 원인과 가설을 구별하세요.'),
 ('why','5 Why 탐색','연속 질문은 가설을 좁히는 도구입니다. 다섯 단계가 증명을 보장하지 않습니다.'),
 ('funnel','단계별 퍼널','정의된 대상 집합·기간·분모를 유지합니다. 숫자는 확인 후 채우세요.'),
 ('venn','겹치는 집합','겹침은 교집합입니다. 면적은 수량을 뜻하지 않는 개념도입니다.'),
 ('containment','중첩된 범위','안에 있다는 것은 포함 관계입니다. 화살표 순서와 구별하세요.'),
 ('sipoc','SIPOC','공급자 → 입력 → 처리 → 출력 → 고객. 각 경계에서 전달물을 적으세요.'),
 ('journey','사용자 여정','단계별 행동·접점·경험·문제를 표시하고 관찰과 가설을 구분하세요.'),
 ('blueprint','서비스 블루프린트','사용자·보이는 서비스·보이지 않는 운영을 나누고 가시성 경계를 표시하세요.'),
 ('canvas','비즈니스 모델 캔버스','가치·고객·실행·비용·수익의 관계를 검토합니다. 모든 칸이 사실은 아닙니다.'),
 ('lean','린 캔버스','문제·해결·지표·고객 가설을 분리하고 검증 상태를 남기세요.'),
 ('affinity','아이디어 묶기','유사성으로 묶습니다. 묶음 이름은 자료에서 도출하고 인과로 읽지 마세요.'),
 ('kanban','작업 상태 보드','열은 상태입니다. 담당자·완료 기준을 적고 이동은 실제 진행에 맞추세요.'),
 ('wireframe','화면 구성','화면 영역·정보 위계·다음 행동을 표현합니다. 구현 완료를 뜻하지 않습니다.'),
 ('opportunity','기회와 해결책 트리','목표 → 기회 → 해결책 → 검증. 각 연결의 근거를 확인하세요.'),
]


def build(slug, title, note):
    s = Scene(slug,title,note)
    if slug == 'flow':
        a=s.box('① 시작 상태',40,350,200,100,kind='ellipse',fill=GREEN)
        b=s.box('② 조건?',350,310,220,180,kind='diamond',fill=AMBER)
        c=s.box('③ 조건 충족\n실행',730,200,260,120)
        d=s.box('④ 조건 미충족\n대안 / 종료',730,540,260,120,fill=AMBER)
        s.arrow(a,b,'입력'); s.arrow(b,c,'예',routed=True); s.arrow(b,d,'아니오',dash=True,routed=True)
        s.text('조건은 실제 임계값으로 바꾸세요. 예: 재고 ≥ 요청 수량',40,700,28)
        s.line_key([('solid',True,'실행'),('dashed',True,'조건 미충족 경로')])
    elif slug == 'swimlane':
        for i, role in enumerate(['사용자','서비스','저장소']):
            s.box('',40,180+i*185,1120,180,fill=PAPER)
            s.text(role,60,245+i*185,30)
        a=s.box('① 요청',250,215); b=s.box('② 검증',570,400); c=s.box('③ 반영',890,585)
        s.arrow(a,b,'요청 전달'); s.arrow(b,c,'검증 통과')
        s.text('실패는 검증 단계에서 별도 경로로 표시',300,770,26)
    elif slug == 'sequence':
        for x, label in [(120,'사용자'),(470,'서비스'),(850,'저장소')]:
            s.box(label,x-80,180,200,80); s.line(x+20,280,x+20,730,dash=True)
        s.box('',479,322,22,385,fill=PAPER)
        s.box('',859,437,22,140,fill=PAPER)
        for x1,x2,y,text,dash in [(140,490,340,'① 요청',False),(490,870,450,'② 읽기 / 쓰기',False),(870,490,560,'③ 결과',True),(490,140,680,'④ 응답',True)]:
            s.line(x1,y,x2,y,arrow=True,dash=dash)
            s.text(text,min(x1,x2)+60,y-45,30)
        s.line_key([('solid',True,'요청'),('dashed',True,'반환 / 응답'),('dashed',False,'세로: 생명선')],y=785)
    elif slug == 'state':
        a=s.box('대기',90,220,240,110,kind='ellipse'); b=s.box('처리 중',470,220,240,110,kind='ellipse'); c=s.box('완료',850,220,240,110,kind='ellipse',fill=GREEN)
        d=s.box('실패',470,560,240,110,kind='ellipse',fill=AMBER)
        s.arrow(a,b,'시작 사건'); s.arrow(b,c,'성공'); s.arrow(b,d,'오류',vertical=True)
        s.line(470,615,210,615,arrow=True,label='재시도 조건')
        s.line(210,615,210,342,arrow=True)
    elif slug in ('hierarchy','opportunity'):
        root=s.box('상위 목표' if slug=='opportunity' else '상위 조직',460,180,280,100)
        for x,name in [(170,'기회 A' if slug=='opportunity' else '하위 A'),(770,'기회 B' if slug=='opportunity' else '하위 B')]:
            b=s.box(name,x,400,280,100)
            edge=s.arrow(root,b,'기여' if slug=='opportunity' else '소속',vertical=True,routed=True)
            if slug=='hierarchy':edge['endArrowhead']=None
            c=s.box('해결책 / 검증' if slug=='opportunity' else '담당 역할',x,640,280,100,fill=GREEN)
            edge=s.arrow(b,c,vertical=True)
            if slug=='hierarchy':edge['endArrowhead']=None
    elif slug in ('mindmap','concept'):
        root=s.box('중심 개념',460,370,260,130,kind='ellipse')
        for x,y,name in [(70,190,'범주 A'),(70,590,'범주 B'),(890,190,'범주 C'),(890,590,'범주 D')]:
            b=s.box(name,x,y,220,100,fill=GREEN if x<460 else AMBER)
            if slug=='mindmap':
                s.line(root['x']+(0 if x<460 else root['width']),435,
                       x+(220 if x<460 else 0),y+50)
            else: s.arrow(root,b,'관계 동사')
    elif slug == 'architecture':
        s.box('',320,180,820,530,fill=PAPER,dash=True)
        s.text('서비스 경계 · 실제 범위 확인',350,200,30)
        a=s.actor('외부 사용자',40,340)
        b=s.box('게이트웨이',380,340,260,120)
        c=s.box('처리 서비스',820,340,250,120)
        d=s.box('권한 검사',380,555,260,100,fill=GREEN)
        store=s.storage('저장소',825,555,240,130)
        s.arrow(a,b,'요청'); s.arrow(b,c,'전달'); s.arrow(b,d,'검증',vertical=True)
        s.arrow(c,store,'조회 / 기록',vertical=True)
        # Separate return route avoids the main request lane.
        s.line(820,352,640,352,arrow=True,dash=True,
               points=[[0,0],[0,-72],[-180,-72],[-180,0]])
        s.text('결과 반환',674,238,24)
        s.text('주석: 경계는 보안 보장과 별도로 검증',60,630,24)
        s.line(245,619,315,600,style='dotted')
        s.line_key([('solid',True,'요청 / 데이터'),('dashed',True,'결과 반환'),('dotted',False,'설명 주석')])
    elif slug == 'dfd':
        s.box('',320,180,820,540,fill=PAPER,dash=True)
        s.text('데이터 처리 범위',350,200,30)
        a=s.actor('외부 주체',40,390)
        b=s.box('① 처리',380,380,270,140,kind='ellipse')
        c=s.storage('D1 저장소',850,385,240,140)
        s.arrow(a,b,'입력 자료'); s.arrow(b,c,'저장 자료')
        s.text('프로세스는 처리 · 원통은 저장소',370,650,28)
        s.line_key([('solid',True,'데이터 이동'),('dashed',False,'시스템 경계')])
    elif slug == 'network':
        s.box('',310,180,830,540,fill=PAPER,dash=True)
        s.text('네트워크 범위',340,200,30)
        a=s.actor('외부 장치',40,390)
        b=s.box('라우터 / 게이트웨이',350,385,340,130)
        c=s.box('내부 노드 A',830,300,250,110)
        d=s.box('내부 노드 B',830,555,250,110,fill=GREEN)
        s.line(240,450,350,450)
        for node in (c,d):
            s.line(690,450,830,node['y']+55,
                   points=[[0,0],[65,0],[65,node['y']+55-450],[140,node['y']+55-450]])
        s.text('연결 ≠ 통신 순서 · 접근 권한은 별도 확인',80,675,28)
        s.line_key([('solid',False,'연결 관계'),('dashed',False,'네트워크 경계')])
    elif slug in ('er','class'):
        if slug=='er':
            nodes=[]
            for x,title,rows in [(40,'고객',['PK 고객 ID','이름','연락처']),
                                 (455,'주문',['PK 주문 ID','FK 고객 ID','일시']),
                                 (870,'품목',['PK 품목 ID','FK 주문 ID','수량'])]:
                nodes.append(s.record(title,rows,x,230))
            for a,b in zip(nodes,nodes[1:]):
                edge=s.arrow(a,b,'1 : N');edge['endArrowhead']=None
            s.text('PK: 기본 키     FK: 외래 키     연결선: 관계 수',80,655,30)
            s.text('키와 필수성·관계 수는 실제 데이터 모델로 확인',100,750,28)
        else:
            a=s.record('클래스 A',['속성: 이름 / 타입','동작: 메서드(인수)'],90,230,360,330)
            b=s.record('클래스 B',['속성: 이름 / 타입','동작: 메서드(인수)'],750,230,360,330)
            s.arrow(a,b,'의존',dash=True)
            s.text('A → B : 의존   /   A ◇ B : 집합   /   A ◆ B : 구성',80,670,30)
    elif slug in ('cycle','feedback'):
        a=s.box('계획' if slug=='cycle' else '변수 A',80,240,250,110)
        b=s.box('실행' if slug=='cycle' else '변수 B',820,240,250,110)
        c=s.box('관찰' if slug=='cycle' else '변수 C',820,620,250,110)
        d=s.box('수정' if slug=='cycle' else '변수 D',80,620,250,110)
        s.arrow(a,b,'다음 단계' if slug=='cycle' else '+ / −'); s.arrow(b,c,'관찰' if slug=='cycle' else '지연 / 부호',vertical=True)
        s.arrow(c,d,'회귀 조건' if slug=='cycle' else '+ / −'); s.line(205,610,205,362,arrow=True,label='반복 / 영향')
    elif slug == 'timeline':
        s.line(90,450,1090,450)
        for i in range(4):
            x=100+i*290; s.line(x,435,x,465); s.text(f'시점 {i+1}',x-35,490,32)
            s.box('사건 / 근거',x-60,245 if i%2==0 else 610,210,100)
    elif slug in ('gantt','roadmap'):
        s.table([['항목','기간 1','기간 2','기간 3'],['작업 A' if slug=='gantt' else '목표 A','','',''],['작업 B' if slug=='gantt' else '목표 B','','',''],['작업 C' if slug=='gantt' else '목표 C','','','']])
        for x,y,w,txt in [(345,350,490,'기간 / 기대 결과 A'),(630,493,490,'기간 / 기대 결과 B'),(345,635,760,'기간 / 기대 결과 C')]:
            s.box(txt,x,y,w,100,fill=GREEN,size=28)
    elif slug=='beforeafter':
        s.table([['항목','이전 상태','이후 상태'],['수량 / 단위','[값]','[값]'],['권한 / 책임','[주체]','[주체]'],['불변 조건','[조건]','[같은 조건]']])
    elif slug=='comparison':
        s.table([['기준','대안 A','대안 B'],['조건 / 범위','[사실]','[사실]'],['이점과 비용','[근거]','[근거]'],['제약 / 미확인','[제약]','[미확인]']])
    elif slug=='raci':
        s.table([['활동','역할 A','역할 B','역할 C'],['활동 1','R','A','C'],['활동 2','I','R / A','C'],['활동 3','[미확인]','[미확인]','[미확인]']])
    elif slug in ('matrix','swot'):
        names=['높은 영향 / 낮은 비용','높은 영향 / 높은 비용','낮은 영향 / 낮은 비용','낮은 영향 / 높은 비용'] if slug=='matrix' else ['강점 (내부)','약점 (내부)','기회 (외부)','위협 (외부)']
        for i,label in enumerate(names):
            s.box(label+'\n[항목과 근거]',80+(i%2)*540,210+(i//2)*270,500,240,fill=PAPER,size=32)
        if slug=='matrix': s.text('세로: 영향 ↑      가로: 비용 →',90,760,32)
    elif slug=='fishbone':
        s.line(100,460,900,460,arrow=True); s.box('문제 / 결과',920,400,230,120,fill=AMBER)
        for x in [230,500,770]:
            for y in [240,680]:
                s.line(x-80,y,x,460); s.text('원인 후보\n[근거 상태]',x-150,y-70 if y==240 else y,28)
    elif slug=='why':
        previous=None
        for i in range(5):
            b=s.box(f'질문 {i+1}\n이유 후보',40+i*230,350,200,150,fill=BLUE if i==0 else PAPER)
            if previous:s.arrow(previous,b)
            previous=b
        s.text('각 단계: 관찰 / 가설 / 반증 자료를 기록',180,650,32)
    elif slug=='funnel':
        for i,w in enumerate([1000,780,560,340]):
            y=190+i*145; x=(1200-w)/2
            e=s.element('line',x,y,w,120,points=[[0,0],[w,0],[w-70,120],[70,120],[0,0]],backgroundColor=BLUE)
            s.text(f'단계 {i+1}: [대상 수 / 전환율]',0,0,30,center=(600,y+60))
    elif slug=='venn':
        s.box('',190,230,500,480,kind='ellipse',fill='transparent')
        s.box('',500,230,500,480,kind='ellipse',fill='transparent')
        s.text('집합 A',300,380,36); s.text('공통\nA ∩ B',565,430,32); s.text('집합 B',800,380,36)
    elif slug=='containment':
        for x,y,w,h,label in [(60,180,1080,600,'전체 범위'),(220,300,760,430,'부분 범위'),(400,440,400,220,'핵심 범위')]:
            s.box('',x,y,w,h,fill=PAPER); s.text(label,x+30,y+20,32)
    elif slug=='sipoc':
        s.table([['공급자','입력','처리','출력','고객'],['[주체]','[전달물]','[활동]','[결과물]','[수신자]'],['[출처]','[요건]','[범위]','[품질 기준]','[필요]']])
    elif slug in ('journey','blueprint'):
        labels=['행동','접점','경험 / 근거','문제 / 개선'] if slug=='journey' else ['사용자 행동','보이는 서비스','가시성 경계','내부 운영']
        s.table([['단계','발견','이용','이후']]+[[name,'[내용]','[내용]','[내용]'] for name in labels])
    elif slug in ('canvas','lean'):
        names=['핵심 파트너','핵심 활동','가치 제안','고객 관계','고객군','핵심 자원','채널','비용 구조','수익원'] if slug=='canvas' else ['문제','해결책','고유 가치','강점','고객군','핵심 지표','채널','비용 구조','수익원']
        cells=[(40,180,215,410),(265,180,215,200),(490,180,215,410),
               (715,180,215,200),(940,180,215,410),(265,390,215,200),
               (715,390,215,200),(40,610,550,180),(610,610,550,180)]
        for label,(x,y,w,h) in zip(names,cells):
            s.box(label+'\n[가설 / 근거]',x,y,w,h,fill=PAPER,size=30)
    elif slug in ('affinity','kanban'):
        names=['묶음 A','묶음 B','묶음 C'] if slug=='affinity' else ['할 일','진행 중','완료']
        for i,name in enumerate(names):
            s.box('',40+i*380,180,350,600,fill=PAPER); s.text(name,80+i*380,210,36)
            for j in range(2):s.box('[아이디어]' if slug=='affinity' else '[작업 / 담당자]',65+i*380,320+j*200,300,155,fill=AMBER,size=28)
    elif slug=='wireframe':
        s.box('',100,165,1000,620,fill=PAPER); s.box('탐색 / 제목',130,190,940,90,fill=BLUE)
        s.box('핵심 정보',130,310,600,300,fill=PAPER); s.box('보조 정보',760,310,310,300,fill=PAPER)
        s.box('주요 행동',130,660,400,85,fill=GREEN); s.box('다음 행동',760,660,310,85,fill=PAPER)
    else: raise ValueError(slug)
    s.footer()
    ids={e['id'] for e in s.elements}
    assert len(ids)==len(s.elements)
    assert all(e['width']>=0 and e['height']>=0 for e in s.elements)
    for e in s.elements:
        if e['type']=='text':
            assert e['containerId'] is None or e['containerId'] in ids
        for key in ('startBinding','endBinding'):
            if e.get(key): assert e[key]['elementId'] in ids
    return s


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--template',choices=[t[0] for t in TEMPLATES])
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    items, index=[],[]
    for slug,title,note in TEMPLATES:
        if args.template and slug!=args.template: continue
        s=build(slug,title,note)
        path=args.output/f'{slug}.excalidraw'
        path.write_text(json.dumps(s.data(),ensure_ascii=False,indent=2))
        elements=json.loads(json.dumps(s.elements))
        for e in elements:e['groupIds']=[f'{slug}-template']
        items.append(dict(id=f'diagram-explainer-{slug}',status='unpublished',created=1791586800000,elements=elements))
        index.append(dict(id=slug,title=title,purpose=note,file=path.name))
    if not args.template:
        (args.output/'diagram-explainer.excalidrawlib').write_text(json.dumps(dict(type='excalidrawlib',version=2,source='diagram-explainer',libraryItems=items),ensure_ascii=False,indent=2))
        (args.output/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
    print(f'Created {len(items)} editable templates in {args.output}')


if __name__=='__main__':main()
