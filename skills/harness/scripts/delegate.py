#!/usr/bin/env python3
"""외부 CLI 에이전트에 작업을 위임하고 결과를 정규화해 회수한다.

어댑터 에이전트가 호출하는 진입점. 런타임마다 다른 호출 문법·결과 회수
방식·샌드박스 플래그를 흡수해서, 호출하는 쪽은 동일한 인터페이스만 쓰면
되게 한다.

    python delegate.py --runtime codex --prompt-file p.txt --out r.txt

종료 코드:
    0  성공 — --out 에 결과가 기록됨
    2  타임아웃 — 재시도할 가치가 있음
    3  런타임 오류 — CLI 부재, 인자 오류, 인증 실패, 비정상 종료, 빈 응답

종료 코드를 3분류로 나누는 이유: 어댑터가 재시도 여부를 판단해야 한다.
타임아웃(2)은 재시도할 가치가 있지만, CLI 부재(3)는 몇 번을 재시도해도
같은 결과다. 그래서 이 스크립트는 0/2/3 외의 코드를 절대 내지 않는다 —
파일 입출력 예외까지 전부 3으로 정규화한다.

신뢰 모델:
    프롬프트 내용은 신뢰할 수 없다. 리뷰 대상 저장소의 코드가 그대로
    들어가므로, 저장소에 파일 하나를 넣을 수 있는 사람이 내용을 통제한다.
    따라서 프롬프트는 **절대 명령줄에 싣지 않는다** — codex 는 stdin,
    agy 는 파일 참조로 넘긴다. Windows 의 .cmd shim 은 cmd.exe 재파싱을
    거치므로, argv 에 실린 프롬프트는 첫 개행에서 잘리거나 메타문자로
    임의 명령을 실행시킬 수 있다.

새 런타임 추가는 RUNTIMES 에 항목 하나를 더하는 것으로 끝난다.
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
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


def fail(msg: str, code: int = EXIT_RUNTIME_ERROR) -> int:
    print(f"delegate: {msg}", file=sys.stderr)
    return code


# ─── 실행 파일 탐색 ────────────────────────────────────────────────────────

def _which(name: str) -> str | None:
    """PATH 에서만 실행 파일을 찾는다.

    shutil.which 를 쓰지 않는 이유: win32 에서 os.curdir 를 검색 경로
    맨 앞에 끼워 넣는다. 이 스크립트는 리뷰 대상 저장소를 cwd 로 두고
    돌기 때문에, 저장소에 codex.cmd 를 심어두면 인증된 CLI 대신 그것이
    실행된다.
    """
    exts = [""]
    if os.name == "nt":
        pathext = [e for e in os.environ.get(
            "PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep) if e]
        if name.lower().endswith(tuple(e.lower() for e in pathext)):
            exts = [""]          # 이미 확장자가 붙어 있다
        else:
            # PATHEXT 를 먼저 시도한다. npm 전역 설치는 확장자 없는 셸
            # 스크립트와 .CMD 를 같은 디렉터리에 함께 깔아 두는데,
            # 확장자 없는 쪽은 Windows 가 실행하지 못해 WinError 2 가 난다.
            exts = [*pathext, ""]

    for entry in os.environ.get("PATH", os.defpath).split(os.pathsep):
        # 절대 경로가 아닌 항목은 전부 건너뛴다. 빈 문자열과 '.' 은 cwd 를
        # 뜻하는데, 이 스크립트는 리뷰 대상 저장소를 cwd 로 두고 돌기 때문에
        # 저장소가 커밋해 둔 codex.cmd 가 인증된 CLI 대신 실행된다.
        # 이 머신의 PATH 에는 실제로 '.' 항목이 들어 있다 — 이론적 위험이
        # 아니라 기본 시나리오다.
        if not entry or not os.path.isabs(entry):
            continue
        base = Path(entry)
        for ext in exts:
            cand = base / (name + ext)
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand.resolve())
    return None


# cmd.exe 가 메타문자로 해석하는 것들. .cmd/.bat shim 을 경유할 때는
# Python 의 인용 처리가 cmd.exe 에 통하지 않아 이들이 그대로 새어 나간다.
_CMD_META = re.compile(r'[&|<>^"%\r\n]')


def _is_shim(path: str) -> bool:
    return path.lower().endswith((".cmd", ".bat"))


def _reject_unsafe_argv(resolved: str, argv: list[str]) -> str | None:
    """.cmd/.bat 경유 시 메타문자가 든 인자를 거부한다.

    Python 의 list2cmdline 은 " 를 \\" 로 이스케이프하지만 cmd.exe 는
    \\" 를 이스케이프로 인정하지 않는다. 따옴표 개수를 고르면 메타문자가
    인용 구간 밖으로 빠져나와 별도 명령으로 실행된다 (실측 확인됨).
    프롬프트는 이미 argv 에 싣지 않으므로, 남은 위험은 경로·모델명 같은
    인자값이다. 이들은 정상적으로 메타문자를 포함할 이유가 없다.
    """
    if not _is_shim(resolved):
        return None
    for a in argv[1:]:
        if _CMD_META.search(a):
            return (
                f"'{Path(resolved).name}' 은(는) 배치 shim 이라 cmd.exe 를 "
                f"경유한다. 메타문자가 든 인자를 넘기면 임의 명령이 실행될 "
                f"수 있어 거부한다: {a[:120]!r}"
            )
    return None


# ─── 런타임별 인자 조립 ────────────────────────────────────────────────────

def _codex_argv(a, prompt_path: Path, raw_out: Path) -> tuple[list[str], bool]:
    """codex 는 -o 로 최종 메시지를 파일에 직접 쓴다.

    프롬프트 자리에 '-' 를 주면 stdin 에서 읽는다. 항상 stdin 을 쓴다 —
    길이 제한이 없고, 프롬프트가 명령줄에 남지 않는다.
    """
    argv = [
        "codex", "exec",
        "--sandbox", a.sandbox_codex,
        "--skip-git-repo-check",
        "-o", str(raw_out),
        "-C", str(a.cwd),
    ]
    if a.model:
        argv += ["-m", a.model]
    if a.schema:
        argv += ["--output-schema", str(a.schema)]
    argv.append("-")
    return argv, True  # stdin 사용


def _agy_argv(a, prompt_path: Path, raw_out: Path) -> tuple[list[str], bool]:
    """agy 는 stdout 으로 응답을 내보낸다 — 호출부가 캡처해 기록한다.

    agy 는 stdin 프롬프트를 지원하지 않는다(인자 없이 -p 를 주면 help 를
    출력한다). 그렇다고 프롬프트를 argv 에 실으면 .cmd shim 경유 시 첫
    개행에서 잘리고 메타문자 주입이 열린다. 따라서 **길이와 무관하게 항상**
    프롬프트 파일을 읽으라는 짧은 지시로 넘긴다 — agy 는 에이전트이므로
    파일을 직접 읽을 수 있다.

    길이 기준으로 분기하던 이전 방식은 틀렸다: 실제 파괴 임계값은 길이가
    아니라 첫 개행 위치이고, 리뷰 프롬프트는 사실상 항상 여러 줄이다.
    """
    argv = [
        "agy", "-p",
        f"Read the file at {prompt_path} and follow the instructions in it "
        f"exactly. Output only what those instructions ask for.",
        "--output-format", a.output_format,
        "--add-dir", str(a.cwd),
    ]
    if a.sandbox_agy:
        argv.append("--sandbox")
    if a.model:
        argv += ["--model", a.model]
    if a.schema:
        argv += ["--json-schema", str(a.schema)]
    return argv, False  # stdout 캡처


RUNTIMES = {
    # writes_out_itself: True 면 CLI 가 결과 파일을 직접 쓴다.
    # False 면 stdout 을 캡처해 이쪽에서 기록한다.
    # supports_json: --output-format json 을 실제로 반영하는가.
    "codex": {"bin": "codex", "argv": _codex_argv,
              "writes_out_itself": True, "supports_json": False},
    "agy": {"bin": "agy", "argv": _agy_argv,
            "writes_out_itself": False, "supports_json": True},
}


# ─── 실행 ─────────────────────────────────────────────────────────────────

def _decode(raw) -> str:
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


def _kill_tree(proc: subprocess.Popen) -> None:
    """자식 프로세스 트리 전체를 종료한다.

    subprocess 의 timeout 은 직접 띄운 프로세스만 죽인다. 외부 CLI 는
    자기 자식(node, 모델 런너 등)을 띄우므로, 부모만 죽이면 손자들이
    계속 돌면서 재시도 실행과 충돌한다.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=30,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _run(argv, stdin_payload, cwd, timeout):
    """(returncode, stdout, stderr, timed_out) 반환."""
    popen_kw = {
        "stdin": subprocess.PIPE if stdin_payload is not None else subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": str(cwd),
    }
    if os.name == "nt":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True

    proc = subprocess.Popen(argv, **popen_kw)
    payload = stdin_payload.encode("utf-8") if stdin_payload is not None else None
    try:
        out, err = proc.communicate(input=payload, timeout=timeout)
        return proc.returncode, _decode(out), _decode(err), False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=30)
        except Exception:
            out, err = b"", b""
        return None, _decode(out), _decode(err), True


def _meaningful(text: str, as_json: bool) -> bool:
    """응답에 실제 내용이 있는가.

    JSON 모드에서는 봉투(`{"result": "", ...}`)가 항상 non-empty 라
    문자열 검사만으로는 빈 응답을 걸러내지 못한다.
    """
    if not text.strip():
        return False
    if not as_json:
        return True
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return True  # JSON 이 아니면 원문 그대로 판단
    if isinstance(obj, dict):
        for key in ("result", "response", "output", "text", "content", "message"):
            if key in obj:
                v = obj[key]
                return bool(v.strip()) if isinstance(v, str) else bool(v)
        return bool(obj)
    return bool(obj)


# ─── 메인 ─────────────────────────────────────────────────────────────────

def main() -> int:
    p = _Parser(description="외부 CLI 에이전트에 작업을 위임하고 결과를 회수한다.")
    p.add_argument("--runtime", required=True, choices=sorted(RUNTIMES))
    p.add_argument("--prompt-file", required=True, type=Path,
                   help="프롬프트 파일. 내용은 절대 명령줄에 실리지 않는다")
    p.add_argument("--out", required=True, type=Path, help="결과를 기록할 경로")
    p.add_argument("--cwd", type=Path, help="외부 런타임의 작업 루트 (기본: 현재 디렉터리)")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"초 단위, 양수 (기본 {DEFAULT_TIMEOUT})")
    p.add_argument("--model", help="런타임별 모델 지정")
    p.add_argument("--schema", type=Path, help="JSON Schema 파일 — 구조화 출력 강제")
    p.add_argument("--output-format", default="text", choices=["text", "json"])
    p.add_argument("--dry-run", action="store_true",
                   help="실행하지 않고 조립된 명령줄만 출력한다. 부작용 없음")
    # 읽기 전용이 기본값이다. 여러 런타임이 같은 워킹트리를 동시에 고치면
    # 충돌·덮어쓰기가 나고 어느 런타임이 무엇을 바꿨는지 추적이 끊긴다.
    p.add_argument("--allow-writes", action="store_true",
                   help="외부 런타임에 쓰기 권한 부여. 기본은 읽기 전용")
    p.add_argument("--allow-out-outside-cwd", action="store_true",
                   help="--out 이 작업 루트 밖을 가리키는 것을 허용한다. "
                        "기본은 거부 — 임의 파일 덮어쓰기를 막는다")

    a = p.parse_args()

    # --- 인자 검증 (전부 종료 코드 3) ---

    if a.timeout <= 0:
        # 0/음수는 타임아웃이 아니라 인자 오류다. subprocess 는 timeout=0 에
        # 즉시 TimeoutExpired 를 던지므로, 그대로 두면 2가 나가고 어댑터가
        # 무의미한 재시도를 반복한다.
        return fail(f"--timeout 은 양수여야 한다 (받은 값: {a.timeout})")

    spec = RUNTIMES[a.runtime]

    if a.output_format == "json" and not spec["supports_json"]:
        # 조용히 무시하면 호출부가 결과 파일에 json.load 를 걸었다가
        # 엉뚱한 지점에서 깨진다.
        return fail(f"{a.runtime} 은(는) --output-format json 을 지원하지 않는다")

    a.cwd = (a.cwd or Path.cwd()).resolve()
    if not a.cwd.is_dir():
        return fail(f"--cwd 가 디렉터리가 아니다: {a.cwd}")

    # 상대 경로는 여기서 전부 절대화한다. 자식은 --cwd 를 자기 cwd 로 삼기
    # 때문에, 상대 경로를 그대로 넘기면 자식과 이쪽이 서로 다른 파일을
    # 가리킨다 — 위임은 성공했는데 "빈 응답"(3)으로 오분류되고 결과가
    # 아무도 보지 않는 위치에 남는다.
    a.out = a.out.resolve()
    a.prompt_file = a.prompt_file.resolve()
    if a.schema:
        a.schema = a.schema.resolve()
        if not a.schema.is_file():
            return fail(f"--schema 파일이 없다: {a.schema}")

    if not a.allow_out_outside_cwd:
        try:
            a.out.relative_to(a.cwd)
        except ValueError:
            return fail(
                f"--out 이 작업 루트 밖을 가리킨다: {a.out}\n"
                f"  작업 루트: {a.cwd}\n"
                f"  의도한 것이면 --allow-out-outside-cwd 를 명시하라. "
                f"기본 거부인 이유: --out 은 샌드박스 통제를 받지 않아 "
                f"설정 파일이나 훅을 덮어쓸 수 있다."
            )

    a.sandbox_codex = "workspace-write" if a.allow_writes else "read-only"
    a.sandbox_agy = not a.allow_writes

    # --- 사전 점검 ---
    # 없는 CLI 를 조용히 건너뛰면 "검증했다"는 착각만 남는다.
    resolved = _which(spec["bin"])
    if not resolved:
        return fail(f"'{spec['bin']}' 를 PATH 에서 찾을 수 없다. "
                    f"설치·인증 여부를 확인하라.")

    if not a.prompt_file.is_file():
        return fail(f"프롬프트 파일이 없다: {a.prompt_file}")

    try:
        prompt = a.prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return fail(f"프롬프트 파일을 읽을 수 없다 ({a.prompt_file}): {e}")

    # 빈 검사에만 strip 을 쓴다. 프롬프트 자체는 원문 그대로 넘긴다 —
    # 들여쓰기가 의미를 갖는 코드 조각이 프롬프트에 들어가기 때문이다.
    if not prompt.strip():
        return fail(f"프롬프트 파일이 비어 있다: {a.prompt_file}")

    # --- 드라이런은 여기서 끝낸다. 파일시스템을 건드리지 않는다 ---
    if a.dry_run:
        argv, uses_stdin = spec["argv"](a, a.prompt_file, a.out)
        argv[0] = resolved
        if (msg := _reject_unsafe_argv(resolved, argv)):
            return fail(msg)
        print(f"# 프롬프트 전달: {'stdin' if uses_stdin else '파일 참조'} "
              f"({len(prompt)}자) · shim={_is_shim(resolved)}")
        print(" ".join(repr(x) if " " in x else x for x in argv))
        return EXIT_OK

    # --- 실행 ---
    # 결과는 임시 파일에 받고 성공했을 때만 --out 으로 옮긴다.
    # 이렇게 하면 (a) 이전 실행의 낡은 내용이 새 결과로 둔갑하지 않고,
    # (b) 실패했을 때 기존 --out 이 파괴되지 않는다.
    try:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix=".delegate-", dir=a.out.parent))
    except OSError as e:
        return fail(f"출력 경로를 준비할 수 없다 ({a.out.parent}): {e}")

    raw_out = tmp_dir / "result"
    # agy 는 프롬프트를 파일로 읽는다. 원본 위치를 그대로 열어주면 그
    # 부모 디렉터리 전체가 외부 에이전트에 노출되므로, 작업 루트 안의
    # 임시 사본을 대신 넘긴다.
    prompt_path = a.prompt_file
    try:
        if not spec["argv"] is _codex_argv:
            prompt_path = tmp_dir / "prompt.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
    except OSError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return fail(f"프롬프트 사본을 만들 수 없다: {e}")

    try:
        argv, uses_stdin = spec["argv"](a, prompt_path, raw_out)
        argv[0] = resolved
        if (msg := _reject_unsafe_argv(resolved, argv)):
            return fail(msg)

        rc, stdout, stderr, timed_out = _run(
            argv, prompt if uses_stdin else None, a.cwd, a.timeout)

        if timed_out:
            return fail(f"{a.runtime}: {a.timeout}초 타임아웃", EXIT_TIMEOUT)

        if rc != 0:
            detail = (stderr or stdout).strip()
            return fail(f"{a.runtime} 비정상 종료 (code={rc}): "
                        f"{detail[:500] or '출력 없음'}")

        if not spec["writes_out_itself"]:
            raw_out.write_text(stdout, encoding="utf-8")

        if not raw_out.is_file():
            return fail(f"{a.runtime}: 정상 종료했으나 결과 파일이 없다")

        body = raw_out.read_text(encoding="utf-8")
        if not _meaningful(body, a.output_format == "json"):
            # 종료 코드 0 인데 빈 응답인 경우가 실제로 있다. 성공으로
            # 흘려보내면 어댑터가 "결함 없음"으로 오인한다.
            return fail(f"{a.runtime}: 정상 종료했으나 응답이 비어 있다")

        os.replace(raw_out, a.out)

    except (OSError, UnicodeDecodeError) as e:
        return fail(f"{a.runtime}: 결과를 처리할 수 없다: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"delegate: {a.runtime} -> {a.out}", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
