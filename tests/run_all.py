"""Run every Spell Check test and the syntax check. From the repo root:  python3 tests/run_all.py
Exit code 0 means everything passed."""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get('SPELLCHECK_APP', os.path.join(HERE, '..', 'index.html'))
ok = True

# 1. Syntax check on every inline script in index.html (this file has broken from small edits before)
html = open(APP, encoding='utf-8').read()
scripts = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', html, re.S)
for i, js in enumerate(scripts):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(js)
    r = subprocess.run(['node', '--check', f.name], capture_output=True, text=True)
    print(('PASS' if r.returncode == 0 else 'FAIL') + f' syntax check, script {i}')
    if r.returncode != 0:
        print(r.stderr[:400]); ok = False

# 2. Browser tests against mocked Firebase, location lookups, and photo files
for name in ['t_main.py', 't_saved.py', 't_photo.py', 't_social.py', 't_zoom.py', 't_big3.py', 't_receipts.py', 'errs.py']:
    r = subprocess.run([sys.executable, '-B', os.path.join(HERE, name)], capture_output=True, text=True)
    out = r.stdout.strip().splitlines()
    fails = [l for l in out if l.startswith('FAIL')]
    summary = out[-1] if out else r.stderr[-300:]
    print(f'{name}: {summary}')
    for l in fails: print('   ' + l)
    if r.returncode != 0 or fails or (name == 'errs.py' and 'unexpected errors: []' not in r.stdout):
        ok = False
        if r.returncode != 0: print(r.stderr[-600:])
# 3. The push Worker, end to end with a fake Firebase and a fake push service
r = subprocess.run(['node', os.path.join(HERE, 'worker_test.mjs')], capture_output=True, text=True)
out = [l for l in r.stdout.splitlines() if l.startswith('PASS') or l.startswith('FAIL') or 'checks,' in l]
print('worker_test.mjs: ' + (out[-1] if out else r.stderr[-300:]))
for l in out:
    if l.startswith('FAIL'): print('   ' + l)
if r.returncode != 0:
    ok = False

print('\nALL PASSED' if ok else '\nSOMETHING FAILED')
sys.exit(0 if ok else 1)
