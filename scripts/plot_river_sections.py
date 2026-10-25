"""Optional scientific export from the saved native1m terrain investigation profiles."""
import os
from pathlib import Path
import json
os.environ['MPLCONFIGDIR']=str(Path(__file__).resolve().parents[1]/'work/cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
for name in ['PROJECT_SPEC.md','STATUS.md']:(root/name).read_text()
rows=json.loads((root/'data/processed/stage03/la_river_adjacent_1m_sections.json').read_text())
if len(rows)<3:raise ValueError('At least3 actual sections required')
selected=[rows[0],rows[len(rows)//2],rows[-1]];fig,axs=plt.subplots(3,1,figsize=(12,9),facecolor='white')
for ax,row in zip(axs,selected):
    ax.plot(row['offsets_east_west_m'],row['ground_NAVD88_m'],color='#735637',lw=1.4)
    half=row['hydrographic_polygon_width_along_transect_m']/2;ax.axvspan(-half,half,color='#8bbacc',alpha=.24)
    ax.set_aspect('equal',adjustable='box');ax.set_xlabel('East-west offset / m');ax.set_ylabel('NAVD88 ground / m');ax.grid(alpha=.2)
    ax.set_title('Actual river transect / local grid north {:.0f} m / lon,lat {:.6f}, {:.6f}'.format(row['center_local_xy_m'][1],*row['center_lon_lat']),loc='left',fontsize=10)
fig.suptitle('LOS ANGELES RIVER / native1m bare-earth DEM ground sections',fontsize=14)
fig.text(.06,.02,'True1:1 axis scale. Blue band: Census hydrographic extent, NOT current flow width. Ground source2023–2024; bank material/bridge decks unknown.',fontsize=9)
fig.tight_layout(rect=(0,.045,1,.96));out=root/'work/previews/stage03/river_terrain_sections.png';fig.savefig(out,dpi=160);print(out)
