### 보안 기본값 점검 2026-10-18 16:43 KST

**확인이 필요합니다**

- OPEN_SIGNUP 이 true 입니다 — 초대하지 않은 아무 구글 계정이나 로그인됩니다
- 초대하지 않은 임의 계정이 allowedEmail() 을 통과합니다
- 배포본에 Anthropic API 키 가 들어 있습니다

<details><summary>점검 내역</summary>

- OPEN_SIGNUP = True
- 초대 안 된 임의 계정 통과 여부 = True
- 허용 도메인 = ['sookmyung.ac.kr']
- 숙명 계정 통과 여부 = True
- 비밀값 4종 스캔 완료

</details>