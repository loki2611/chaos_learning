from flask import Blueprint, jsonify, request, Response, current_app
import subprocess
import threading
import json
import time
import os
import uuid
import queue
import requests as http_requests
 
api_bp = Blueprint('api', __name__)
 
# ── In-memory job store ────────────────────────────────────────────────────────
# Each running experiment gets a job_id.
# jobs[job_id] = { status, log_queue, result, started_at, type }
jobs   = {}
# Completed results stored for the Results page
results_store = []
 
 
# =============================================================================
# /api/status — health check of TradeSphere + pod listing
# =============================================================================
@api_bp.route('/status', methods=['GET'])
def status():
    """
    Returns:
      - TradeSphere health (calls /health/ready on the target app)
      - List of pods in the namespace (via kubectl)
    """
    target = current_app.config['TARGET_APP_URL']
    ns     = current_app.config['APP_NAMESPACE']
 
    # ── Check TradeSphere health ──────────────────────────────────────────────
    app_health = {'status': 'unknown', 'code': 0}
    try:
        r = http_requests.get(f"{target}/health/ready", timeout=5)
        app_health = {'status': 'ready' if r.status_code == 200 else 'unhealthy',
                      'code': r.status_code, 'body': r.json()}
    except Exception as e:
        app_health = {'status': 'unreachable', 'error': str(e), 'code': 0}
 
    # ── Get pod list via kubectl ──────────────────────────────────────────────
    pods = []
    try:
        out = subprocess.check_output(
            ['kubectl', 'get', 'pods', '-n', ns,
             '-o', 'jsonpath={range .items[*]}{.metadata.name}|'
                   '{.status.phase}|'
                   '{.spec.nodeName}|'
                   '{.status.containerStatuses[0].ready}\\n{end}'],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode().strip()
 
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split('|')
            if len(parts) >= 3:
                pods.append({
                    'name':  parts[0],
                    'phase': parts[1],
                    'node':  parts[2] if len(parts) > 2 else 'unknown',
                    'ready': parts[3].lower() == 'true' if len(parts) > 3 else False,
                })
    except Exception as e:
        pods = [{'name': 'kubectl-error', 'phase': 'Unknown',
                 'node': str(e), 'ready': False}]
 
    return jsonify(
        app_health=app_health,
        pods=pods,
        target_url=target,
        namespace=ns,
        timestamp=time.time()
    )
 
 
# =============================================================================
# Shared: run a chaos experiment as a background job
# =============================================================================
def _run_chaos_job(job_id, experiment_file, env_vars):
    """
    Runs a ChaosToolkit experiment in a background thread.
    Streams every log line to the job's log_queue so SSE can forward it.
    Saves the result to results_store when done.
    """
    job = jobs[job_id]
    q   = job['log_queue']
 
    def emit(msg, level='INFO'):
        """Push a log line to the queue with timestamp."""
        entry = {'ts': time.strftime('%H:%M:%S'), 'level': level, 'msg': msg}
        q.put(entry)
 
    emit(f"Starting experiment: {experiment_file}")
    emit(f"Target: {env_vars.get('APP_URL', '?')}")
    emit(f"Namespace: {env_vars.get('APP_NAMESPACE', '?')}")
 
    journal_file = f"/tmp/journal-{job_id}.json"
 
    # Build the environment for the subprocess
    env = os.environ.copy()
    env.update(env_vars)
 
    cmd = [
        'chaos', 'run',
        experiment_file,
        '--journal-path', journal_file,
    ]
 
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            env=env,
            text=True,
            bufsize=1                   # line-buffered
        )
        job['pid'] = proc.pid
        emit(f"Process started (PID {proc.pid})")
 
        # Stream lines as they come in
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            level = 'ERROR'   if 'ERROR'    in line.upper() else \
                    'WARNING' if 'WARNING'  in line.upper() else \
                    'SUCCESS' if 'succeeded' in line.lower() or 'met!' in line.lower() else \
                    'INFO'
            emit(line, level)
 
        proc.wait()
        exit_code = proc.returncode
 
    except FileNotFoundError:
        emit("ERROR: 'chaos' command not found. Install with: pip install chaostoolkit", 'ERROR')
        exit_code = 1
    except Exception as e:
        emit(f"ERROR: {e}", 'ERROR')
        exit_code = 1
 
    # ── Parse journal for score ───────────────────────────────────────────────
    score  = 0
    status = 'failed'
    findings = []
 
    try:
        with open(journal_file) as f:
            journal = json.load(f)
 
        exp_status = journal.get('status', 'unknown')
        status = 'completed' if exp_status == 'completed' else 'deviated'
 
        # Score based on which probes passed
        runs   = journal.get('run', [])
        passed = sum(1 for r in runs if r.get('status') == 'succeeded')
        total  = len(runs) if runs else 1
        score  = round((passed / total) * 100)
 
        # Bonus if both steady-state checks passed
        ss = journal.get('steady_states', {})
        before_met = ss.get('before', {}).get('steady_state_met', False)
        after_met  = ss.get('after',  {}).get('steady_state_met', False)
        if before_met:  score = min(score + 10, 100)
        if after_met:   score = min(score + 15, 100)
 
        # Build findings list
        if before_met:
            findings.append({'ok': True,  'text': 'Pre-experiment steady-state passed'})
        else:
            findings.append({'ok': False, 'text': 'Pre-experiment steady-state FAILED'})
 
        if after_met:
            findings.append({'ok': True,  'text': 'Post-experiment steady-state passed — app recovered'})
        else:
            findings.append({'ok': False, 'text': 'Post-experiment steady-state FAILED — weakness found'})
 
        for r in runs:
            findings.append({
                'ok':   r.get('status') == 'succeeded',
                'text': f"{r.get('activity', {}).get('name', 'step')}: {r.get('status', '?')}"
            })
 
    except Exception as e:
        emit(f"Could not parse journal: {e}", 'WARNING')
        status = 'completed' if exit_code == 0 else 'deviated'
        score  = 60 if exit_code == 0 else 30
 
    # ── Save result ───────────────────────────────────────────────────────────
    result = {
        'job_id':    job_id,
        'type':      job['type'],
        'status':    status,
        'score':     score,
        'exit_code': exit_code,
        'findings':  findings,
        'duration':  round(time.time() - job['started_at']),
        'finished_at': time.strftime('%H:%M:%S'),
    }
    results_store.append(result)
    job['result'] = result
    job['status'] = 'done'
 
    emit(f"Experiment finished — status: {status.upper()} | score: {score}/100", 'SUCCESS')
    # Sentinel tells the SSE stream to close
    q.put(None)
 
 
# =============================================================================
# /api/experiment/pod-kill
# =============================================================================
@api_bp.route('/experiment/pod-kill', methods=['POST'])
def run_pod_kill():
    """Kick off the pod-kill chaos experiment as a background job."""
    target = current_app.config['TARGET_APP_URL']
    ns     = current_app.config['APP_NAMESPACE']
 
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'type':       'Pod Kill',
        'status':     'running',
        'log_queue':  queue.Queue(),
        'result':     None,
        'started_at': time.time(),
    }
 
    env_vars = {
        'APP_URL':       target,
        'APP_NAMESPACE': ns,
    }
 
    t = threading.Thread(
        target=_run_chaos_job,
        args=(job_id, 'chaos_experiments/pod_kill.json', env_vars),
        daemon=True
    )
    t.start()
 
    return jsonify(job_id=job_id, message='Pod kill experiment started')
 
 
# =============================================================================
# /api/experiment/stress
# =============================================================================
@api_bp.route('/experiment/stress', methods=['POST'])
def run_stress():
    """Kick off the scale-down stress experiment as a background job."""
    target = current_app.config['TARGET_APP_URL']
    ns     = current_app.config['APP_NAMESPACE']
 
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'type':       'Scale Stress',
        'status':     'running',
        'log_queue':  queue.Queue(),
        'result':     None,
        'started_at': time.time(),
    }
 
    env_vars = {
        'APP_URL':       target,
        'APP_NAMESPACE': ns,
    }
 
    t = threading.Thread(
        target=_run_chaos_job,
        args=(job_id, 'chaos_experiments/scale_down.json', env_vars),
        daemon=True
    )
    t.start()
 
    return jsonify(job_id=job_id, message='Stress experiment started')
 
 
# =============================================================================
# /api/loadtest/run
# =============================================================================
@api_bp.route('/loadtest/run', methods=['POST'])
def run_loadtest():
    """
    Run a JMeter load test as a background job.
    Accepts JSON body: { users: 20, duration: 60 }
    """
    data     = request.get_json() or {}
    users    = int(data.get('users',    20))
    duration = int(data.get('duration', 60))
    target   = current_app.config['TARGET_APP_URL']
 
    # Parse host and port from target URL
    # e.g. http://tradesphere-svc → host=tradesphere-svc, port=80
    host = target.replace('http://', '').replace('https://', '').split(':')[0].split('/')[0]
    port = '80'
    if ':' in target.replace('http://', '').replace('https://', ''):
        port = target.split(':')[-1].split('/')[0]
 
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'type':       f'Load Test ({users}u {duration}s)',
        'status':     'running',
        'log_queue':  queue.Queue(),
        'result':     None,
        'started_at': time.time(),
    }
 
    def _run_jmeter(job_id):
        job = jobs[job_id]
        q   = job['log_queue']
 
        def emit(msg, level='INFO'):
            q.put({'ts': time.strftime('%H:%M:%S'), 'level': level, 'msg': msg})
 
        emit(f"JMeter load test: {users} users × {duration}s → {host}:{port}")
 
        results_dir = f"/tmp/jmeter-results-{job_id}"
        jtl_file    = f"{results_dir}/results.jtl"
        os.makedirs(results_dir, exist_ok=True)
 
        # Find JMeter binary
        jmeter_bin = '/opt/jmeter/bin/jmeter'
        if not os.path.exists(jmeter_bin):
            jmeter_bin = 'jmeter'  # fallback: hope it's on PATH
 
        cmd = [
            jmeter_bin, '-n',
            '-t', 'chaos_experiments/load_test.jmx',
            '-l', jtl_file,
            f'-Jhost={host}',
            f'-Jport={port}',
            f'-Jusers={users}',
            f'-Jduration={duration}',
            f'-Jramp=10',
        ]
 
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    emit(line)
            proc.wait()
            exit_code = proc.returncode
        except FileNotFoundError:
            emit("ERROR: JMeter not found. Check /opt/jmeter/bin/jmeter exists.", 'ERROR')
            exit_code = 1
        except Exception as e:
            emit(f"ERROR: {e}", 'ERROR')
            exit_code = 1
 
        # Parse JTL CSV
        peak_rps = 0; avg_lat = 0; err_pct = 0.0; total = 0
        try:
            import csv
            rows = []
            with open(jtl_file) as f:
                rows = list(csv.DictReader(f))
            total    = len(rows)
            errors   = sum(1 for r in rows if r.get('success','true').lower() == 'false')
            lats     = [int(r['elapsed']) for r in rows if 'elapsed' in r]
            avg_lat  = round(sum(lats)/len(lats)) if lats else 0
            err_pct  = round((errors/total)*100, 2) if total else 0
            tss      = [int(r['timeStamp']) for r in rows if 'timeStamp' in r]
            if len(tss) >= 2:
                dur = (max(tss)-min(tss))/1000.0
                peak_rps = round(total/dur) if dur > 0 else 0
        except Exception as e:
            emit(f"Could not parse JTL: {e}", 'WARNING')
 
        lt_status = 'passed' if err_pct < 1 and avg_lat < 500 else 'failed'
        score = min(
            (40 if err_pct < 1 else 15) +
            (30 if avg_lat < 300 else 15 if avg_lat < 500 else 5) +
            (20 if peak_rps > 50 else 10) + 10,
            97
        )
 
        result = {
            'job_id':    job_id,
            'type':      job['type'],
            'status':    lt_status,
            'score':     score,
            'duration':  round(time.time() - job['started_at']),
            'finished_at': time.strftime('%H:%M:%S'),
            'metrics': {
                'peak_rps':   peak_rps,
                'avg_latency': avg_lat,
                'error_rate':  err_pct,
                'total_reqs':  total,
            },
            'findings': [
                {'ok': err_pct < 1,     'text': f"Error rate: {err_pct:.2f}% (SLO: <1%)"},
                {'ok': avg_lat < 300,   'text': f"Avg latency: {avg_lat}ms (SLO: <300ms)"},
                {'ok': peak_rps >= 50,  'text': f"Peak throughput: {peak_rps} req/s (SLO: >50)"},
                {'ok': total > 0,       'text': f"Total requests completed: {total}"},
            ],
        }
        results_store.append(result)
        job['result'] = result
        job['status'] = 'done'
        emit(f"Load test done — {peak_rps} req/s | {avg_lat}ms avg | {err_pct:.2f}% errors | score: {score}/100", 'SUCCESS')
        q.put(None)
 
    t = threading.Thread(target=_run_jmeter, args=(job_id,), daemon=True)
    t.start()
 
    return jsonify(job_id=job_id, message='Load test started')
 
 
# =============================================================================
# /api/stream/<job_id> — Server-Sent Events live log stream
# =============================================================================
@api_bp.route('/stream/<job_id>', methods=['GET'])
def stream(job_id):
    """
    SSE endpoint. The browser connects here and receives log lines
    as they are produced by the running experiment.
 
    Each event looks like:
      data: {"ts":"15:23:30","level":"INFO","msg":"Probe passed"}
    """
    if job_id not in jobs:
        return jsonify(error='Job not found'), 404
 
    def generate():
        q = jobs[job_id]['log_queue']
        while True:
            try:
                # Block for up to 30 seconds waiting for next log line
                entry = q.get(timeout=30)
                if entry is None:
                    # Sentinel — experiment finished
                    yield f"data: {json.dumps({'ts':'--:--:--','level':'DONE','msg':'__DONE__'})}\n\n"
                    break
                yield f"data: {json.dumps(entry)}\n\n"
            except queue.Empty:
                # Heartbeat to keep connection alive
                yield f"data: {json.dumps({'ts':time.strftime('%H:%M:%S'),'level':'PING','msg':'…'})}\n\n"
 
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':   'no-cache',
            'X-Accel-Buffering': 'no',   # disable nginx buffering
        }
    )
 
 
# =============================================================================
# /api/job/<job_id> — get job status and result
# =============================================================================
@api_bp.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    if job_id not in jobs:
        return jsonify(error='Job not found'), 404
    job = jobs[job_id]
    return jsonify(
        status=job['status'],
        result=job.get('result'),
        type=job.get('type'),
    )
 
 
# =============================================================================
# /api/results — all completed experiment results
# =============================================================================
@api_bp.route('/results', methods=['GET'])
def get_results():
    return jsonify(results=list(reversed(results_store)))