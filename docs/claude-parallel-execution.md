# Claude Code 병렬 실행 가이드

> 상위 Claude Code가 하위 Claude Code 인스턴스를 병렬로 실행하는 방법

## 개요

```
┌─────────────────────────────────────┐
│  Claude Code (상위)                  │
│  - 사용자와 대화                      │
│  - 작업 분배 및 조율                  │
│                                     │
│  PowerShell                         │
│       ↓                             │
│  ┌─────────────────────────────────┐│
│  │ claude "하위 작업 1" (병렬)      ││
│  │ claude "하위 작업 2" (병렬)      ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

## 환경

- OS: Windows 11 x86
- Claude Code: 2.0.75
- Shell: Git Bash (Claude Code 기본) + PowerShell (병렬 실행용)

---

## 시행착오 기록

### 시도 1: 직접 claude 호출 (성공)

```bash
claude -p "1+1은?" --output-format text
```

**결과**: 성공. 기본적인 CLI 호출은 문제없음.

---

### 시도 2: Bash에서 백그라운드 실행 (실패)

```bash
start /B claude -p "작업1" > result1.txt &
start /B claude -p "작업2" > result2.txt &
```

**오류**:
- `start /B`는 Windows cmd.exe 전용 명령어
- Claude Code의 Bash 도구는 Git Bash/WSL 환경에서 실행됨
- 두 환경이 섞여서 명령어가 인식되지 않음

**원인**: Shell 환경 불일치

---

### 시도 3: cmd.exe 명시적 호출 (부분 실패)

```bash
cmd.exe /C "start /B claude -p \"작업\" > result.txt"
```

**결과**: 명령은 실행되지만 결과 파일이 생성되지 않음

**원인**: 백그라운드 프로세스의 작업 디렉토리와 출력 리다이렉션 문제

---

### 시도 4: PowerShell 직접 명령 (실패)

```bash
powershell.exe -Command "Start-Process -FilePath 'claude' ..."
```

**오류**:
```
'%1은(는) 올바른 Win32 응용 프로그램이 아닙니다'
```

**원인**:
- `claude`는 Node.js 스크립트
- Windows에서는 `claude.cmd` 래퍼를 통해 실행해야 함
- 경로: `C:\Users\wjd86\AppData\Roaming\npm\claude.cmd`

---

### 시도 5: PowerShell Start-Job (실패)

```powershell
$job1 = Start-Job { & 'claude.cmd' -p '작업' }
```

**오류**: Job이 null로 반환됨

**원인**:
- Start-Job은 별도 PowerShell 프로세스에서 실행
- 해당 프로세스에서 claude.cmd 실행 환경이 제대로 설정되지 않음

---

### 시도 6: PowerShell Start-Process + cmd.exe (성공!)

```powershell
$proc1 = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d C:\project && claude -p `"작업`" > result.txt" `
    -NoNewWindow -PassThru

$proc1.WaitForExit()
Get-Content result.txt
```

**결과**: 성공!

**성공 요인**:
1. `Start-Process`로 완전히 독립된 프로세스 생성
2. `cmd.exe`를 통해 claude 실행 (Node.js 래퍼 호환)
3. `/c cd /d`로 작업 디렉토리 명시적 설정
4. 결과를 파일로 저장 후 읽기

---

## 최종 해결책

### 작동하는 PowerShell 스크립트

```powershell
# parallel_claude.ps1
# 사용법: powershell.exe -ExecutionPolicy Bypass -File parallel_claude.ps1

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$projectPath = "C:\Users\wjd86\t\study\chalssak"
$startTime = Get-Date

# 병렬로 두 개의 Claude 프로세스 시작
$proc1 = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d $projectPath && claude -p `"작업1 내용`" --output-format text > result1.txt 2>&1" `
    -NoNewWindow -PassThru

$proc2 = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c cd /d $projectPath && claude -p `"작업2 내용`" --output-format text > result2.txt 2>&1" `
    -NoNewWindow -PassThru

Write-Host "Started at: $($startTime.ToString('HH:mm:ss'))"

# 모든 프로세스 완료 대기
$proc1.WaitForExit()
$proc2.WaitForExit()

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

Write-Host "Finished at: $($endTime.ToString('HH:mm:ss'))"
Write-Host "Duration: $duration seconds"

# 결과 읽기
Write-Host "`n=== Result 1 ==="
Get-Content "$projectPath\result1.txt" -Encoding UTF8

Write-Host "`n=== Result 2 ==="
Get-Content "$projectPath\result2.txt" -Encoding UTF8
```

### Claude Code에서 호출하는 방법

```bash
powershell.exe -ExecutionPolicy Bypass -File "C:\path\to\parallel_claude.ps1"
```

---

## 성능 비교

| 실행 방식 | 소요 시간 |
|-----------|-----------|
| 순차 실행 (2개 작업) | ~40초 |
| 병렬 실행 (2개 작업) | ~25초 |
| **절감률** | **~37%** |

---

## 주의사항

1. **인코딩**: 한글 출력 시 UTF-8 설정 필요
2. **경로**: 공백이 있는 경로는 따옴표로 감싸기
3. **프롬프트 이스케이프**: 쌍따옴표 내부의 따옴표는 백틱(`)으로 이스케이프
4. **작업 디렉토리**: `cd /d`로 드라이브까지 포함해서 이동

---

## 활용 시나리오

### 1. 병렬 코드 분석
```powershell
# 여러 폴더를 동시에 분석
claude -p "src/api 분석" > api_analysis.txt &
claude -p "src/services 분석" > services_analysis.txt &
claude -p "tests 분석" > tests_analysis.txt &
```

### 2. 분할 작업
```powershell
# 설계 → 구현 → 테스트를 독립 컨텍스트로
claude -p "기능 X 설계" > design.txt
claude -p "design.txt 기반으로 구현" > impl.txt
claude -p "impl.txt 기반으로 테스트 작성" > test.txt
```

### 3. 독립 컨텍스트 작업
```powershell
# 각 작업이 서로의 컨텍스트를 오염시키지 않음
claude -p "버그 A 수정" > bugfix_a.txt &
claude -p "기능 B 추가" > feature_b.txt &
```

---

## 파일 목록

- `parallel_test.ps1` - 초기 테스트 스크립트 (Start-Job 방식, 실패)
- `parallel_test2.ps1` - 최종 작동 스크립트 (Start-Process 방식, 성공)
- `docs/claude-parallel-execution.md` - 이 문서

---

## 결론

추가 MCP 설치 없이 **PowerShell의 Start-Process**만으로 Claude Code 병렬 실행이 가능합니다.

핵심은:
1. `cmd.exe`를 통해 claude 호출 (Node.js 래퍼 호환성)
2. `Start-Process -PassThru`로 프로세스 핸들 획득
3. 결과는 파일로 저장 후 읽기
