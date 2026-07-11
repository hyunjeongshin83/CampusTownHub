# 캠퍼스타운 허브 — 무료 배포 가이드

회의 허브를 **무료로** 웹에 올리고, 교수님·인혜 님과 **같은 회의·회의록을 공유**하는 방법입니다.

전부 무료입니다. 신용카드 필요 없습니다.

---

## 1단계 — Supabase (무료 DB) 만들기 · 약 5분

여러 사람이 같은 데이터를 보려면 DB가 필요합니다. Supabase 무료 티어로 충분합니다.

### 1-1. 계정 만들기
1. https://supabase.com 접속 → **Start your project** (GitHub 계정으로 가입 가능)
2. **New Project** 클릭
3. 이름: `campustown-hub` (아무거나)
4. Database Password: 아무거나 정하고 **어딘가 적어두세요**
5. Region: **Northeast Asia (Seoul)** 선택
6. **Create new project** → 1~2분 기다립니다

### 1-2. 테이블 만들기 (복사·붙여넣기)
1. 왼쪽 메뉴에서 **SQL Editor** 클릭
2. **New query** 클릭
3. 아래 SQL을 **그대로 복사해서 붙여넣고** **Run** 클릭

```sql
-- 허브 데이터 저장 테이블
create table if not exists hub_state (
  key text primary key,
  value jsonb,
  updated_at timestamptz default now()
);

-- 접근 권한 (초대된 사람만 쓰도록 나중에 강화 가능)
alter table hub_state enable row level security;

create policy "read hub_state"  on hub_state for select using (true);
create policy "write hub_state" on hub_state for insert with check (true);
create policy "update hub_state" on hub_state for update using (true);
```

"Success. No rows returned" 이 뜨면 성공입니다.

### 1-3. 키 2개 복사하기
1. 왼쪽 메뉴 맨 아래 **Project Settings** (톱니바퀴) → **API**
2. 두 값을 복사합니다:
   - **Project URL** → 예: `https://abcdefgh.supabase.co`
   - **anon public** 키 → 아주 긴 문자열 (`eyJhbGciOi...`)

> **참고**: `anon public` 키는 **공개되어도 되는 키**입니다. 웹사이트에 넣어도 안전합니다.
> (절대 넣으면 안 되는 건 `service_role` 키입니다. 그건 복사하지 마세요.)

---

## 2단계 — 허브 파일에 키 넣기 · 1분

1. `MedIT_회의허브.html` 파일을 메모장(또는 VS Code)으로 엽니다
2. `Ctrl+F`로 **`SUPABASE_URL`** 검색
3. 아래 두 줄을 찾아서 따옴표 사이에 복사한 값을 넣습니다:

```javascript
const SUPABASE_URL = "";        // ← 여기에 Project URL
const SUPABASE_ANON_KEY = "";   // ← 여기에 anon public 키
```

이렇게 됩니다:

```javascript
const SUPABASE_URL = "https://abcdefgh.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6...";
```

4. 저장합니다.

**확인**: 파일을 열고 로그인하면, 회의 목록 아래에 **"● 클라우드 연결됨"** 이라고 뜹니다.
(안 뜨면 키가 잘못된 것 — F12 → Console에서 오류 확인)

---

## 3단계 — GitHub Pages에 올리기 (무료 웹 주소) · 약 10분

### 3-1. GitHub 저장소 만들기
1. https://github.com 가입/로그인
2. 오른쪽 위 **+** → **New repository**
3. 이름: `campustown-hub`
4. **Public** 선택 (Pages 무료는 Public에서 됩니다)
5. **Create repository**

### 3-2. 파일 올리기
1. **uploading an existing file** 클릭
2. 아래 두 파일을 **드래그해서** 올립니다:
   - `MedIT_회의허브.html` → **이름을 `index.html`로 바꿔서** 올리세요 (중요!)
   - `MediNote_app.html`
3. **Commit changes** 클릭

> `index.html`로 바꿔야 주소로 접속했을 때 바로 열립니다.

### 3-3. Pages 켜기
1. 저장소 상단 **Settings** → 왼쪽 메뉴 **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** / **/ (root)** 선택 → **Save**
4. 1~2분 기다리면 위에 주소가 나옵니다:

```
https://<your-id>.github.io/campustown-hub/
```

**이 주소를 교수님·인혜 님께 보내시면 됩니다.**

---

## 이제 이렇게 작동합니다

| 기능 | 상태 |
|---|---|
| 웹 주소로 접속 | ✅ GitHub Pages |
| 초대된 사람만 가입·입장 | ✅ |
| 교수님·인혜 님과 **같은 회의·회의록 공유** | ✅ Supabase |
| 슬라이드 자동 발표 + 음성 | ✅ |
| 화상회의 (Jitsi, 무제한) | ✅ (링크 접속이라 임베드도 작동) |
| 녹취 → 회의록 → **원문 자동 파기** | ✅ |
| 백업 내보내기/가져오기 | ✅ |
| AI 자동 정리·즉석 리서치 | ⚠️ 아래 참고 |

### AI 기능만은 별도입니다 (선택)

AI(회의록 자동정리·즉석 리서치·이메일 자동작성)는 `api.anthropic.com` 호출이 필요한데,
**API 키를 웹페이지에 넣으면 누구나 훔쳐볼 수 있습니다.** 절대 넣지 마세요.

AI가 필요하면 두 가지 선택지:
1. **AI 없이 사용** — 회의록을 직접 작성하거나, 정리된 스크립트를 복사해서 쓰기 (지금도 충분히 실용적)
2. **중계 함수 추가** — Netlify/Vercel 무료 함수에 키를 숨겨서 안전하게 호출 (원하시면 만들어 드립니다)

---

## 문제가 생기면

**"● 로컬 모드"라고 뜸** → 키가 안 들어갔습니다. 2단계를 다시 확인하세요.

**"● 클라우드 연결 실패"** → 키는 넣었는데 연결이 안 됨.
- F12 → Console에서 빨간 오류 확인
- SQL(1-2단계)을 실행했는지 확인
- URL 끝에 `/`가 붙어있으면 지우세요

**교수님이 가입이 안 된다고 함** → 초대 명단에 이메일이 있어야 합니다.
현재 초대된 이메일:
- `jsbang@sookmyung.ac.kr` (방준석 교수님)
- `jih4154@sookmyung.ac.kr` (진인혜)
- `hyunjeong.shin@sookmyung.ac.kr` (신현정)
- `operator@campustown.hub` (운영자)

다른 사람을 초대하려면: 개최자로 로그인 → 회의 → 사전 준비 탭에서 참석자 추가

---

## 보안에 관한 솔직한 안내

- `anon public` 키는 공개해도 되지만, **현재 설정은 누구나 읽고 쓸 수 있습니다** (RLS 정책이 `true`).
  진짜 기밀 회의라면 Supabase Auth를 붙여 **로그인한 사람만** 접근하도록 강화해야 합니다.
- 지금 구조는 "실수로 남이 들어오는 것"은 막지만, 작정한 사람은 막지 못합니다.
- 매우 민감한 내용은 회의록을 이메일로 내보낸 뒤 허브 기록을 삭제하시길 권합니다.

강화가 필요하면 말씀해 주세요 — Supabase Auth 연동까지 만들어 드리겠습니다.

---

© 2026 MedIT. All rights reserved.
