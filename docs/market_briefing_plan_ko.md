# 전일 시장 요약 자동화 프로그램 설계안

## 1) 목표 정의
- **목표**: 매일 오전 10시(로컬 타임존 기준)에 **전일 시장 데이터**를 수집하여, 첨부한 UI 스타일의 HTML 리포트를 생성/저장.
- **데이터 소스**: `FinanceDataReader`(FDR) 우선 사용.
- **산출물**:
  - 일별 HTML (`output/2026-04-18_market_summary.html` 형태)
  - 원천 데이터 JSON/CSV(재현성·감사 로그 목적)
  - 실행 로그 파일

---

## 2) 핵심 고려사항

### A. "전일" 기준일 계산 (가장 중요)
- 한국 기준 오전 10시에 실행하더라도, 자산별로 거래 마감 시점/휴장일이 다름.
- 단순히 `today - 1day`가 아니라, **각 지표별 마지막 유효 거래일(last available trading day)** 을 찾는 방식 권장.
- 공휴일/주말/데이터 지연 시 fallback 로직 필요.

### B. 데이터 정합성/결측치
- 지표마다 심볼과 제공 필드(종가/전일비/등락률)가 다를 수 있음.
- `close`, `prev_close`, `change_pct`를 내부 표준 스키마로 정규화.
- 결측 시 화면에 `N/A` 표시 + 경고 로그 남기기.

### C. 스케줄링 안정성
- 로컬 PC 실행이면 OS 스케줄러(Windows 작업 스케줄러 / cron) 사용.
- 서버/컨테이너라면 `cron + lockfile` 또는 워크플로우 도구(예: Airflow) 고려.
- 중복 실행 방지(락 파일), 실패 시 재시도(예: 10분 간격 2회).

### D. UI/리포트 버전 관리
- HTML 템플릿(Jinja2)과 데이터 로직 분리.
- 스타일은 고정 CSS로 유지, 데이터만 치환.
- 과거 리포트 회귀 비교를 위해 파일명에 날짜 포함.

### E. 운영 관점
- 예외/오류 알림(이메일, 슬랙 등) 추가 시 운영 효율 상승.
- 장기적으로는 SQLite/PostgreSQL에 저장해 통계/추세 기능 확장 가능.

---

## 3) 권장 아키텍처

```text
[Scheduler 10:00]
      ↓
[Collector(FDR)] --(raw 저장: json/csv)--> [data/raw/YYYY-MM-DD.json]
      ↓
[Normalizer/Calculator]
      ↓
[Renderer(Jinja2 HTML 템플릿)]
      ↓
[output/YYYY-MM-DD_market_summary.html]
      ↓
[Logger/Notifier]
```

### 디렉터리 예시
```text
project/
  src/
    collect.py
    normalize.py
    render.py
    main.py
  templates/
    market_summary.html.j2
  static/
    market_summary.css
  config/
    symbols.yml
  data/raw/
  output/
  logs/
```

---

## 4) 데이터 모델(내부 표준)

```json
{
  "as_of_date": "2026-04-17",
  "generated_at": "2026-04-18T10:00:03+09:00",
  "sections": {
    "domestic": [
      {"name": "코스피", "value": 5301.69, "change_pct": 0.06, "direction": "up"},
      {"name": "코스닥", "value": 1115.20, "change_pct": -1.09, "direction": "down"}
    ],
    "global": [],
    "fx": [],
    "commodities": []
  }
}
```

- `direction`: `up/down/flat`
- `change_pct`: 소수점(예: `0.06` = +0.06%)
- UI 표시 시 색상/아이콘(▲▼)은 renderer에서 처리

---

## 5) 구현 단계별 계획 (권장 순서)

1. **심볼 확정**
   - 화면 항목(코스피/코스닥/다우/나스닥/상해/니케이/환율/금/은/WTI)에 대한 FDR 조회 가능 심볼 확정.
   - 심볼은 코드에 하드코딩하지 말고 `config/symbols.yml`로 분리.

2. **수집기(Collector) 구현**
   - 심볼별 최근 10~15영업일 데이터 조회.
   - 마지막 2개 유효 데이터로 `value`, `change_pct` 계산.

3. **정규화/검증 구현**
   - 필수값 누락 체크, 이상치 체크(예: 등락률 절댓값 > 20% 경고).
   - 누락값 `N/A` 처리.

4. **HTML 템플릿 구현**
   - 첨부 UI와 유사한 2열 테이블 블록(국내/해외/환율/상품).
   - 상승(빨강), 하락(파랑), 보합(회색) 스타일 적용.

5. **스케줄링 + 로그 + 알림**
   - 오전 10시 실행 등록.
   - 성공/실패 로그 기록 + 실패 알림.

6. **운영 테스트(최소 1주)**
   - 휴장일/주말/데이터 지연 케이스 점검.
   - HTML 파일 생성 여부와 값 정확성 검수.

---

## 6) 스케줄링 방법 제안

### 옵션 1. 운영체제 스케줄러(간단, 권장)
- Windows: 작업 스케줄러에서 `python src/main.py`를 매일 10:00 실행
- Linux: `0 10 * * * /usr/bin/python3 /path/src/main.py`

### 옵션 2. Python 내부 스케줄러
- `APScheduler` 등 사용 가능하나, 프로세스 상시 실행/장애 복구 고려 필요.
- 개인/소규모 운영은 OS 스케줄러가 단순하고 안정적.

---

## 7) 실패 시나리오와 대응
- API/소스 장애: 이전 영업일 데이터로 fallback + 경고 배지 표시
- 일부 심볼 실패: 전체 중단 대신 부분 성공 허용 (`N/A` 렌더링)
- 템플릿 렌더 실패: raw 데이터만 저장하고 오류 알림
- 중복 실행: lockfile로 동시 실행 방지

---

## 8) 보안/품질 체크리스트
- 외부 입력값(심볼/이름) HTML escape
- 로그에 민감정보 저장 금지
- 테스트:
  - 기준일 계산 함수 단위 테스트
  - 등락률 계산 테스트(0분모, 결측)
  - 렌더링 스냅샷 테스트

---

## 9) 빠른 MVP 범위(1~2일)
- 고정 심볼 10개 내외
- 일 1회 수집 및 HTML 생성
- 로컬 파일 저장 + 기본 로그

## 10) 확장 로드맵
- 주간/월간 요약 자동 생성
- 이메일/메신저 발송
- DB 적재 후 대시보드화
- 생성형 AI 코멘트(시장 해설) 추가

