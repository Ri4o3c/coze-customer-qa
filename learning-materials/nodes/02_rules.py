import json
import re


async def main(args: Args) -> Output:
    hits = args.params.get('hits', [])
    errors = []
    if isinstance(hits, str):
        try:
            hits = json.loads(hits)
        except ValueError:
            hits = [{'content': hits}]
    if not isinstance(hits, list):
        errors.append('retrieval_output_must_be_list')
        hits = []
    rules = {}
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get('content'), str):
            errors.append('retrieval_hit_missing_content')
            continue
        for block in re.split(r'(?=^RULE_ID:)', hit['content'], flags=re.MULTILINE):
            rid = re.search(r'^RULE_ID:\s*(R0[123])\s*$', block, re.MULTILINE)
            ver = re.search(r'^RULE_VERSION:\s*(\S+)\s*$', block, re.MULTILINE)
            policy = re.search(r'^POLICY:[ \t]*(.+)$', block, re.MULTILINE)
            if not rid or not ver or not policy:
                continue
            r = {'rule_id': rid.group(1), 'version': ver.group(1), 'policy': policy.group(1).strip()}
            if r['version'] != '1.0':
                errors.append('unsupported_rule_version_' + r['rule_id'])
            previous = rules.get(r['rule_id'])
            if previous and previous != r:
                errors.append('conflicting_rule_' + r['rule_id'])
            rules[r['rule_id']] = r
    missing = sorted({'R01', 'R02', 'R03'} - set(rules))
    errors.extend('missing_rule_' + rid for rid in missing)
    # Conflicting or unrecognised retrieval formats cannot flow into a passing decision.
    if any(e.startswith(('conflicting_', 'unsupported_', 'retrieval_')) for e in errors):
        rules = {}
    return {'rules_json': json.dumps(list(rules.values()), ensure_ascii=False),
            'rules_ok': not errors, 'errors': list(dict.fromkeys(errors))}
