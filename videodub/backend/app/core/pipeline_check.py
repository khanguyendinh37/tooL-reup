"""Explicit opt-in real-video check, using a fresh isolated job database."""
import asyncio
import json
import os
from pathlib import Path


async def run(url, report_path):
    if not os.environ.get('VIDEODUB_DATA_DIR') or not os.environ.get('DATABASE_URL'):
        raise RuntimeError('Set isolated VIDEODUB_DATA_DIR and DATABASE_URL before this test')
    from app.models.database import init_db, async_session, DubbingJob
    from app.core.pipeline import run_pipeline
    from app.core.paths import DATA_DIR
    await init_db()
    async with async_session() as session:
        job = DubbingJob(id='parity-check', url=url, source_lang='zh', target_lang='vi',
                         voice='vi-VN-NamMinhNeural', whisper_model='small', status='pending')
        session.add(job)
        await session.commit()
        report = {'data_dir': str(DATA_DIR), 'voice': job.voice}
        try:
            await run_pipeline(job.id, url, 'zh', 'vi', job.voice, 'small', 1.0,
                               session, subtitle_config={'enabled': True})
            await session.refresh(job)
            report.update(status=job.status, result_path=job.result_path)
        except Exception as exc:
            report.update(status='error', error=str(exc))
            raise
        finally:
            Path(report_path).write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    import sys
    asyncio.run(run(sys.argv[1], sys.argv[2]))
