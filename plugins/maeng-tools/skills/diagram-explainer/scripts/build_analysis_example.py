#!/usr/bin/env python3
"""Build assets/example-analysis.html: the nine analysis charts of references/type-analysis.md.

Sample data is deterministic (formulas, no randomness). Every statistic the page labels is computed from the
plotted data and asserted, so the example obeys its own honest-data rules:

    python3 scripts/build_analysis_example.py          # write the example
    python3 scripts/build_analysis_example.py --check  # rebuild, assert, compare with the committed file
"""
import argparse
import math
import sys
from pathlib import Path
from statistics import NormalDist, mean

OUT = Path(__file__).resolve().parent.parent / 'assets' / 'example-analysis.html'
W, H = 320, 200


def f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def scale(d0, d1, r0, r1):
    return lambda v: r0 + (v - d0) * (r1 - r0) / (d1 - d0)


def svg(slug, title, desc, body, h=H):
    return (f'<svg viewBox="0 0 {W} {h}" role="img" aria-labelledby="{slug}-t {slug}-d">'
            f'<title id="{slug}-t">{title}</title><desc id="{slug}-d">{desc}</desc>{body}</svg>')


def text(x, y, s, cls='t', anchor='start'):
    return f'<text class="{cls}" x="{f(x)}" y="{f(y)}" text-anchor="{anchor}">{s}</text>'


def line(x1, y1, x2, y2, cls):
    return f'<line class="{cls}" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}"/>'


def poly(points, cls):
    return f'<polyline class="{cls}" points="{" ".join(f"{f(x)},{f(y)}" for x, y in points)}"/>'


# 1. Cohort retention: repurchase rate (%) by first-purchase month, months since first purchase.
def cohort():
    months = ['5월', '6월', '7월', '8월', '9월', '10월']
    sizes = [820, 760, 905, 870, 1040, 980]
    base = [36, 34, 35, 37, 45, 0]
    rows = [[100] + [round(b * 0.74 ** k) for k in range(len(months) - 1 - i)] for i, b in enumerate(base)]
    assert all(len(r) == len(months) - i and r[0] == 100 for i, r in enumerate(rows)), 'cohort triangle; unreached cells stay empty'
    focal = (4, 1)  # 9월 cohort, month +1
    rest = [v for i, r in enumerate(rows) for j, v in enumerate(r) if j and (i, j) != focal]
    hi = max(rest)
    body = [text(64 + j * 42 + 20, 16, f'+{j}', anchor='middle') for j in range(len(months))]
    for i, r in enumerate(rows):
        y = 24 + i * 26
        body.append(text(32, y + 16, months[i], 't-ink' if i == focal[0] else 't', 'end'))
        body.append(text(60, y + 16, f'{sizes[i]:,}', 't-s', 'end'))
        for j, v in enumerate(r):
            x = 64 + j * 42
            if j == 0:
                body.append(f'<rect class="cell0" x="{x}" y="{y}" width="40" height="24"/>')
                body.append(text(x + 20, y + 16, v, 't-ink', 'middle'))
            elif (i, j) == focal:
                body.append(f'<rect class="cell-acc" data-focal="true" x="{x}" y="{y}" width="40" height="24"/>')
                body.append(text(x + 20, y + 16, v, 't-inv', 'middle'))
            else:
                op = 0.08 + 0.55 * v / hi
                body.append(f'<rect class="cell" style="fill-opacity:{op:.2f}" x="{x}" y="{y}" width="40" height="24"/>')
                body.append(text(x + 20, y + 16, v, 't-inv' if op >= 0.4 else 't-ink', 'middle'))
    return svg('cohort', '코호트 리텐션: 첫 구매 월별 재구매율',
               '가입 월별 행, 경과 개월 열의 삼각형 표. 9월 코호트의 1개월 차 재구매율이 45%로 가장 높다.', ''.join(body))


# 2. Small multiples: 12 campaigns, 12-week ROAS, one shared scale.
def small_multiples():
    series = []
    for c in range(12):
        trend = -0.12 if c == 7 else 0.01 * (c % 3)
        series.append([2.6 + 0.35 * math.sin(w * 0.9 + c) + trend * w for w in range(12)])
    lo, hi = 0.0, 4.0
    assert all(lo <= v <= hi for s in series for v in s), 'shared scale covers every panel'
    body = []
    for c, s in enumerate(series):
        px, py = 4 + (c % 4) * 80, 6 + (c // 4) * 62
        sx, sy = scale(0, 11, px + 6, px + 70), scale(lo, hi, py + 52, py + 14)
        focal = c == 7
        body.append(f'<rect class="{"panel-acc" if focal else "panel"}" x="{px}" y="{py}" width="76" height="56" rx="4"/>')
        body.append(line(px + 6, sy(1), px + 70, sy(1), 'ref'))  # ROAS 1× = break-even
        body.append(text(px + 6, py + 11, f'C{c + 1:02d}', 't-acc' if focal else 't-s'))
        body.append(text(px + 70, py + 11, f'{s[-1]:.1f}', 't-acc' if focal else 't-s', 'end'))
        body.append(poly([(sx(w), sy(v)) for w, v in enumerate(s)], 'ln-acc' if focal else 'ln'))
    return svg('multiples', '스몰 멀티플: 캠페인 12개의 12주 ROAS',
               '같은 축(ROAS 0–4배)을 쓰는 작은 선 그래프 12개. C08만 꾸준히 떨어진다.', ''.join(body), h=192)


# 3. Control chart (individuals/XmR): daily conversion rate (%), limits = mean ± 3σ, σ from the mean moving range.
def control():
    xs = [3.0 + 0.18 * math.sin(d * 1.7) + 0.12 * math.cos(d * 0.6) for d in range(30)]
    xs[24] = 2.05
    center = mean(xs)
    sigma = mean(abs(b - a) for a, b in zip(xs, xs[1:])) / 1.128
    ucl, lcl = center + 3 * sigma, center - 3 * sigma
    out = [d for d, v in enumerate(xs) if v > ucl or v < lcl]
    assert out == [24], f'flagged points must be exactly those outside ±3σ, got {out}'
    sx, sy = scale(0, 29, 36, 280), scale(1.8, 4.2, 176, 16)
    body = [line(36, sy(v), 280, sy(v), 'grid') for v in (2, 3, 4)]
    body += [text(30, sy(v) + 3, v, 't', 'end') for v in (2, 3, 4)]
    body += [line(36, sy(ucl), 280, sy(ucl), 'lim'), line(36, sy(lcl), 280, sy(lcl), 'lim'),
             line(36, sy(center), 280, sy(center), 'ref-solid'),
             text(284, sy(ucl) + 3, '+3σ', 't-acc'), text(284, sy(lcl) + 3, '−3σ', 't-acc'),
             text(284, sy(center) + 3, '평균', 't')]
    body.append(poly([(sx(d), sy(v)) for d, v in enumerate(xs)], 'ln-thin'))
    body += [f'<circle class="{"dot-acc" if d in out else "dot"}" cx="{f(sx(d))}" cy="{f(sy(v))}" r="{3.5 if d in out else 2}"/>'
             for d, v in enumerate(xs)]
    body += [text(sx(0), 192, '1일'), text(sx(14), 192, '15일', anchor='middle'), text(sx(29), 192, '30일', anchor='end')]
    return svg('control', f'관리도: 일 전환율, 평균 {center:.1f}% ± 3σ',
               f'30일 전환율의 개별값 관리도. 평균 {center:.2f}%, 관리 한계 {lcl:.2f}–{ucl:.2f}%. 25일만 한계를 벗어났다.',
               ''.join(body)), (center, lcl, ucl)


# 4. Forest plot: A/B test lift (%) with 95% intervals (estimate ± 1.96·SE).
def forest():
    tests = [('무료배송 문구', 7.5, 3.2), ('리뷰 위로', 2.4, 2.6), ('가격 강조', -1.2, 2.4),
             ('영상 썸네일', 12.8, 3.6), ('CTA 색', 0.6, 2.2), ('쿠폰 팝업', -3.4, 2.7)]
    z = NormalDist().inv_cdf(0.975)
    rows = [(n, e, e - z * se, e + z * se) for n, e, se in tests]
    assert all(lo < e < hi for _, e, lo, hi in rows), 'interval contains its estimate'
    lo_ax, hi_ax = -12, 24
    assert all(lo_ax <= lo and hi <= hi_ax for _, _, lo, hi in rows), 'axis covers every interval'
    focal = max(rows, key=lambda r: r[1])
    assert focal[2] > 0, 'the highlighted test excludes zero'
    sx = scale(lo_ax, hi_ax, 108, 308)
    body = [line(sx(0), 10, sx(0), 168, 'ax')]
    body += [text(sx(v), 182, ('+' if v > 0 else '') + str(v), anchor='middle') for v in (-10, 0, 10, 20)]
    for i, (n, e, lo, hi) in enumerate(rows):
        y = 22 + i * 26
        acc, sig = (n, e, lo, hi) == focal, lo > 0 or hi < 0
        cls = 'acc' if acc else ('ink' if sig else 'soft')
        body.append(text(100, y + 3, n, 't-ink' if acc else 't', 'end'))
        body.append(line(sx(lo), y, sx(hi), y, f'ci-{cls}'))
        body.append(f'<rect class="sq-{cls}" x="{f(sx(e) - 4)}" y="{y - 4}" width="8" height="8"/>')
    body += [text(sx(0) - 4, 196, '← 대조군 우세', 't', 'end'), text(sx(0) + 4, 196, '실험군 우세 →')]
    return svg('forest', 'A/B 테스트 효과와 95% 구간',
               '테스트 6개의 효과 추정치와 95% 신뢰구간. 영상 썸네일만 구간 전체가 0보다 크고 효과가 가장 크다.',
               ''.join(body))


# 5. Fan chart: monthly revenue (억원), months 1–9 actual, 10–12 forecast with 50/80/95% bands of the forecast.
def fan():
    actual = [3.9, 4.0, 4.2, 4.6, 4.4, 4.7, 4.9, 5.0, 4.9]
    median = [actual[-1] + 0.15 * h for h in range(4)]
    sd = [0.32 * math.sqrt(h) for h in range(4)]
    levels = (0.95, 0.8, 0.5)
    bands = {p: [(m - NormalDist().inv_cdf(0.5 + p / 2) * s, m + NormalDist().inv_cdf(0.5 + p / 2) * s)
                 for m, s in zip(median, sd)] for p in levels}
    for h in range(4):
        inner = [bands[p][h] for p in reversed(levels)]
        assert all(o[0] <= i[0] <= median[h] <= i[1] <= o[1] for i, o in zip(inner, inner[1:])), 'bands nest'
    assert all(bands[0.95][h + 1][1] - bands[0.95][h + 1][0] >= bands[0.95][h][1] - bands[0.95][h][0] for h in range(3))
    sx, sy = scale(1, 12, 36, 270), scale(3, 7, 176, 16)
    body = [line(36, sy(v), 270, sy(v), 'grid') for v in (3, 5, 7)] + [text(30, sy(v) + 3, v, 't', 'end') for v in (3, 5, 7)]
    for p, cls in zip(levels, ('band95', 'band80', 'band50')):
        upper = [(sx(9 + h), sy(b[1])) for h, b in enumerate(bands[p])]
        lower = [(sx(9 + h), sy(b[0])) for h, b in reversed(list(enumerate(bands[p])))]
        body.append(f'<polygon class="{cls}" points="{" ".join(f"{f(x)},{f(y)}" for x, y in upper + lower)}"/>')
    body.append(poly([(sx(m + 1), sy(v)) for m, v in enumerate(actual)], 'ln'))
    body.append(poly([(sx(9 + h), sy(v)) for h, v in enumerate(median)], 'ln-acc-dash'))
    body += [text(sx(m), 192, f'{m}월', anchor='middle') for m in (1, 5, 9, 12)]
    body += [line(sx(9), 20, sx(9), 176, 'ref'), text(sx(9) - 4, 28, '예측 시작', 't', 'end'),
             text(sx(12) + 4, sy(bands[0.95][3][1]) + 3, '95%', 't-acc'),
             text(sx(12) + 4, sy(median[3]) + 3, '중앙값', 't-ink')]
    return svg('fan', '팬 차트: 월 매출과 3개월 예측',
               '1–9월 실적 선과 10–12월 예측 중앙값, 예측 분포의 50·80·95% 구간 띠. 멀리 갈수록 띠가 넓어진다.',
               ''.join(body))


# 6. Survival curve (Kaplan–Meier): share of monthly-plan subscribers still active, trial vs direct signup, 12 months.
# Both groups are on the same monthly plan: an annual plan can only churn at renewal, which a monthly curve would misdraw.
def km(times):
    """times: list of (month, event). Returns steps [(t, S, lo, hi)] with a Greenwood 95% band, and censor marks."""
    z = NormalDist().inv_cdf(0.975)
    s, var_sum, steps, marks = 1.0, 0.0, [(0, 1.0, 1.0, 1.0)], []
    for t in sorted({t for t, _ in times}):
        at_risk = sum(1 for u, _ in times if u >= t)
        events = sum(1 for u, e in times if u == t and e)
        if events:
            s *= 1 - events / at_risk
            var_sum += events / (at_risk * (at_risk - events)) if at_risk > events else 0
            half = z * s * math.sqrt(var_sum)
            steps.append((t, s, max(0.0, s - half), min(1.0, s + half)))
        if any(u == t and not e for u, e in times):
            marks.append((t, s))
    return steps, marks


def cohort_times(median_months, n=40):
    lam = math.log(2) / median_months
    out = []
    for i in range(n):
        t = -math.log(1 - (i + 0.5) / n) / lam
        censored = i % 7 == 3 and t < 12
        out.append((min(12, max(1, round(t))), not censored and t < 12))
    return out


def survival():
    groups = [('바로 결제', cohort_times(5), 'acc'), ('체험 경유', cohort_times(26), 'ink')]
    sx, sy = scale(0, 12, 64, 300), scale(0, 1, 128, 16)
    body = [line(64, sy(v), 300, sy(v), 'grid') for v in (0, 0.5, 1)]
    body += [text(58, sy(v) + 3, int(v * 100), 't', 'end') for v in (0, 0.5, 1)]
    medians = {}
    for name, times, cls in groups:
        steps, marks = km(times)
        assert all(b[1] <= a[1] and b[2] <= b[1] <= b[3] for a, b in zip(steps, steps[1:])), 'KM never rises; band holds S'
        med = next((t for t, s, _, _ in steps if s <= 0.5), None)
        medians[name] = med
        if cls == 'acc':  # 95% band for the focal group only
            pts = [(0, 1.0, 1.0)] + [(t, lo, hi) for t, _, lo, hi in steps[1:]]
            up, dn = [], []
            for (t, lo, hi), nxt in zip(pts, pts[1:] + [(12, None, None)]):
                up += [(sx(t), sy(hi)), (sx(nxt[0]), sy(hi))]
                dn += [(sx(t), sy(lo)), (sx(nxt[0]), sy(lo))]
            body.append(f'<polygon class="band95" points="{" ".join(f"{f(x)},{f(y)}" for x, y in up + dn[::-1])}"/>')
        d = f'M{f(sx(0))},{f(sy(1))}'
        for t, s, _, _ in steps[1:]:
            d += f' H{f(sx(t))} V{f(sy(s))}'
        d += f' H{f(sx(12))}'
        body.append(f'<path class="km-{cls}" d="{d}"/>')
        body += [line(sx(t), sy(s) - 4, sx(t), sy(s) + 4, f'tick-{cls}') for t, s in marks]
        for t in (0, 6, 12):
            body.append(text(sx(t), 174 + (0 if cls == 'acc' else 14), sum(1 for u, _ in times if u >= t), f't-{cls}', 'middle'))
    assert medians['바로 결제'] is not None and medians['체험 경유'] is None, 'focal median inside 12 months, the other not reached'
    m = medians['바로 결제']
    body += [line(64, sy(0.5), sx(m), sy(0.5), 'ref'), line(sx(m), sy(0.5), sx(m), 128, 'ref'),
             text(sx(m) + 4, 124, f'중앙 {m}개월', 't-acc'), text(298, sy(0.62), '중앙값 미도달', 't-ink', 'end'),
             text(4, 174, '바로 결제', 't-acc'), text(4, 188, '체험 경유', 't-ink'), text(4, 160, '남은 인원', 't')]
    body += [text(sx(t), 141, f'{t}개월' if t else '0', anchor='middle') for t in (0, 6, 12)]
    return svg('survival', '생존 곡선: 월간 요금제 유지 비율, 바로 결제 대 체험 경유',
               f'Kaplan–Meier 계단 곡선 두 개. 바로 결제한 사람은 {m}개월에 절반이 이탈하고, 체험을 거친 사람은 12개월까지 절반 넘게 남는다. 옅은 띠는 95% 구간, 짧은 세로선은 중도 절단.',
               ''.join(body)), m


# 7. Contribution decomposition: weekly revenue contribution by channel, baseline at the bottom, fixed order.
def contribution():
    names = ('기본', '검색', 'PMax', '메타')
    weeks = []
    for w in range(16):
        weeks.append((40 + w % 3, 12 + 2 * math.sin(w / 2), 14 + 0.6 * w, 8 + 2 * math.cos(w / 3)))
    assert all(min(wk) >= 0 for wk in weeks), 'non-negative decomposition in this example'
    totals = [sum(wk) for wk in weeks]
    actual = [t + 3 * math.sin(w * 1.3) for w, t in enumerate(totals)]  # observed revenue; the stack is the model fit
    sx, sy = scale(0, 16, 36, 308), scale(0, 100, 176, 16)
    body = [line(36, sy(v), 308, sy(v), 'grid') for v in (0, 50, 100)] + [text(30, sy(v) + 3, v, 't', 'end') for v in (0, 50, 100)]
    for w, wk in enumerate(weeks):
        top = 0.0
        for part, cls in zip(wk, ('base', 'c2', 'acc', 'c4')):
            body.append(f'<rect class="seg-{cls}" x="{f(sx(w) + 2)}" y="{f(sy(top + part))}" width="13" height="{f(sy(top) - sy(top + part))}"/>')
            top += part
        assert abs(top - totals[w]) < 1e-9, 'stacked top equals the modelled total'
    body += [f'<circle class="dot-halo" cx="{f(sx(w) + 8.5)}" cy="{f(sy(v))}" r="2.5"/>' for w, v in enumerate(actual)]
    body += [text(sx(0) + 2, 192, '1주'), text(sx(16), 192, '16주', anchor='end')]
    return svg('contribution', '기여도 분해: 주별 매출의 모델 추정 기여',
               '16주 매출을 기본·검색·PMax·메타로 쌓은 모델 추정 막대와 실제 매출 점. 기본이 맨 아래에 고정되고 PMax 기여가 꾸준히 커진다.',
               ''.join(body)), names


# 8. Lift chart: response rate per predicted-score decile ÷ overall rate (per decile, not cumulative).
def lift():
    n = 1000
    rates = [0.03 * 2.9 * 0.72 ** d + 0.006 for d in range(10)]
    responders = [round(r * n) for r in rates]
    overall = sum(responders) / (10 * n)
    lifts = [r / n / overall for r in responders]
    assert abs(mean(lifts) - 1) < 1e-9, 'equal-size deciles average to 1×'
    sx, sy = scale(0, 10, 36, 308), scale(0, 4, 176, 16)
    body = [line(36, sy(v), 308, sy(v), 'grid') for v in (0, 1, 2, 3, 4)] + [text(30, sy(v) + 3, v, 't', 'end') for v in (0, 2, 4)]
    for d, l in enumerate(lifts):
        cls = 'acc' if d == 0 else ('ink' if l > 1 else 'base')
        body.append(f'<rect class="seg-{cls}" x="{f(sx(d) + 3)}" y="{f(sy(l))}" width="21" height="{f(sy(0) - sy(l))}"/>')
    body += [line(36, sy(1), 308, sy(1), 'ref'), text(306, sy(1) - 4, '평균 1배', 't', 'end'),
             text(sx(0) + 13, sy(lifts[0]) - 4, f'{lifts[0]:.1f}배', 't-acc', 'middle'),
             text(sx(0) + 3, 192, '상위 10%'), text(sx(10) - 3, 192, '하위', anchor='end')]
    return svg('lift', '리프트 차트: 예측 점수 10분위별 리프트',
               f'점수 상위 10%부터 하위 10%까지 10분위 막대. 상위 10%의 반응률이 평균의 {lifts[0]:.1f}배이고 점선은 평균 1배.',
               ''.join(body)), lifts[0]


# 9. ROC curve: lead-scoring model; AUC by trapezoid, cross-checked against the Mann–Whitney probability.
def roc():
    nd = NormalDist()
    k = 60
    neg = [nd.inv_cdf((i + 0.5) / k) for i in range(k)]
    pos = [nd.inv_cdf((i + 0.5) / k) + 1.3 for i in range(k)]
    pts = [(0.0, 0.0)]
    for th in sorted(set(neg + pos), reverse=True):
        pts.append((sum(s >= th for s in neg) / k, sum(s >= th for s in pos) / k))
    assert pts[-1] == (1.0, 1.0)
    auc = sum((x2 - x1) * (y1 + y2) / 2 for (x1, y1), (x2, y2) in zip(pts, pts[1:]))
    mw = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (k * k)
    assert abs(auc - mw) < 1e-9, 'trapezoid AUC equals the Mann–Whitney probability'
    sx, sy = scale(0, 1, 92, 252), scale(0, 1, 176, 16)
    area = [(sx(x), sy(y)) for x, y in pts] + [(sx(1), sy(0))]
    body = [f'<rect class="frame" x="92" y="16" width="160" height="160"/>',
            f'<polygon class="band95" points="{" ".join(f"{f(x)},{f(y)}" for x, y in area)}"/>',
            line(sx(0), sy(0), sx(1), sy(1), 'ref'), poly([(sx(x), sy(y)) for x, y in pts], 'ln-acc'),
            text(sx(0.55), sy(0.35), f'AUC {auc:.2f}', 't-ink', 'middle'),
            text(sx(0.62), sy(0.56), '무작위 0.5', 't', 'start'),
            text(86, sy(1) + 3, '1', 't', 'end'), text(86, sy(0) + 3, '0', 't', 'end'),
            text(sx(1), 192, '거짓 양성 비율 →', anchor='end'), text(sx(0), 192, '0'),
            text(258, sy(1) + 8, '참 양성', 't'), text(258, sy(1) + 20, '비율', 't')]
    return svg('roc', 'ROC 커브: 리드 스코어링 모델',
               f'검증 데이터 {2 * k}명(양성 {k})에서 그린 거짓 양성 비율 대비 참 양성 비율 계단 곡선과 대각선(무작위). 곡선 아래 넓이 AUC {auc:.2f}.',
               ''.join(body)), (auc, k)


CSS = '''@font-face { font-family: 'Diagram Nunito Sans'; src: local('NunitoSans-Regular'); font-weight: 400; }
@font-face { font-family: 'Diagram Nunito Sans'; src: local('NunitoSans-Bold'); font-weight: 700; }
@font-face { font-family: 'Diagram LINE Seed Sans KR'; src: local('LINESeedSansKR-Regular'); font-weight: 400; }
@font-face { font-family: 'Diagram LINE Seed Sans KR'; src: local('LINESeedSansKR-Bold'); font-weight: 700; }
:root { --paper: #f5f5f5; --paper-2: #ececec; --ink: #2d3142; --muted: #4f5d75; --soft: #5a6580;
  --rule: rgba(45,49,66,0.12); --rule-solid: #bfc0c0; --accent: #bf4520; --accent-tint: rgba(191,69,32,0.08);
  --font: 'Diagram Nunito Sans', 'Diagram LINE Seed Sans KR', system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --paper: #2d3142; --paper-2: #393e53;
  --ink: #f5f5f5; --muted: #bfc0c0; --soft: #949eb2; --rule: rgba(245,245,245,0.12); --rule-solid: rgba(191,192,192,0.25);
  --accent: #f08a59; --accent-tint: rgba(240,138,89,0.10); color-scheme: dark; } }
:root[data-theme="dark"] { --paper: #2d3142; --paper-2: #393e53; --ink: #f5f5f5; --muted: #bfc0c0; --soft: #949eb2;
  --rule: rgba(245,245,245,0.12); --rule-solid: rgba(191,192,192,0.25); --accent: #f08a59;
  --accent-tint: rgba(240,138,89,0.10); color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--font); line-height: 1.6;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.wrap { max-width: 1080px; margin: 0 auto; padding-block: 40px 56px; display: grid; gap: 24px; }
.eyebrow { font-size: 13px; letter-spacing: 0.06em; color: var(--muted); margin: 0; }
h1 { font-size: clamp(24px, 3.4vw, 34px); line-height: 1.25; margin: 0; word-break: keep-all; text-wrap: balance; }
.lede { margin: 0; color: var(--muted); max-width: 44rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
figure { margin: 0; padding: 16px; border: 1px solid var(--rule-solid); border-radius: 8px; display: grid; gap: 8px; min-width: 0; }
figure h2 { margin: 0; font-size: 18px; line-height: 1.3; }
figure h2 span { color: var(--accent); margin-right: 6px; font-variant-numeric: tabular-nums; }
.metric { margin: 0; font-size: 13px; color: var(--muted); }
.legend { margin: 0; font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 12px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
.k-base { background: var(--rule-solid); } .k-c2 { background: var(--soft); } .k-acc { background: var(--accent); } .k-c4 { background: var(--ink); }
figure svg { width: 100%; height: auto; display: block; }
figcaption { font-size: 13px; color: var(--ink); }
.foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; border-top: 1px solid var(--rule); padding-top: 8px; }
.when { font-size: 14px; font-weight: 700; }
.lv { font-size: 12px; padding: 1px 8px; border-radius: 4px; white-space: nowrap; }
.lv-mid { border: 1px solid var(--rule-solid); color: var(--muted); }
.lv-adv { background: var(--ink); color: var(--paper); }
.note { margin: 0; font-size: 13px; color: var(--muted); }
svg text { font-family: var(--font); font-size: 10px; }
.t { fill: var(--muted); } .t-s { fill: var(--soft); font-size: 9px; } .t-ink { fill: var(--ink); }
.t-acc { fill: var(--accent); font-weight: 700; } .t-inv { fill: var(--paper); }
line.grid { stroke: var(--rule); stroke-width: 1; }
.ax { stroke: var(--ink); stroke-width: 1; } .frame { fill: none; stroke: var(--rule-solid); stroke-width: 1; }
.ref { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.ref-solid { stroke: var(--ink); stroke-width: 1; }
.lim { stroke: var(--accent); stroke-width: 1; stroke-dasharray: 4 3; }
.ln { fill: none; stroke: var(--ink); stroke-width: 1.5; } .ln-thin { fill: none; stroke: var(--soft); stroke-width: 1; }
.ln-acc { fill: none; stroke: var(--accent); stroke-width: 2; }
.ln-acc-dash { fill: none; stroke: var(--accent); stroke-width: 2; stroke-dasharray: 5 3; }
.dot { fill: var(--ink); } .dot-acc { fill: var(--accent); } .dot-halo { fill: var(--ink); stroke: var(--paper); stroke-width: 1.5; }
.k-dot { border-radius: 50%; width: 8px; height: 8px; background: var(--ink); }
.cell0 { fill: var(--paper-2); } .cell { fill: var(--ink); } .cell-acc { fill: var(--accent); stroke: var(--accent); stroke-width: 1.2; }
.panel { fill: var(--paper-2); } .panel-acc { fill: var(--accent-tint); stroke: var(--accent); stroke-width: 1; }
.band95 { fill: var(--accent); fill-opacity: 0.12; } .band80 { fill: var(--accent); fill-opacity: 0.2; } .band50 { fill: var(--accent); fill-opacity: 0.32; }
.ci-acc, .ci-ink, .ci-soft { stroke-width: 1.5; } .ci-acc { stroke: var(--accent); } .ci-ink { stroke: var(--ink); } .ci-soft { stroke: var(--soft); }
.sq-acc { fill: var(--accent); } .sq-ink { fill: var(--ink); } .sq-soft { fill: var(--soft); }
.km-acc, .km-ink { fill: none; stroke-width: 2; } .km-acc { stroke: var(--accent); } .km-ink { stroke: var(--ink); }
.tick-acc { stroke: var(--accent); stroke-width: 1; } .tick-ink { stroke: var(--ink); stroke-width: 1; }
.seg-base { fill: var(--rule-solid); } .seg-c2 { fill: var(--soft); } .seg-acc { fill: var(--accent); } .seg-c4 { fill: var(--ink); } .seg-ink { fill: var(--ink); }'''


def card(no, title, metric, chart, caption, when, level, legend=''):
    lv = '<span class="lv lv-adv">심화</span>' if level == 'advanced' else '<span class="lv lv-mid">중급</span>'
    return (f'<figure id="chart-{no}"><h2><span>{no:02d}</span>{title}</h2><p class="metric">{metric}</p>{legend}{chart}'
            f'<figcaption><b>읽는 법</b> {caption}</figcaption><div class="foot"><span class="when">{when}</span>{lv}</div></figure>')


def build():
    c3, (center, lcl, ucl) = control()
    c6, med = survival()
    c7, names = contribution()
    c8, top = lift()
    c9, (auc, k) = roc()
    order = tuple(zip(names, ('base', 'c2', 'acc', 'c4')))[::-1]  # legend lists the stack top-down
    legend = ('<p class="legend">' + ''.join(f'<span><i class="k-{c}"></i>{n}</span>' for n, c in order)
              + '<span><i class="k-dot"></i>실제 매출</span></p>')
    cards = [
        card(1, '코호트 리텐션', '그 달에 재구매한 비율(%) · 행은 첫 구매 월과 인원, 10월 말 기준', cohort(),
             '한 행이 한 코호트예요. 같은 열(같은 경과 개월)끼리 위아래로 비교해요. 빈칸은 0%가 아니라 아직 그 시점이 오지 않은 거예요.', '가입 시점별 잔존', 'intermediate'),
        card(2, '스몰 멀티플', '캠페인 12개 · 12주 ROAS, 모든 칸 같은 축(0–4배), 번호순 정렬', small_multiples(),
             '칸마다 축이 같아서 높이를 바로 비교할 수 있어요. 점선은 손익분기(1배), 오른쪽 위 숫자는 마지막 주 값이에요.', '세그먼트가 많을 때', 'intermediate'),
        card(3, '관리도', f'일 전환율(%) · 평균 {center:.1f}% ± 3σ, 개별값 관리도(σ는 이동범위로 추정)', c3,
             '점선은 목표가 아니라 이 과정이 평소 흔들리는 폭이에요. 밖으로 나간 점(주황)은 원인을 찾아볼 신호이지, 원인의 증거는 아니에요.', '이상 변동 감지', 'advanced'),
        card(4, '포레스트 플롯', 'A/B 테스트 효과(%) · 네모는 추정치, 선은 95% 신뢰구간', forest(),
             '선이 0을 가로지르면 효과가 없다는 게 아니라 아직 판단할 수 없다는 뜻이에요. 테스트가 많으면 우연히 하나쯤 유의하게 나올 수 있어요.', '실험 효과 한눈에', 'advanced'),
        card(5, '팬 차트', '월 매출(억원) · 3개월 예측, 띠는 예측 분포의 50·80·95% 구간', fan(),
             '띠는 최솟값과 최댓값이 아니라 확률이에요. 실제 값이 95% 띠 밖에 떨어질 확률이 약 5%이고, 모델이 가정한 조건이 바뀌면 띠도 틀려요.', '예측과 불확실성', 'intermediate'),
        card(6, '생존 곡선', '월간 요금제 유지 비율(%) · Kaplan–Meier, 11월 1일 기준, 아래는 남은 인원', c6,
             f'계단이 내려갈 때마다 누군가 이탈했어요. 짧은 세로선은 이탈이 아니라 아직 구독 중인 사람이에요. 50% 선과 만나는 곳이 중앙 생존 시간이에요(바로 결제 {med}개월).', '이탈까지 걸린 시간', 'intermediate'),
        card(7, '기여도 분해', '주별 매출의 모델(MMM) 추정 기여 · 기본을 맨 아래에 고정', c7,
             '조각은 측정값이 아니라 모델이 나눠 준 몫이에요. 두꺼운 조각이 효율 좋은 채널이라는 뜻은 아니니 지출과 함께 보세요.', '채널별 기여', 'advanced', legend),
        card(8, '리프트 차트', '예측 점수 10분위별 리프트(배) · 분위별, 누적 아님, 분위당 1,000명', c8,
             f'상위 10%의 반응률이 평균의 {top:.1f}배라는 뜻이지, 매출이 {top:.1f}배라는 뜻은 아니에요. 점선(1배)보다 높은 막대만 무작위보다 나아요.', '상위 N%의 성과', 'intermediate'),
        card(9, 'ROC 커브', f'리드 스코어링 모델 · 검증 데이터 {2 * k}명(양성 {k}) · AUC {auc:.2f}', c9,
             f'AUC {auc:.2f}는 정확도가 아니라, 양성 하나와 음성 하나를 뽑았을 때 양성에 더 높은 점수를 줄 확률이에요. 대각선은 무작위(0.5)예요.', '분류 모델 성능', 'intermediate'),
    ]
    return ('<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<title>분석 차트 9종</title>\n<style>\n' + CSS + '\n</style>\n</head>\n<body>\n<div class="wrap">\n'
            '<p class="eyebrow">Analysis charts · Diagram Design</p>\n<h1>분석 차트 9종: 언제 무엇을 쓰나</h1>\n'
            '<p class="lede">코호트부터 ROC까지, 데이터 질문마다 맞는 차트 하나. 예시 데이터이며 실제 성과가 아니에요.</p>\n'
            '<div class="cards">\n' + '\n'.join(cards) + '\n</div>\n'
            '<p class="note">예시 데이터 · 표기한 통계(±3σ, 95% 구간, 중앙 생존 시간, 리프트, AUC)는 그려진 데이터에서 계산했어요. '
            '구성 참고: 사용자가 공유한 분석 차트 이미지(@isaac.perform), MAE-299.</p>\n</div>\n</body>\n</html>\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='rebuild and compare with the committed file')
    args = parser.parse_args(argv)
    html = build()
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding='utf-8') != html:
            print(f'stale: {OUT} differs from the generated page; run without --check')
            return 1
        print('example-analysis: statistics asserted, committed file matches')
        return 0
    OUT.write_text(html, encoding='utf-8')
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
