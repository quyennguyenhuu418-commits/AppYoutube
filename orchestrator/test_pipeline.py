"""Run the full pipeline on a single short test topic.

This script:
1. Creates a job (like the API would)
2. Runs all 11 stages synchronously
3. Reports success/failure at each stage
4. Outputs final MP4 path if rendered
"""
import sys
sys.path.insert(0, ".")

# Force UTF-8 stdout
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("END-TO-END PIPELINE TEST")
print("Topic: The mystery of the Voynich manuscript")
print("=" * 60)

from app.db import store
from app.schemas.job import JobCreateRequest, JobDetail
from app.pipeline.runner import run_job

# 1. Create job
req = JobCreateRequest(
    topic="ancient humans winter cold adaptation ice age survival",
    title_hint="How Ancient Humans Survived the Ice Age",
)
detail = store.create_job(req)
print(f"\n[OK] Job created: {detail.id}")
print(f"     Topic: {detail.topic}")
print(f"     Status: {detail.status}")

# 2. Run pipeline
print("\n[RUNNING PIPELINE - 11 stages]...\n")

try:
    run_job(detail)
    print("\n[OK] Pipeline completed!")

    # 3. Show final state
    from app.core.paths import job_dir
    jd = job_dir(detail.id)
    print(f"\n[OUTPUTS in {jd}]")

    import os
    for f in sorted(os.listdir(jd))[:30]:
        fpath = jd / f
        if fpath.is_file():
            sz = fpath.stat().st_size
            print(f"  - {f} ({sz} bytes)")
        elif fpath.is_dir():
            print(f"  - {f}/")

except Exception as e:
    print(f"\n[FAIL] Pipeline error: {e}")
    import traceback
    traceback.print_exc()
