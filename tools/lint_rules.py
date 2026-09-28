#!/usr/bin/env python3
"""Project guideline checker: mechanical enforcement of rules in docs/agent/.

Every rule has an ID that matches the docs (e.g. CPP-004 -> docs/agent/cpp.md).
Standard linters (uncrustify, cpplint, flake8, pep257, xmllint, clang-tidy) cover
style; this tool covers the project-specific, ROS-specific mistakes that agents
actually make.

Usage:
    tools/lint_rules.py [PATH ...]      # default: src/
    tools/lint_rules.py --list          # print the rule table
    tools/lint_rules.py --self-test     # every rule's bad sample fires, good sample doesn't

Suppress a finding only with a reason, on the same or the preceding line:
    std::this_thread::sleep_for(1ms);  // guideline-ignore: CPP-003 hardware settle time per datasheet
"""

import argparse
import dataclasses
import io
import pathlib
import re
import sys
import tokenize
from typing import Callable, Iterable, List, Optional

CPP_SUFFIXES = {'.cpp', '.hpp', '.h', '.cc', '.hh', '.cxx'}
HDR_SUFFIXES = {'.hpp', '.h', '.hh'}
PY_SUFFIXES = {'.py'}
SKIP_DIRS = {'build', 'install', 'log', '.git', '__pycache__', '.pytest_cache'}
SUPPRESS_RE = re.compile(r'guideline-ignore:\s*([A-Z]+-\d{3})\s+\S')


@dataclasses.dataclass(frozen=True)
class FileInfo:
    path: pathlib.Path

    @property
    def parts(self):
        return self.path.parts

    @property
    def is_test(self) -> bool:
        return 'test' in self.parts or self.path.name.startswith('test_')

    @property
    def is_launch(self) -> bool:
        return self.path.name.endswith(('.launch.py', '.launch.xml', '.launch.yaml'))

    @property
    def is_cpp(self) -> bool:
        return self.path.suffix in CPP_SUFFIXES

    @property
    def is_header(self) -> bool:
        return self.path.suffix in HDR_SUFFIXES

    @property
    def is_py(self) -> bool:
        return self.path.suffix in PY_SUFFIXES

    @property
    def is_cmake(self) -> bool:
        return self.path.name == 'CMakeLists.txt' or self.path.suffix == '.cmake'

    @property
    def is_package_xml(self) -> bool:
        return self.path.name == 'package.xml'

    @property
    def is_main(self) -> bool:
        return self.path.stem == 'main' or self.path.stem.endswith('_main')

    @property
    def is_qos_definition(self) -> bool:
        return self.path.stem in ('qos', 'qos_profiles')

    @property
    def is_py_node_code(self) -> bool:
        return (self.is_py and not self.is_test and not self.is_launch
                and self.path.name != 'setup.py')


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    doc: str
    message: str
    pattern: re.Pattern
    applies: Callable[[FileInfo], bool]
    bad: str
    good: str
    sample_name: str


def cpp(p: str) -> re.Pattern:
    return re.compile(p, re.MULTILINE | re.DOTALL)


RULES: List[Rule] = [
    # --- Architecture ---------------------------------------------------------
    Rule('ARCH-006', 'architecture.md',
         'ROS 1 API. This workspace is ROS 2 only.',
         re.compile(r'#include\s*[<"]ros/ros\.h|\bros::(NodeHandle|init|spin|Rate|Publisher)\b'
                    r'|\bimport\s+rospy\b|\bfrom\s+rospy\b|\bcatkin_package\s*\(', re.M),
         lambda f: f.is_cpp or f.is_py or f.is_cmake,
         '#include <ros/ros.h>\n', '#include "rclcpp/rclcpp.hpp"\n', 'src/n.cpp'),
    Rule('ARCH-007', 'architecture.md',
         'Absolute user path. Use FindPackageShare / ament_index / parameters.',
         re.compile(r'''["'](/home/|/Users/|C:\\\\Users)'''),
         lambda f: not f.is_package_xml,
         "cfg = '/home/me/robot.yaml'\n",
         "cfg = os.path.join(get_package_share_directory('pkg'), 'config', 'robot.yaml')\n",
         'pkg/node.py'),

    # --- C++ ------------------------------------------------------------------
    Rule('CPP-003', 'cpp.md',
         'Blocking sleep in node code stalls the executor. Use a timer or a state machine.',
         cpp(r'std::this_thread::sleep_(for|until)|rclcpp::sleep_for|\busleep\s*\(|[^:\w.]sleep\s*\('),
         lambda f: f.is_cpp and not f.is_test,
         'void cb() { std::this_thread::sleep_for(100ms); }\n',
         'timer_ = create_wall_timer(100ms, [this] {step();});\n', 'src/n.cpp'),
    Rule('CPP-004', 'cpp.md',
         'Spinning/blocking on a future inside node code deadlocks the executor. '
         'Use async_send_request with a response callback.',
         cpp(r'spin_until_future_complete|\bspin_some\s*\(|\bspin_all\s*\(|\.wait_for\s*\(|'
             r'\bfuture\w*\.get\s*\(\s*\)|\bfuture\w*\.wait\s*\('),
         lambda f: f.is_cpp and not f.is_test and not f.is_main,
         'rclcpp::spin_until_future_complete(node, client->async_send_request(req));\n',
         'client->async_send_request(req, [this](Future f) {on_response(f.get());});\n',
         'src/n.cpp'),
    Rule('CPP-005', 'cpp.md',
         'Use RCLCPP_* logging (with _THROTTLE/_ONCE in loops), not stdout/stderr.',
         cpp(r'std::(cout|cerr|clog)\b|(?<![\w:])(printf|fprintf|puts)\s*\('),
         lambda f: f.is_cpp and not f.is_test,
         'std::cout << "value " << v << std::endl;\n',
         'RCLCPP_DEBUG(get_logger(), "value %f", v);\n', 'src/n.cpp'),
    Rule('CPP-008', 'cpp.md',
         'Raw new/delete. Use std::make_unique / std::make_shared / containers.',
         cpp(r'(?<![\w.:>])new\s+[A-Za-z_:][\w:<>]*\s*[\(\{\[;]'
             r'|(?<!operator)\bdelete\b\s*(\[\s*\])?\s*[A-Za-z_(*]'),
         lambda f: f.is_cpp and not f.is_test,
         'auto * f = new Filter(1.0);\ndelete f;\n',
         'auto f = std::make_unique<Filter>(1.0);\nFilter(const Filter &) = delete;\n',
         'src/n.cpp'),
    Rule('CPP-009', 'cpp.md',
         '`using namespace` in a header leaks into every includer.',
         cpp(r'^\s*using\s+namespace\s+'),
         lambda f: f.is_header,
         'using namespace std::chrono_literals;\n',
         'namespace ns { using std::chrono::milliseconds; }\n', 'include/p/n.hpp'),
    Rule('CPP-012', 'cpp.md',
         'Hand-rolled `while (rclcpp::ok())` / rclcpp::Rate loop in node code. '
         'Use a timer, or a documented dedicated thread (realtime.md).',
         cpp(r'while\s*\(\s*rclcpp::ok\s*\(|\brclcpp::(Wall)?Rate\b'),
         lambda f: f.is_cpp and not f.is_test and not f.is_main,
         'rclcpp::Rate rate(100);\nwhile (rclcpp::ok()) { step(); rate.sleep(); }\n',
         'timer_ = create_wall_timer(10ms, [this] {step();});\n', 'src/n.cpp'),
    Rule('CPP-013', 'cpp.md',
         'Detached thread: unowned lifetime, cannot be joined on shutdown. Own a std::thread '
         'and join it in on_cleanup/destructor.',
         cpp(r'\.detach\s*\(\s*\)'),
         lambda f: f.is_cpp,
         'std::thread([this] {loop();}).detach();\n',
         'worker_ = std::thread([this] {loop();});  // joined in on_cleanup\n', 'src/n.cpp'),

    # --- QoS ------------------------------------------------------------------
    Rule('QOS-001', 'qos.md',
         'Bare numeric QoS depth. Use a named profile from qos.hpp / qos.py.',
         cpp(r'create_(publisher|subscription)\s*(<[^;()]*?>)?\s*\('
             r'(?:[^()]|\((?:[^()]|\([^()]*\))*\))*?,\s*\d+\s*[,)]'
             r'|\bQoS\s*\(\s*\d+\s*\)'),
         lambda f: (f.is_cpp or f.is_py) and not f.is_qos_definition,
         'pub_ = create_publisher<Imu>("imu", 10);\n',
         'pub_ = create_publisher<Imu>("imu", qos::sensor_publisher());\n', 'src/n.cpp'),

    # --- Python ---------------------------------------------------------------
    Rule('PY-001', 'python.md',
         'time.sleep() in node code blocks the executor. Use create_timer or rate-limited state.',
         re.compile(r'\btime\.sleep\s*\(|^\s*from\s+time\s+import\s+.*\bsleep\b', re.M),
         lambda f: f.is_py_node_code,
         'time.sleep(0.5)\n', 'self.create_timer(0.5, self._step)\n', 'pkg/node.py'),
    Rule('PY-002', 'python.md',
         'print() in node code. Use self.get_logger().',
         re.compile(r'(?<![\w.])print\s*\(', re.M),
         lambda f: f.is_py_node_code,
         'print("started")\n', 'self.get_logger().info("started")\n', 'pkg/node.py'),
    Rule('PY-003', 'python.md',
         'Spinning inside node code (e.g. to wait for a service) deadlocks the executor. '
         'Use call_async + add_done_callback, or an async callback.',
         re.compile(r'spin_until_future_complete|\bspin_once\s*\(', re.M),
         lambda f: f.is_py_node_code and not f.path.name.endswith('_main.py'),
         'rclpy.spin_until_future_complete(self, self.cli.call_async(req))\n',
         'self.cli.call_async(req).add_done_callback(self._on_response)\n', 'pkg/node.py'),

    # --- CMake / package ------------------------------------------------------
    Rule('CMAKE-002', 'cpp.md',
         'ament_target_dependencies() is deprecated. Use target_link_libraries() with '
         'exported targets (rclcpp::rclcpp, ${msg_pkg_TARGETS}).',
         re.compile(r'\bament_target_dependencies\s*\(', re.M),
         lambda f: f.is_cmake,
         'ament_target_dependencies(node rclcpp sensor_msgs)\n',
         'target_link_libraries(node PUBLIC rclcpp::rclcpp ${sensor_msgs_TARGETS})\n',
         'CMakeLists.txt'),
    Rule('CMAKE-003', 'cpp.md',
         'Directory-scoped include/link/definitions leak to every target. Use target_* commands.',
         re.compile(r'^\s*(include_directories|link_directories|link_libraries|add_definitions)\s*\(',
                    re.M | re.I),
         lambda f: f.is_cmake,
         'include_directories(include)\n',
         'target_include_directories(lib PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}'
         '/include>)\n', 'CMakeLists.txt'),
    Rule('CMAKE-004', 'cpp.md',
         'file(GLOB) sources are not re-evaluated on change. List sources explicitly.',
         re.compile(r'\bfile\s*\(\s*GLOB', re.M | re.I),
         lambda f: f.is_cmake,
         'file(GLOB SRCS src/*.cpp)\n', 'add_library(core src/a.cpp src/b.cpp)\n',
         'CMakeLists.txt'),
    Rule('CMAKE-005', 'cpp.md',
         'Do not overwrite global CMAKE_CXX_FLAGS in a package; use add_compile_options/target '
         'options. Warnings-as-errors is injected by tools/check.sh.',
         re.compile(r'^\s*set\s*\(\s*CMAKE_(CXX|C)_FLAGS\b', re.M),
         lambda f: f.is_cmake,
         'set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3")\n',
         'add_compile_options(-Wall -Wextra -Wpedantic)\n', 'CMakeLists.txt'),
    Rule('ARCH-004', 'architecture.md',
         'package.xml must use format 3.',
         re.compile(r'<package\s+format\s*=\s*"[12]"'),
         lambda f: f.is_package_xml,
         '<package format="2">\n', '<package format="3">\n', 'package.xml'),
]
RULES_BY_ID = {r.id: r for r in RULES}


# --- Source preprocessing: blank comments and string literals, keep offsets ----

def _blank(text: str) -> str:
    return re.sub(r'[^\n]', ' ', text)


def strip_cpp(src: str) -> str:
    """Replace comments and string/char literals with spaces (newlines kept)."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ''
        if c == '/' and nxt == '/':
            j = src.find('\n', i)
            j = n if j < 0 else j
            out.append(_blank(src[i:j]))
            i = j
        elif c == '/' and nxt == '*':
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(_blank(src[i:j]))
            i = j
        elif c == 'R' and nxt == '"':
            m = re.match(r'R"([^(\s]*)\(', src[i:])
            if m:
                end = src.find(')' + m.group(1) + '"', i)
                j = n if end < 0 else end + len(m.group(1)) + 2
                out.append('""' + _blank(src[i + 2:j]))
                i = j
            else:
                out.append(c)
                i += 1
        elif c in '"\'':
            j = i + 1
            while j < n and src[j] != c and src[j] != '\n':
                j += 2 if src[j] == '\\' else 1
            j = min(j + 1, n)
            out.append(c + _blank(src[i + 1:j - 1]) + c if j - i >= 2 else src[i:j])
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def strip_py(src: str) -> str:
    """Blank comments and string literals using the tokenizer (offsets preserved)."""
    lines = src.splitlines(keepends=True)
    chars = [list(line) for line in lines]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (sr, sc), (er, ec) = tok.start, tok.end
            for r in range(sr - 1, er):
                start = sc if r == sr - 1 else 0
                end = ec if r == er - 1 else len(chars[r])
                for k in range(start, end):
                    if chars[r][k] != '\n':
                        chars[r][k] = ' '
            if tok.type == tokenize.STRING:
                chars[sr - 1][sc] = '"'
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src
    return ''.join(''.join(c) for c in chars)


def strip_hash_comments(src: str) -> str:
    return re.sub(r'#[^\n]*', lambda m: _blank(m.group(0)), src)


def preprocess(info: FileInfo, text: str) -> str:
    if info.is_cpp:
        return strip_cpp(text)
    if info.is_py:
        return strip_py(text)
    if info.is_cmake:
        return strip_hash_comments(text)
    return text


# --- Checking ---------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Finding:
    path: pathlib.Path
    line: int
    rule: Rule

    def __str__(self):
        return (f'{self.path}:{self.line}: [{self.rule.id}] {self.rule.message} '
                f'(docs/agent/{self.rule.doc})')


def suppressed(raw_lines: List[str], line: int, rule_id: str) -> bool:
    for idx in (line - 1, line - 2):
        if 0 <= idx < len(raw_lines):
            m = SUPPRESS_RE.search(raw_lines[idx])
            if m and m.group(1) == rule_id:
                return True
    return False


def check_text(path: pathlib.Path, text: str, rules: Iterable[Rule] = RULES) -> List[Finding]:
    info = FileInfo(path)
    applicable = [r for r in rules if r.applies(info)]
    if not applicable:
        return []
    code = preprocess(info, text)
    raw_lines = text.splitlines()
    findings = []
    for rule in applicable:
        # String-matching rules (ARCH-007) must see literals.
        haystack = text if rule.id == 'ARCH-007' else code
        for m in rule.pattern.finditer(haystack):
            line = haystack.count('\n', 0, m.start()) + 1
            # Report on the line where the offending token starts.
            line += haystack[m.start():m.end()].count('\n') if rule.id == 'QOS-001' else 0
            if not suppressed(raw_lines, line, rule.id):
                findings.append(Finding(path, line, rule))
    return findings


def iter_files(paths: Iterable[pathlib.Path]):
    for root in paths:
        if root.is_file():
            yield root
            continue
        for p in sorted(root.rglob('*')):
            if p.is_file() and not SKIP_DIRS.intersection(p.parts):
                yield p


def run(paths: List[pathlib.Path]) -> int:
    findings: List[Finding] = []
    count = 0
    for path in iter_files(paths):
        info = FileInfo(path)
        if not (info.is_cpp or info.is_py or info.is_cmake or info.is_package_xml
                or path.suffix in {'.yaml', '.yml', '.xml'}):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        count += 1
        findings.extend(check_text(path, text))
    for f in findings:
        print(f)
    if findings:
        print(f'lint_rules: {len(findings)} finding(s) in {count} files. Fix them, or suppress '
              'with "guideline-ignore: <ID> <reason>" if the rule genuinely does not apply.')
        return 1
    print(f'lint_rules: OK ({count} files, {len(RULES)} rules)')
    return 0


RULE_ID_RE = re.compile(
    r'\b(ARCH|CPP|CMAKE|PY|QOS|RT|PERF|IF|LAUNCH|TEST|TOOL|MAINT|DEVENV|PLAN|CONTRACT)-\d{3}\b')


def check_rule_references(root: pathlib.Path) -> int:
    """Every rule ID cited anywhere must be defined (bold) in docs/agent or AGENTS.md §2."""
    docs = root / 'docs' / 'agent'
    if not docs.is_dir():
        return 0
    defined = set()
    for doc in list(docs.glob('*.md')) + [root / 'AGENTS.md']:
        if doc.is_file():
            text = doc.read_text(encoding='utf-8')
            defined.update(m.group(0) for m in re.finditer(
                RULE_ID_RE.pattern.replace(r'\b(', r'(?<=\*\*)('), text))
            defined.update(m.group(0) for m in re.finditer(
                r'(?<=^\| )' + RULE_ID_RE.pattern[2:], text, re.M))
            defined.update(m.group(1) for m in re.finditer(
                r'^#+ (' + RULE_ID_RE.pattern[2:] + ')', text, re.M))
    failures = 0
    scan = [root / 'AGENTS.md', root / 'CLAUDE.md', root / 'PROJECT.md', root / 'Makefile',
            root / '.claude', docs, root / 'templates', root / 'tools', root / 'scripts']
    for path in iter_files(p for p in scan if p.exists()):
        if path.suffix not in {'.md', '.cpp', '.hpp', '.py', '.txt', '.yaml', '.sh', '.json'} \
                and path.name not in {'Makefile', 'Dockerfile'} and not path.name.startswith('Dockerfile'):
            continue
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for m in RULE_ID_RE.finditer(line):
                if m.group(0) not in defined:
                    print(f'{path.relative_to(root)}:{n}: rule {m.group(0)} is cited but never defined')
                    failures += 1
    return failures


def self_test() -> int:
    failures = 0
    ids = [r.id for r in RULES]
    if len(ids) != len(set(ids)):
        print('duplicate rule IDs')
        failures += 1
    docs = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'agent'
    for rule in RULES:
        p = pathlib.Path(rule.sample_name)
        if not check_text(p, rule.bad, [rule]):
            print(f'{rule.id}: bad sample did not fire')
            failures += 1
        if check_text(p, rule.good, [rule]):
            print(f'{rule.id}: good sample fired')
            failures += 1
        suppressed_bad = ''.join(
            line.rstrip('\n') + f'  // guideline-ignore: {rule.id} test\n'
            if rule.sample_name.endswith(('.cpp', '.hpp')) else
            line.rstrip('\n') + f'  # guideline-ignore: {rule.id} test\n'
            for line in rule.bad.splitlines(keepends=True))
        if not rule.sample_name.endswith('package.xml') and check_text(p, suppressed_bad, [rule]):
            print(f'{rule.id}: suppression comment not honoured')
            failures += 1
        doc = docs / rule.doc
        if docs.is_dir() and (not doc.is_file() or rule.id not in doc.read_text(encoding='utf-8')):
            print(f'{rule.id}: not documented in docs/agent/{rule.doc}')
            failures += 1
    failures += check_rule_references(docs.parent.parent)
    # Comments and strings must not trigger code rules.
    if check_text(pathlib.Path('src/n.cpp'), '// new Filter(); std::cout\nauto s = "delete x;";\n'):
        print('comment/string stripping failed for C++')
        failures += 1
    if check_text(pathlib.Path('pkg/n.py'), '# time.sleep(1)\nx = "print(1)"\n'):
        print('comment/string stripping failed for Python')
        failures += 1
    print('self-test: ' + ('OK' if not failures else f'{failures} failure(s)'))
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', type=pathlib.Path)
    parser.add_argument('--list', action='store_true', help='print rules as a markdown table')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    if args.list:
        print('| ID | Rule | Doc |\n|---|---|---|')
        for r in RULES:
            print(f'| {r.id} | {r.message} | {r.doc} |')
        return 0
    if args.self_test:
        return self_test()
    paths = args.paths or [pathlib.Path('src')]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f'no such path: {", ".join(map(str, missing))}', file=sys.stderr)
        return 2
    return run(paths)


if __name__ == '__main__':
    sys.exit(main())
