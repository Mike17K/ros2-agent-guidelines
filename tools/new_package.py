#!/usr/bin/env python3
"""Scaffold a new ROS 2 package from a golden template.

Usage:
    tools/new_package.py cpp        my_driver
    tools/new_package.py py         mission_manager
    tools/new_package.py interfaces my_robot_interfaces
    tools/new_package.py cpp my_driver --dest src/drivers --maintainer "Jane Doe" \
        --email jane@example.com --copyright "My Lab"

Defaults for maintainer/email/copyright come from $ROS_MAINTAINER_NAME,
$ROS_MAINTAINER_EMAIL, $ROS_COPYRIGHT_HOLDER, then project.env, then `git config user.*`.

The copy is renamed everywhere (paths, contents, include guards, namespaces).
Agents must use this instead of hand-copying templates [ARCH-001].
"""

import argparse
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = {
    'cpp': 'ros_template_cpp',
    'py': 'ros_template_py',
    'interfaces': 'ros_template_interfaces',
}
NAME_RE = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$')
TEXT_SUFFIXES = {
    '.cpp', '.hpp', '.h', '.c', '.py', '.txt', '.xml', '.yaml', '.yml', '.md',
    '.cfg', '.msg', '.srv', '.action', '.toml', '.json', '',
}


def project_env(key, workspace=ROOT):
    """Read KEY from <workspace>/project.env (plain KEY=VALUE lines)."""
    env_file = pathlib.Path(workspace) / 'project.env'
    if not env_file.is_file():
        return ''
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.startswith(key + '='):
            return line.split('=', 1)[1].strip()
    return ''


def git_config(key):
    try:
        return subprocess.run(
            ['git', 'config', '--get', key], capture_output=True, text=True, check=False
        ).stdout.strip()
    except FileNotFoundError:
        return ''


def fail(msg):
    print(f'error: {msg}', file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('kind', choices=sorted(TEMPLATES))
    parser.add_argument('name', help='package name: lower_snake_case, ASCII, no leading digit')
    parser.add_argument('--dest', default='src', help='directory relative to the workspace root')
    parser.add_argument('--workspace', default=str(ROOT), help='workspace root (default: this one)')
    parser.add_argument('--maintainer', default=os.environ.get('ROS_MAINTAINER_NAME')
                        or project_env('ROS_MAINTAINER_NAME') or git_config('user.name'))
    parser.add_argument('--email', default=os.environ.get('ROS_MAINTAINER_EMAIL')
                        or project_env('ROS_MAINTAINER_EMAIL') or git_config('user.email'))
    parser.add_argument('--copyright', default=os.environ.get('ROS_COPYRIGHT_HOLDER')
                        or project_env('ROS_COPYRIGHT_HOLDER') or None,
                        help='copyright holder (default: maintainer)')
    args = parser.parse_args()

    name = args.name
    if not NAME_RE.match(name):
        fail(f'"{name}" is not a valid ROS package name (lower_snake_case, [a-z0-9_]) [ARCH-003]')
    if args.kind == 'interfaces' and not name.endswith(('_interfaces', '_msgs')):
        fail('interface packages must end in "_interfaces" or "_msgs" [IF-001]')
    if name.startswith('ros_') or name.startswith('rcl'):
        fail('package names must not start with "ros_" or "rcl" (reserved by upstream) [ARCH-003]')
    if not args.maintainer or not args.email or '@' not in args.email:
        fail('maintainer name and a valid email are required: pass --maintainer/--email or set '
             'ROS_MAINTAINER_NAME/ROS_MAINTAINER_EMAIL or git config user.name/user.email')
    holder = args.copyright or args.maintainer

    template = TEMPLATES[args.kind]
    src = ROOT / 'templates' / template
    if not src.is_dir():
        fail(f'template not found: {src}')
    workspace = pathlib.Path(args.workspace).resolve()
    dest = workspace / args.dest / name
    if dest.exists():
        fail(f'{dest} already exists')

    # Refuse duplicates anywhere in the workspace source tree.
    for pkg_xml in (workspace / 'src').rglob('package.xml'):
        if f'<name>{name}</name>' in pkg_xml.read_text(encoding='utf-8'):
            fail(f'a package named {name} already exists at {pkg_xml.parent}')

    replacements = [
        (template, name),
        (template.upper(), name.upper()),
        ('MAINTAINER_NAME', args.maintainer),
        ('MAINTAINER_EMAIL', args.email),
        ('Copyright 2026 COPYRIGHT_HOLDER',
         f'Copyright {datetime.date.today().year} {holder}'),
        ('COPYRIGHT_HOLDER', holder),
    ]

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    # Rename paths deepest-first so parents are renamed after children.
    for path in sorted(dest.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if template in path.name:
            path.rename(path.with_name(path.name.replace(template, name)))

    for path in dest.rglob('*'):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding='utf-8')
        new = text
        for old, value in replacements:
            new = new.replace(old, value)
        if new != text:
            path.write_text(new, encoding='utf-8')

    rel = dest.relative_to(workspace)
    print(f'Created {rel} from templates/{template}')
    print('Next steps:')
    print('  1. Rename example classes/files/topics to your domain '
          '(grep -rn "filter\\|Filter\\|monitor\\|Example" ' + str(rel) + ').')
    print('  2. Update package.xml <description> and README.md interface table.')
    print(f'  3. tools/check.sh --packages {name}')


if __name__ == '__main__':
    main()
