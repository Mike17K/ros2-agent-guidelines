#!/usr/bin/env python3
"""Node contracts: validate, check the static graph, and verify a running node.

    tools/contracts.py validate [PATH ...] [--no-types]   # schema (+ interface types via ament index)
    tools/contracts.py graph [--system FILE] [PATH ...]   # static wiring / QoS check
    tools/contracts.py live CONTRACT /ns/node [--timeout S]

Spec: docs/agent/contracts.md (CONTRACT-001..004). The live check is also a library
function, `check_live()`, which the templates' launch tests call (CONTRACT-003).
"""

import argparse
import dataclasses
import pathlib
import re
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Must match templates/ros_template_cpp/include/ros_template_cpp/qos.hpp (QOS-002).
PROFILES: Dict[str, Dict[str, object]] = {
    'sensor_publisher': {'reliability': 'reliable', 'durability': 'volatile', 'depth': 5},
    'sensor_subscription': {'reliability': 'best_effort', 'durability': 'volatile', 'depth': 5},
    'command': {'reliability': 'reliable', 'durability': 'volatile', 'depth': 1},
    'state': {'reliability': 'reliable', 'durability': 'volatile', 'depth': 10},
    'latched': {'reliability': 'reliable', 'durability': 'transient_local', 'depth': 1},
}
TOP_KEYS = {'node', 'package', 'executable', 'plugin', 'lifecycle', 'parameters_schema',
            'parameters', 'publishes', 'subscribes', 'services', 'clients', 'action_servers',
            'action_clients', 'description'}
TOPIC_KEYS = {'topic', 'type', 'qos', 'rate_hz', 'max_latency_ms', 'when', 'required',
              'description'}
NAMED_KEYS = {'name', 'type', 'required', 'description'}
PARAM_TYPES = {'bool', 'int', 'double', 'string', 'bool_array', 'int_array', 'double_array',
               'string_array', 'string_fixed_25'}
NAME_RE = re.compile(r'^(~/|/)?[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*$')
NODE_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
TYPE_RE = re.compile(r'^([a-z][a-z0-9_]*)/(msg|srv|action)/([A-Z][A-Za-z0-9]*)$')
SECTIONS = {  # section -> (kind of interface, is topic)
    'publishes': ('msg', True), 'subscribes': ('msg', True),
    'services': ('srv', False), 'clients': ('srv', False),
    'action_servers': ('action', False), 'action_clients': ('action', False),
}


# --- Loading ---------------------------------------------------------------------

@dataclasses.dataclass
class Contract:
    path: pathlib.Path
    data: dict

    @property
    def id(self) -> str:
        return f'{self.data.get("package", "?")}/{self.data.get("node", "?")}'

    def section(self, name: str) -> List[dict]:
        return self.data.get(name) or []


def load(path: pathlib.Path) -> Contract:
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f'{path}: top level must be a mapping')
    return Contract(path, data)


def find_contracts(paths: Iterable[pathlib.Path]) -> List[pathlib.Path]:
    found = []
    for root in paths:
        if root.is_file():
            found.append(root)
            continue
        for p in sorted(root.rglob('*.yaml')):
            if {'build', 'install', 'log'} & set(p.parts):
                continue
            if p.name == 'contract.yaml' or (p.parent.name == 'contracts'
                                             and not p.name.endswith('.contract.yaml')):
                found.append(p)
    return found


def qos_of(spec) -> Dict[str, object]:
    if isinstance(spec, str):
        return dict(PROFILES[spec])
    return dict(spec)


def schema_parameters(schema_file: pathlib.Path) -> Dict[str, dict]:
    """Flatten a generate_parameter_library YAML into {dotted_name: spec}."""
    with open(schema_file, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    out: Dict[str, dict] = {}

    def walk(prefix: str, node: dict):
        for key, value in node.items():
            if not isinstance(value, dict):
                continue
            name = f'{prefix}.{key}' if prefix else key
            if 'type' in value:
                out[name] = value
            else:
                walk(name, value)

    for top in data.values():  # the top-level key is the C++ namespace
        if isinstance(top, dict):
            walk('', top)
    return out


def schema_path(c: Contract) -> Optional[pathlib.Path]:
    """Locate parameters_schema: next to the source contract, or installed next to it."""
    schema = c.data.get('parameters_schema')
    if not schema:
        return None
    for base in (c.path.parent, c.path.resolve().parent):
        for candidate in (base / schema, base / pathlib.Path(schema).name):
            if candidate.is_file():
                return candidate
    return None


def declared_parameters(c: Contract) -> Dict[str, dict]:
    params = {p['name']: p for p in c.section('parameters') if isinstance(p, dict) and 'name' in p}
    schema = schema_path(c)
    if schema:
        params.update(schema_parameters(schema))
    elif c.data.get('parameters_schema'):
        raise FileNotFoundError(f'{c.path}: parameters_schema {c.data["parameters_schema"]} not '
                                'found (install it next to contract.yaml)')
    return params


NODE_CMAKE_RE = re.compile(r'rclcpp_components_register_nodes?\s*\(|add_executable\s*\(')
CONSOLE_SCRIPT_RE = re.compile(r'''['"][\w-]+\s*=\s*[\w.]+:\w+['"]''')


def missing_contracts(paths: Iterable[pathlib.Path]) -> List[str]:
    """Packages that build node executables but ship no contract (CONTRACT-001)."""
    errs = []
    for root in paths:
        for pkg_xml in ([root / 'package.xml'] if (root / 'package.xml').is_file()
                        else sorted(root.rglob('package.xml'))):
            pkg = pkg_xml.parent
            cmake, setup = pkg / 'CMakeLists.txt', pkg / 'setup.py'
            builds_nodes = (cmake.is_file() and NODE_CMAKE_RE.search(cmake.read_text()))\
                or (setup.is_file() and CONSOLE_SCRIPT_RE.search(setup.read_text()))
            has = (pkg / 'contract.yaml').is_file() or any((pkg / 'contracts').glob('*.yaml'))
            if builds_nodes and not has:
                errs.append(f'{pkg}: builds nodes but has no contract.yaml (CONTRACT-001)')
    return errs


# --- validate ----------------------------------------------------------------------

def interface_exists(type_str: str) -> Optional[bool]:
    """True/False via the ament index, None if the index is not available."""
    try:
        from ament_index_python.resources import get_resource
    except ImportError:
        return None
    pkg, kind, name = TYPE_RE.match(type_str).groups()
    try:
        content, _ = get_resource('rosidl_interfaces', pkg)
    except LookupError:
        return False
    entries = set(content.split())
    return any(f'{kind}/{name}.{ext}' in entries for ext in ('idl', kind))


def validate(c: Contract, check_types: bool = True) -> List[str]:
    errs = []
    d = c.data

    def err(msg):
        errs.append(f'{c.path}: {msg}')

    for key in sorted(set(d) - TOP_KEYS):
        err(f'unknown key "{key}"')
    for key in ('node', 'package', 'executable'):
        if not isinstance(d.get(key), str) or not d.get(key):
            err(f'"{key}" is required')
    if isinstance(d.get('node'), str) and not NODE_RE.match(d['node']):
        err(f'invalid node name "{d["node"]}"')
    if 'lifecycle' in d and not isinstance(d['lifecycle'], bool):
        err('"lifecycle" must be true or false')

    schema = d.get('parameters_schema')
    if schema and schema_path(c) is None:
        err(f'parameters_schema "{schema}" not found')
    for p in c.section('parameters'):
        if not isinstance(p, dict) or 'name' not in p or p.get('type') not in PARAM_TYPES:
            err(f'parameter entry {p!r} needs "name" and a "type" in {sorted(PARAM_TYPES)}')
        elif 'range' in p and not (isinstance(p['range'], list) and len(p['range']) == 2
                                   and p['range'][0] <= p['range'][1]):
            err(f'parameter {p["name"]}: range must be [min, max]')

    for section, (kind, is_topic) in SECTIONS.items():
        seen = set()
        entries = d.get(section) or []
        if not isinstance(entries, list):
            err(f'"{section}" must be a list')
            continue
        for e in entries:
            if not isinstance(e, dict):
                err(f'{section}: entry {e!r} must be a mapping')
                continue
            name_key = 'topic' if is_topic else 'name'
            name = e.get(name_key)
            allowed = TOPIC_KEYS if is_topic else NAMED_KEYS
            for key in sorted(set(e) - allowed):
                err(f'{section} {name}: unknown key "{key}"')
            if not isinstance(name, str) or not NAME_RE.match(name):
                err(f'{section}: invalid or missing {name_key} {name!r}')
                continue
            if name in seen:
                err(f'{section}: duplicate {name}')
            seen.add(name)
            t = e.get('type')
            m = TYPE_RE.match(t) if isinstance(t, str) else None
            if not m or m.group(2) != kind:
                err(f'{section} {name}: type must look like pkg/{kind}/Name, got {t!r}')
            elif check_types and interface_exists(t) is False:
                err(f'{section} {name}: interface {t} not found (typo, or package not built/'
                    'declared in package.xml?)')
            if is_topic:
                q = e.get('qos')
                if isinstance(q, str):
                    if q not in PROFILES:
                        err(f'{section} {name}: unknown QoS profile "{q}" (known: '
                            f'{", ".join(PROFILES)})')
                elif isinstance(q, dict):
                    if q.get('reliability') not in ('reliable', 'best_effort') or \
                            q.get('durability', 'volatile') not in ('volatile', 'transient_local'):
                        err(f'{section} {name}: qos needs reliability reliable|best_effort and '
                            'durability volatile|transient_local')
                else:
                    err(f'{section} {name}: "qos" is required (QOS-001)')
                r = e.get('rate_hz')
                if r is not None and not (isinstance(r, dict) and
                                          r.get('min', 0) <= r.get('max', float('inf'))):
                    err(f'{section} {name}: rate_hz must be {{min, max}}')
                if e.get('when', 'active') not in ('active', 'always'):
                    err(f'{section} {name}: when must be active|always')
    return errs


# --- Name resolution -----------------------------------------------------------------

def resolve(name: str, namespace: str, node: str, remap: Optional[Dict[str, str]] = None) -> str:
    name = (remap or {}).get(name, name)
    if name.startswith('/'):
        return name
    ns = '/' + namespace.strip('/') if namespace.strip('/') else ''
    if name.startswith('~/'):
        return f'{ns}/{node}/{name[2:]}'
    return f'{ns}/{name}'


# --- graph ---------------------------------------------------------------------------

@dataclasses.dataclass
class Endpoint:
    owner: str
    section: str
    name: str
    type: str
    qos: Optional[Dict[str, object]]
    required: bool
    qos_label: str = ''


def qos_compatible(pub: Dict[str, object], sub: Dict[str, object]) -> Optional[str]:
    if pub.get('reliability') == 'best_effort' and sub.get('reliability') == 'reliable':
        return 'best_effort publisher cannot serve a reliable subscriber'
    if pub.get('durability', 'volatile') == 'volatile' and \
            sub.get('durability') == 'transient_local':
        return 'volatile publisher cannot serve a transient_local subscriber'
    return None


def collect(instances: List[Tuple[Contract, str, Dict[str, str]]]) -> List[Endpoint]:
    eps = []
    for c, ns, remap in instances:
        node = c.data['node']
        owner = f'{c.id}@{ns or "/"}'
        for section, (_kind, is_topic) in SECTIONS.items():
            for e in c.section(section):
                raw = e['topic'] if is_topic else e['name']
                q = e.get('qos')
                eps.append(Endpoint(owner, section, resolve(raw, ns, node, remap), e['type'],
                                    qos_of(q) if is_topic and q else None,
                                    e.get('required', True),
                                    q if isinstance(q, str) else ''))
    return eps


def external_endpoints(system: dict) -> List[Endpoint]:
    ext = system.get('external') or {}
    eps = []
    for e in ext.get('publishes') or []:
        eps.append(Endpoint('external', 'publishes', e['topic'], e['type'],
                            qos_of(e.get('qos', 'sensor_publisher')), True))
    for section in ('services', 'action_servers'):
        for e in ext.get(section) or []:
            eps.append(Endpoint('external', section, e['name'], e['type'], None, True))
    return eps


def graph_check(eps: List[Endpoint], strict_wiring: bool) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    by_name: Dict[str, List[Endpoint]] = {}
    for e in eps:
        by_name.setdefault(e.name, []).append(e)

    for name, group in sorted(by_name.items()):
        types = sorted({e.type for e in group})
        if len(types) > 1:
            detail = ', '.join(f'{e.owner}:{e.section}={e.type}' for e in group)
            errors.append(f'{name}: conflicting types ({detail})')
        pubs = [e for e in group if e.section == 'publishes']
        subs = [e for e in group if e.section == 'subscribes']
        for p in pubs:
            for s in subs:
                why = qos_compatible(p.qos or {}, s.qos or {})
                if why:
                    errors.append(f'{name}: {p.owner} -> {s.owner}: incompatible QoS: {why} '
                                  '(QOS-003)')
        cmd_pubs = [p for p in pubs if p.qos_label == 'command']
        if len(cmd_pubs) > 1:
            warnings.append(f'{name}: {len(cmd_pubs)} command publishers '
                            f'({", ".join(p.owner for p in cmd_pubs)}): use a mux')
        pairs = (('subscribes', 'publishes', 'publisher'), ('clients', 'services', 'server'),
                 ('action_clients', 'action_servers', 'action server'))
        for consumer, provider, what in pairs:
            for e in group:
                if e.section == consumer and e.required and \
                        not any(p.section == provider for p in group):
                    msg = f'{name}: {e.owner} needs a {what}, none declared'
                    (errors if strict_wiring else warnings).append(msg)
    return errors, warnings


def load_instances(system_file: pathlib.Path, by_id: Dict[str, Contract]):
    with open(system_file, encoding='utf-8') as f:
        system = yaml.safe_load(f) or {}
    instances, errors = [], []
    for inst in system.get('instances') or []:
        c = by_id.get(inst.get('contract', ''))
        if c is None:
            errors.append(f'{system_file}: unknown contract id {inst.get("contract")!r} '
                          f'(known: {", ".join(sorted(by_id))})')
            continue
        instances.append((c, inst.get('namespace', ''), inst.get('remap') or {}))
    return system, instances, errors


# --- live ----------------------------------------------------------------------------

def _qos_names(endpoint_qos) -> Dict[str, str]:
    from rclpy.qos import DurabilityPolicy, ReliabilityPolicy
    rel = {ReliabilityPolicy.RELIABLE: 'reliable', ReliabilityPolicy.BEST_EFFORT: 'best_effort'}
    dur = {DurabilityPolicy.VOLATILE: 'volatile',
           DurabilityPolicy.TRANSIENT_LOCAL: 'transient_local'}
    return {'reliability': rel.get(endpoint_qos.reliability, str(endpoint_qos.reliability)),
            'durability': dur.get(endpoint_qos.durability, str(endpoint_qos.durability))}


def _call(node, srv_type, name, request, timeout_s):
    import rclpy
    client = node.create_client(srv_type, name)
    try:
        if not client.wait_for_service(timeout_sec=timeout_s):
            return None
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=timeout_s)
        return future.result() if future.done() else None
    finally:
        node.destroy_client(client)


def _live_once(c: Contract, node, ns: str, name: str, remap: Dict[str, str]) -> List[str]:
    from rclpy.action import (get_action_client_names_and_types_by_node,
                              get_action_server_names_and_types_by_node)
    fails = []
    where = f'{ns.rstrip("/")}/{name}'
    for section, getter in (('publishes', node.get_publishers_info_by_topic),
                            ('subscribes', node.get_subscriptions_info_by_topic)):
        for e in c.section(section):
            topic = resolve(e['topic'], ns, name, remap)
            mine = [i for i in getter(topic)
                    if i.node_name == name and i.node_namespace.rstrip('/') == ns.rstrip('/')]
            if not mine:
                fails.append(f'{where}: missing {section[:-1]} {topic} [{e["type"]}]')
                continue
            if all(i.topic_type != e['type'] for i in mine):
                fails.append(f'{where}: {topic} has type {mine[0].topic_type}, contract says '
                             f'{e["type"]}')
            want = qos_of(e['qos'])
            got = _qos_names(mine[0].qos_profile)
            for k in ('reliability', 'durability'):
                if k in want and got[k] != want[k]:
                    fails.append(f'{where}: {topic} QoS {k} is {got[k]}, contract says {want[k]}')
    listings = {
        'services': node.get_service_names_and_types_by_node(name, ns),
        'clients': node.get_client_names_and_types_by_node(name, ns),
        'action_servers': get_action_server_names_and_types_by_node(node, name, ns),
        'action_clients': get_action_client_names_and_types_by_node(node, name, ns),
    }
    for section, found in listings.items():
        found_map = {n: types for n, types in found}
        for e in c.section(section):
            target = resolve(e['name'], ns, name, remap)
            if target not in found_map:
                fails.append(f'{where}: missing {section[:-1]} {target} [{e["type"]}]')
            elif e['type'] not in found_map[target]:
                fails.append(f'{where}: {target} has type {found_map[target]}, contract says '
                             f'{e["type"]}')
    return fails


def check_live(contract_path, node_fqn: str, node=None, timeout_s: float = 15.0,
               remap: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Verify that the running node `node_fqn` matches its contract.

    Returns a list of human-readable failures (empty = match). Pass an existing rclpy
    node to reuse it (e.g. inside a launch test); otherwise one is created. `remap`
    must mirror the remappings the launch file applies ({contract name: actual name}).
    """
    remap = remap or {}
    import rclpy
    from lifecycle_msgs.srv import GetState
    from rcl_interfaces.srv import ListParameters

    c = load(pathlib.Path(contract_path))
    ns, _, name = node_fqn.rpartition('/')
    ns = ns or '/'
    own = node is None
    if own:
        if not rclpy.ok():
            rclpy.init()
        node = rclpy.create_node('contract_checker')
    try:
        deadline = time.monotonic() + timeout_s
        while (name, ns) not in node.get_node_names_and_namespaces():
            if time.monotonic() > deadline:
                return [f'{node_fqn}: node not found within {timeout_s:.0f} s']
            rclpy.spin_once(node, timeout_sec=0.1)
        if c.data.get('lifecycle'):
            res = _call(node, GetState, f'{node_fqn}/get_state', GetState.Request(),
                        max(1.0, deadline - time.monotonic()))
            if res is None:
                return [f'{node_fqn}: lifecycle node but {node_fqn}/get_state did not answer']
            if res.current_state.label != 'active':
                return [f'{node_fqn}: lifecycle state is "{res.current_state.label}", '
                        'expected "active"']
        # Endpoints appear asynchronously: retry until they match or time runs out.
        fails = _live_once(c, node, ns, name, remap)
        while fails and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
            fails = _live_once(c, node, ns, name, remap)
        req = ListParameters.Request()
        res = _call(node, ListParameters, f'{node_fqn}/list_parameters', req,
                    max(1.0, deadline - time.monotonic()))
        if res is None:
            fails.append(f'{node_fqn}: list_parameters did not answer')
        else:
            have = set(res.result.names)
            for p in sorted(declared_parameters(c)):
                if p not in have:
                    fails.append(f'{node_fqn}: parameter {p} declared in contract is missing')
        return fails
    finally:
        if own:
            node.destroy_node()


# --- CLI -----------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('validate')
    v.add_argument('paths', nargs='*', type=pathlib.Path)
    v.add_argument('--no-types', action='store_true', help='skip the ament index type check')
    v.add_argument('--require-for-nodes', action='store_true',
                   help='fail when a package that builds nodes has no contract (CONTRACT-001)')
    g = sub.add_parser('graph')
    g.add_argument('paths', nargs='*', type=pathlib.Path)
    g.add_argument('--system', type=pathlib.Path, action='append',
                   help='system.contract.yaml (default: every one found under the paths)')
    lv = sub.add_parser('live')
    lv.add_argument('contract', type=pathlib.Path)
    lv.add_argument('node', help='fully qualified node name, e.g. /robot_1/filter_node')
    lv.add_argument('--timeout', type=float, default=15.0)
    lv.add_argument('--remap', action='append', default=[], metavar='FROM:=TO',
                    help='remapping applied by the launch file (repeatable)')
    args = parser.parse_args(argv)

    if args.cmd == 'live':
        remap = dict(r.split(':=', 1) for r in args.remap)
        fails = check_live(args.contract, args.node, timeout_s=args.timeout, remap=remap)
        for f in fails:
            print(f'FAIL {f}')
        print('live: ' + ('OK' if not fails else f'{len(fails)} mismatch(es)'))
        return 1 if fails else 0

    paths = args.paths or [ROOT / 'src']
    files = find_contracts(paths)
    contracts, errors = [], []
    for f in files:
        try:
            contracts.append(load(f))
        except (yaml.YAMLError, ValueError) as e:
            errors.append(f'{f}: {e}')

    if args.cmd == 'validate':
        for c in contracts:
            errors.extend(validate(c, check_types=not args.no_types))
        if args.require_for_nodes:
            errors.extend(missing_contracts(paths))
        for e in errors:
            print(f'ERROR {e}')
        print(f'contracts validate: {len(contracts)} contract(s), '
              + ('OK' if not errors else f'{len(errors)} error(s)'))
        return 1 if errors else 0

    # graph
    for c in contracts:
        errors.extend(validate(c, check_types=False))
    if errors:
        for e in errors:
            print(f'ERROR {e}')
        print('contracts graph: fix validation errors first')
        return 1
    by_id = {c.id: c for c in contracts}
    systems = args.system or [p for root in paths if root.is_dir()
                              for p in sorted(root.rglob('system.contract.yaml'))
                              if not {'build', 'install'} & set(p.parts)]
    all_errors, all_warnings = [], []
    if systems:
        for sf in systems:
            system, instances, errs = load_instances(sf, by_id)
            all_errors.extend(errs)
            e, w = graph_check(collect(instances) + external_endpoints(system), True)
            all_errors.extend(f'[{sf.name}] {x}' for x in e)
            all_warnings.extend(f'[{sf.name}] {x}' for x in w)
    else:
        e, w = graph_check(collect([(c, '', {}) for c in contracts]), False)
        all_errors.extend(e)
        all_warnings.extend(w)
    for w in all_warnings:
        print(f'WARN  {w}')
    for e in all_errors:
        print(f'ERROR {e}')
    print(f'contracts graph: {len(contracts)} contract(s), {len(systems)} system file(s), '
          + ('OK' if not all_errors else f'{len(all_errors)} error(s)')
          + (f', {len(all_warnings)} warning(s)' if all_warnings else ''))
    return 1 if all_errors else 0


if __name__ == '__main__':
    sys.exit(main())
