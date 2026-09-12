# 자동 점검 카카오톡 알림 설정

허브 자동 점검(`.github/workflows/hub-watch.yml`)이 **새로운 이상을 발견했을 때만**
카카오톡 "나에게 보내기"로 알립니다. 같은 문제가 계속되면 이슈에 댓글만 붙고
카톡은 다시 오지 않습니다.

시크릿 두 개를 등록하면 켜집니다. 없으면 조용히 건너뛰고 이슈만 남습니다.

| 시크릿 이름 | 값 |
|---|---|
| `KAKAO_REST_KEY` | 카카오 앱의 REST API 키 |
| `KAKAO_REFRESH_TOKEN` | `talk_message` 동의를 받은 리프레시 토큰 |

등록 위치: 저장소 → Settings → Secrets and variables → Actions → New repository secret

---

## 리프레시 토큰 받는 법

사전 조건: 카카오 개발자센터에서 **카카오 로그인 활성화**, **Redirect URI 등록**,
**동의항목에 카카오톡 메시지 전송 추가**가 끝나 있어야 합니다.

### 1. 브라우저 주소창에 아래를 입력해 동의 화면을 엽니다

`REST키` 자리에 본인 앱의 REST API 키를 넣으세요.

```
https://kauth.kakao.com/oauth/authorize?client_id=REST키&redirect_uri=https://hyunjeongshin83.github.io/CampusTownHub/&response_type=code&scope=talk_message
```

동의하면 주소창이 이렇게 바뀝니다. `code=` 뒤의 값을 복사하세요.

```
https://hyunjeongshin83.github.io/CampusTownHub/?code=여기가_인가코드
```

### 2. 인가코드를 토큰으로 바꿉니다

터미널(윈도우는 PowerShell)에서 아래를 실행하세요. 인가코드는 **1회용이고 10분 안에** 써야 합니다.

```bash
curl -X POST "https://kauth.kakao.com/oauth/token" \
  -d "grant_type=authorization_code" \
  -d "client_id=REST키" \
  -d "redirect_uri=https://hyunjeongshin83.github.io/CampusTownHub/" \
  -d "code=인가코드"
```

응답의 `refresh_token` 값을 `KAKAO_REFRESH_TOKEN` 시크릿에 넣으면 끝입니다.

### 3. 확인

Actions → 허브 자동 점검 → **Run workflow** 로 즉시 실행해 볼 수 있습니다.
다만 이상이 없으면 카톡은 오지 않습니다(정상 동작). 발송 경로만 확인하시려면
`scripts/kakao_notify.py`를 로컬에서 직접 실행해 보세요.

---

## 유지보수

- 리프레시 토큰 유효기간은 약 2개월입니다. 만료 한 달 전부터 카카오가 새 토큰을 함께
  내려주는데, 그때 워크플로 로그에 경고가 남습니다. 그 값으로 시크릿을 갱신해 주세요.
- 갱신하지 않으면 약 2개월 뒤 카톡 알림만 멈춥니다. 이슈 등록은 계속 동작합니다.
