#!/usr/bin/env python3
"""외부 CLI 에이전트에 작업을 위임하고 결과를 정규화해 회수한다.

어댑터 에이전트가 호출하는 진입점. 런타임마다 다른 호출 문법·결과 회수
방식·샌드박스 플래그를 흡수해서, 호출하는 쪽은 동일한 인터페이스만 쓰면
되게 한다.

    python delegate.py --runtime codex --prompt-file p.txt --out r.txt

종료 코드:
    0  성공 — --out 에 결과가 기록됨
    2  타임아웃 — 부분 출력이 있으면 --out 에 기록됨
    3  런타임 오류 — CLI 부재, 인증 실패, 비정상 종료, 빈 응답

종료 코드를 3분류로 나누는 이유: 어댑터가 재시도 여부를 판단해야 한다.
타임아웃(2)은 재시도할 가치가 있지만, CLI 부재(3)는 몇 번을 재시도해도
같은 결과다.

알려진 한계:
    agy 는 stdin 프롬프트를 지원하지 않아 짧은 프롬프트가 프로세스 명령줄에
    남는다. 같은 머신의 다른 프로세스가 이를 조회할 수 있으므로, 비밀정보를
    프롬프트에 넣지 마라. (codex 는 항상 stdin 을 쓴다. agy 도 프롬프트가
    ARG_PROMPT_LIMIT 를 넘으면 파일 참조 방식으로 전환된다.)

새 런타임 추가는 RUNTIMES 에 항목 하나를 더하는 것으로 끝난다.
"""

from __future__ import annotations

import argparse
import locale
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_TIMEOUT = 2
EXIT_RUNTIME_ERROR = 3

DEFAULT_TIMEOUT = 600

# Windows 콘솔 기본 인코딩(cp949 등)에서는 한글 메시지가 깨져 나간다.
# 어댑터 에이전트는 stderr 를 읽고 실패 사유를 판단하므로, 읽을 수 없는
# 메시지는 진단 자체를 무력화한다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


class _Parser(argparse.ArgumentParser):
    """인자 오류도 런타임 오류(3)로 낸다.

    argparse 기본값은 종료 코드 2인데, 이 스크립트에서 2는 '타임아웃 —
    재시도할 가치가 있음'을 뜻한다. 그대로 두면 어댑터가 오타난 인자를
    재시도 대상으로 오인한다.
    """

    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"delegate: 인자 오류: {message}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME_ERROR)


# Windows CreateProcess 의 명령줄 상한은 32767 자이지만, cmd.exe 를 경유하는
# .CMD shim 은 8191 자에서 끊긴다. 여유를 두고 이 값을 넘으면 프롬프트를
# argv 로 넘기지 않는다.
ARG_PROMPT_LIMIT = 6000


def _codex_argv(a: argparse.Namespace, prompt: str, out: Path) -> tuple[list[str], str | None]:
    """codex 는 -o 로 최종 메시지를 파일에 직접 쓴다.

    프롬프트 자리에 '-' 를 주면 stdin 에서 읽으므로 길이 제한이 없다.
    항상 stdin 을 쓴다 — 짧은 프롬프트에도 동작하고, 분기가 하나 줄어든다.
    """
    argv = [
        "codex", "exec",
        "--sandbox", a.sandbox_codex,
        "--skip-git-repo-check",
        "-o", str(out),
    ]
    if a.cwd:
        argv += ["-C", str(a.cwd)]
    if a.model:
        argv += ["-m", a.model]
    if a.schema:
        argv += ["--output-schema", str(a.schema)]
    argv.append("-")
    return argv, prompt


def _agy_argv(a: argparse.Namespace, prompt: str, out: Path) -> tuple[list[str], str | None]:
    """agy 는 stdout 으로 응답을 내보낸다 — 호출부가 캡처해 기록한다.

    agy 는 stdin 프롬프트를 지원하지 않는다 (인자 없이 -p 를 주면 help 를
    출력한다). 따라서 긴 프롬프트는 argv 상한에 걸린다. 이 경우 프롬프트
    파일을 읽으라는 짧은 지시로 대체하고, 파일이 있는 디렉터리를 작업
    공간에 추가한다 — agy 는 에이전트이므로 파일을 직접 읽을 수 있다.
    """
    argv = ["agy"]
    extra_dir: Path | None = None

    if len(prompt) > ARG_PROMPT_LIMIT:
        pf = a.prompt_file.resolve()
        argv += ["-p", (
            f"Read the file at {pf} and follow the instructions in it exactly. "
            f"Output only what those instructions ask for."
        )]
        extra_dir = pf.parent
    else:
        argv += ["-p", prompt]

    argv += ["--output-format", a.output_format]
    if a.sandbox_agy:
        argv.append("--sandbox")
    if a.cwd:
        argv += ["--add-dir", str(a.cwd)]
    if extra_dir and (not a.cwd or extra_dir != Path(a.cwd).resolve()):
        argv += ["--add-dir", str(extra_dir)]
    if a.model:
        argv += ["--model", a.model]
    if a.schema:
        argv += ["--json-schema", str(a.schema)]
    return argv, None


# writes_out_itself: True 면 CLI 가 --out 파일을 직접 쓴다.
# False 면 stdout 을 캡처해 이쪽에서 기록한다.
# argv 빌더는 (argv, stdin_payload) 를 반환한다.
RUNTIMES = {
    "codex": {"bin": "codex", "argv": _codex_argv, "writes_out_itself": True},
    "agy": {"bin": "agy", "argv": _agy_argv, "writes_out_itself": False},
}


def _decode(raw: bytes | str | None) -> str:
    """서브프로세스 출력을 디코드한다.

    Windows 콘솔 도구는 UTF-8 이 아니라 로케일 코드페이지(cp949 등)로
    에러를 낸다. UTF-8 로만 디코드하면 진단 메시지가 깨져 실패 원인을
    읽을 수 없다.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8", locale.getpreferredencoding(False), "cp949"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def fail(msg: str, code: int = EXIT_RUNTIME_ERROR) -> int:
    print(f"delegate: {msg}", file=sys.stderr)
    return code


def main() -> int:
    p = _Parser(
        description="외부 CLI 에이전트에 작업을 위임하고 결과를 회수한다.",
    )
    p.add_argument("--runtime", required=True, choices=sorted(RUNTIMES),
                   help="위임할 외부 런타임")
    p.add_argument("--prompt-file", required=True, type=Path,
                   help="프롬프트 파일. 인자가 아닌 파일로 받는 이유: 긴 프롬프트의 "
                        "셸 이스케이프와 인자 길이 제한을 피한다")
    p.add_argument("--out", required=True, type=Path, help="결과를 기록할 경로")
    p.add_argument("--cwd", type=Path, help="외부 런타임의 작업 루트")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"초 단위 (기본 {DEFAULT_TIMEOUT})")
    p.add_argument("--model", help="런타임별 모델 지정")
    p.add_argument("--schema", type=Path, help="JSON Schema 파일 — 구조화 출력 강제")
    p.add_argument("--output-format", default="text",
                   choices=["text", "json"], help="agy 전용")
    p.add_argument("--dry-run", action="store_true",
                   help="실행하지 않고 조립된 명령줄만 출력한다 (샌드박스 플래그 검증용)")

    # 읽기 전용이 기본값이다. 여러 런타임이 같은 워킹트리를 동시에 고치면
    # 충돌·덮어쓰기가 나고 어느 런타임이 무엇을 바꿨는지 추적이 끊긴다.
    # 파일 수정은 Claude Code 가 단일 진입점으로 수행한다.
    p.add_argument("--allow-writes", action="store_true",
                   help="외부 런타임에 쓰기 권한 부여. 기본은 읽기 전용")

    a = p.parse_args()

    a.sandbox_codex = "workspace-write" if a.allow_writes else "read-only"
    a.sandbox_agy = not a.allow_writes

    spec = RUNTIMES[a.runtime]

    # 사전 점검을 먼저 한다. 없는 CLI 를 조용히 건너뛰면
    # "검증했다"는 착각만 남는다.
    resolved = shutil.which(spec["bin"])
    if not resolved:
        return fail(
            f"'{spec['bin']}' 를 PATH 에서 찾을 수 없다. "
            f"설치·인증 여부를 확인하라."
        )

    if not a.prompt_file.is_file():
        return fail(f"프롬프트 파일이 없다: {a.prompt_file}")

    # 파일 입출력 예외를 그대로 흘리면 traceback 과 함께 종료 코드 1 이
    # 나온다. 1 은 이 스크립트의 규약에 없는 값이라 어댑터가 분류할 수 없다.
    try:
        prompt = a.prompt_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        return fail(f"프롬프트 파일을 읽을 수 없다 ({a.prompt_file}): {e}")

    if not prompt:
        return fail(f"프롬프트 파일이 비어 있다: {a.prompt_file}")

    try:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        # 이전 실행의 산출물을 먼저 지운다. 남겨두면 런타임이 종료 코드 0 으로
        # 끝나면서 출력 파일을 갱신하지 않았을 때, 아래 빈 응답 검사가 옛 내용을
        # 읽고 성공으로 판정한다 — 낡은 결과가 새 결과로 둔갑한다.
        a.out.unlink(missing_ok=True)
    except OSError as e:
        return fail(f"출력 경로를 준비할 수 없다 ({a.out}): {e}")
    argv, stdin_payload = spec["argv"](a, prompt, a.out)

    # argv[0] 을 해석된 절대 경로로 바꾼다. Windows 에서 npm 전역 설치는
    # 확장자 없는 셸 shim 과 .CMD 가 함께 깔리는데, subprocess 는 PATHEXT 를
    # 보지 않으므로 이름만 넘기면 WinError 2 로 실패한다.
    argv[0] = resolved

    if a.dry_run:
        via = "stdin" if stdin_payload is not None else "argv"
        print(f"# 프롬프트 전달: {via} ({len(prompt)}자)")
        print(" ".join(repr(x) if " " in x else x for x in argv))
        return EXIT_OK

    try:
        proc = subprocess.run(
            argv,
            input=stdin_payload.encode("utf-8") if stdin_payload is not None else None,
            capture_output=True,
            timeout=a.timeout,
            cwd=str(a.cwd) if a.cwd else None,
        )
    except subprocess.TimeoutExpired as e:
        partial = _decode(e.stdout)
        if partial.strip() and not spec["writes_out_itself"]:
            a.out.write_text(partial, encoding="utf-8")
            return fail(f"{a.runtime}: {a.timeout}초 타임아웃 (부분 출력 기록됨)",
                        EXIT_TIMEOUT)
        return fail(f"{a.runtime}: {a.timeout}초 타임아웃", EXIT_TIMEOUT)
    except OSError as e:
        return fail(f"{a.runtime} 실행 실패: {e}")

    stdout, stderr = _decode(proc.stdout), _decode(proc.stderr)

    if proc.returncode != 0:
        detail = (stderr or stdout).strip()
        return fail(
            f"{a.runtime} 비정상 종료 (code={proc.returncode}): "
            f"{detail[:500] or '출력 없음'}"
        )

    try:
        if not spec["writes_out_itself"]:
            a.out.write_text(stdout, encoding="utf-8")

        # 종료 코드 0 인데 빈 응답인 경우가 실제로 있다. 성공으로 흘려보내면
        # 어댑터가 빈 결과를 유효한 산출물로 오인한다. 실행 전에 --out 을
        # 지웠으므로, 여기서 파일이 없다는 것은 런타임이 아무것도 쓰지
        # 않았다는 뜻이다.
        if not a.out.is_file() or not a.out.read_text(encoding="utf-8").strip():
            return fail(f"{a.runtime}: 정상 종료했으나 응답이 비어 있다")
    except (OSError, UnicodeDecodeError) as e:
        return fail(f"{a.runtime}: 결과를 기록·확인할 수 없다 ({a.out}): {e}")

    print(f"delegate: {a.runtime} -> {a.out}", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
