<p align="center">
  <img src="harness_banner.png" alt="Harness Banner" width="600">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.1-brightgreen.svg" alt="Version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Claude_Code-Plugin-purple.svg" alt="Claude Code Plugin">
  <img src="https://img.shields.io/badge/Patterns-6_Architectures-orange.svg" alt="6 Architecture Patterns">
</p>

# myharness — Claude Code 에이전트 팀 & 스킬 아키텍트

[English](README.md) | **한국어** | [日本語](README_JA.md)

> **"하네스 구성해줘"** 한마디면, 도메인 설명을 에이전트 팀과 그들이 사용할 스킬 세트로 변환합니다.

> **포크 안내.** [revfactory/harness](https://github.com/revfactory/harness)(Apache-2.0)의 개인 포크입니다. 원저작자 표기와 변경 내역 전문은 [`NOTICE`](NOTICE)를 참조하세요.

## 개요

myharness는 복잡한 작업을 전문 에이전트들의 협업 팀으로 분해합니다. 도메인에 맞는 에이전트 정의(`.claude/agents/`)와 스킬(`.claude/skills/`)을 생성하고, 오케스트레이터 스킬로 이들을 하나의 워크플로우로 엮습니다.

## 설치

```shell
/plugin marketplace add punkyade/myharness
/plugin install myharness@myharness-marketplace
```

플러그인 시스템 없이 스킬만 직접 설치하려면:

```shell
cp -r skills/harness ~/.claude/skills/harness
```

## 요구사항

- [에이전트 팀 활성화](https://code.claude.com/docs/en/agent-teams): `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

이 플래그가 없으면 팀 기반 실행 모드가 단일 에이전트 실행으로 폴백됩니다. [`docs/experimental-dependency.md`](docs/experimental-dependency.md) 참조.

## 사용법

Claude Code에서 다음과 같이 트리거합니다:

```
하네스 구성해줘
이 도메인에 맞는 에이전트 팀을 설계해줘
Build a harness for this project
```

후속 작업도 같은 스킬이 처리합니다. "하네스 점검", "에이전트 추가해줘", "하네스 수정해줘"는 처음부터 다시 만들지 않고 감사·유지보수 경로로 진입합니다.

## 워크플로우

```
Phase 0: 현황 감사 (신규 구축 / 기존 확장 / 운영·유지보수)
    ↓
Phase 1: 도메인 분석
    ↓
Phase 2: 팀 아키텍처 설계 (에이전트 팀 / 서브 에이전트 / 하이브리드)
    ↓
Phase 3: 에이전트 정의 생성 (.claude/agents/)
    ↓
Phase 4: 스킬 생성 (.claude/skills/)
    ↓
Phase 5: 통합 및 오케스트레이션
    ↓
Phase 6: 검증 및 테스트
    ↓
Phase 7: 하네스 진화 (피드백 → 반영 → 변경 이력)
```

### 실행 모드

| 모드 | 방식 | 권장 상황 |
|------|------|----------|
| **에이전트 팀** (기본) | `TeamCreate` + `SendMessage` + `TaskCreate` | 2명 이상이 협업·조율해야 할 때 |
| **서브 에이전트** | `Agent` 도구 직접 호출 | 단발 작업, 에이전트 간 통신 불필요 |
| **하이브리드** | Phase마다 다른 모드 | 예: 병렬 수집(서브) → 합의 통합(팀) |

### 아키텍처 패턴

| 패턴 | 설명 |
|------|------|
| 파이프라인 | 순차 의존 작업 |
| 팬아웃/팬인 | 병렬 독립 작업 |
| 전문가 풀 | 상황별 선택 호출 |
| 생성-검증 | 생성 후 품질 검수 |
| 감독자 | 중앙 에이전트가 상태 관리 및 동적 분배 |
| 계층적 위임 | 상위 에이전트가 하위에 재귀적 위임 |

## 플러그인 구조

```
myharness/
├── .claude-plugin/
│   ├── plugin.json                     # 플러그인 매니페스트
│   └── marketplace.json                # 마켓플레이스 매니페스트
├── skills/
│   └── harness/
│       ├── SKILL.md                    # 메인 스킬 정의 (Phase 0~7)
│       └── references/
│           ├── agent-design-patterns.md   # 6가지 아키텍처 패턴
│           ├── orchestrator-template.md   # 오케스트레이터 템플릿
│           ├── team-examples.md           # 실전 팀 구성 예시 5종
│           ├── skill-writing-guide.md     # 스킬 작성 가이드
│           ├── skill-testing-guide.md     # 테스트·평가 방법론
│           └── qa-agent-guide.md          # QA 에이전트 통합 가이드
└── docs/
    ├── quickstart.md
    └── experimental-dependency.md
```

## 산출물

대상 프로젝트에 생성되는 파일:

```
your-project/
├── CLAUDE.md            # 하네스 포인터 (트리거 규칙 + 변경 이력)
└── .claude/
    ├── agents/          # 에이전트 정의 파일
    │   ├── analyst.md
    │   ├── builder.md
    │   └── qa.md
    └── skills/          # 스킬 파일
        ├── analyze/
        │   └── SKILL.md
        └── build/
            ├── SKILL.md
            └── references/
```

## 프롬프트 예시

```
딥리서치용 하네스를 구성해줘. 웹 검색, 학술 자료, 커뮤니티 반응 등
여러 각도에서 주제를 조사하고 교차 검증한 뒤 종합 보고서를 내는
에이전트 팀이 필요해.
```

```
풀스택 웹사이트 개발 하네스를 구성해줘. 디자인, 프론트엔드(React/Next.js),
백엔드(API), QA 테스트를 와이어프레임부터 배포까지 파이프라인으로
처리하는 팀이면 좋겠어.
```

```
코드 리뷰 하네스를 구성해줘. 아키텍처, 보안 취약점, 성능 병목, 코드 스타일을
병렬 에이전트가 각각 검사한 뒤 하나의 보고서로 통합했으면 해.
```

## 라이선스

Apache 2.0 — [`LICENSE`](LICENSE) 및 [`NOTICE`](NOTICE) 참조.
