"""Reclaim only an unaccepted generated draft; keep formal checkpoints and deltas."""
from pathlib import Path
import json,shutil,datetime
from stage05_preserve import sha
from stage02_io import write_json
ROOT=Path(__file__).resolve().parents[1]
def compact(root=ROOT):
 root=Path(root);report=root/'work/reports/stage05/unaccepted_draft_compaction.json'
 if report.exists():return
 b=json.load(open(root/'work/reports/stage05/blender_check.json'));s=json.load(open(root/'work/reports/stage05/building_sample_audit.json'));assert b['status']==s['status']=='passed' and s['sample_count']>=20
 visual=json.load(open(root/'work/reports/stage05/visual_inspection.json'))
 for r in visual['images'].values():assert sha(root/r['path'])==r['sha256']
 old=root/'work/history/stage05_before_nonbuilding_filter/stage05_city_medium.blend';current=root/'scenes/stage05_city_medium.blend';assert old.is_file() and current.is_file() and old!=current;before=shutil.disk_usage(root).free;size=old.stat().st_size;digest=sha(old);deltas=[]
 for folder in ['stage05_before_nonbuilding_filter','stage05_before_roof_winding','stage05_before_height_type_review','stage05_before_sidewalk_repair']:
  for p in sorted((root/'work/history'/folder).rglob('*')):
   if p.is_file() and p!=old:deltas.append({'path':str(p.relative_to(root)),'sha256':sha(p),'bytes':p.stat().st_size})
 assert any(r['path'].endswith('.npz') for r in deltas);write_json(old.parent/'draft_geometry_preservation.json',{'unaccepted_full_binary_sha256':digest,'unaccepted_full_binary_bytes':size,'preserved_geometry_deltas_and_generation_evidence':deltas,'full_binary_recoverable_byte_for_byte':False,'geometry_reconstruction_inputs_preserved':True,'note':'Only the first unaccepted stage05 draft, containing explicit nonbuilding areas and failed roof normals, is removed. Formal stage01–05 files remain. Delta records preserve original feature geometry and correction evidence; no binary-identical restoration is claimed.'});old.unlink();write_json(report,{'status':'executed','removed_unaccepted_generated_draft':str(old.relative_to(root)),'old_bytes':size,'old_sha256':digest,'preservation_record':str((old.parent/'draft_geometry_preservation.json').relative_to(root)),'formal_stage01_to05_models_or_raw_sources_removed':False,'disk_free_before_bytes':before,'disk_free_after_bytes':shutil.disk_usage(root).free,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});print('UNACCEPTED_DRAFT_REPLACED_BY_GEOMETRY_DELTA_ARCHIVE',size,flush=True)
if __name__=='__main__':compact()
