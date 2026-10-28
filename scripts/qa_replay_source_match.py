"""Verify rendered replay video frames come from the selected source clip."""
import argparse, json, subprocess
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

def shot(ffmpeg, path, seconds):
    raw=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-ss',str(seconds),'-i',str(path),'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,check=True).stdout
    return Image.open(BytesIO(raw)).convert('RGB')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--project-root',type=Path)
    ap.add_argument('--ffmpeg',type=Path,required=True)
    ap.add_argument('--report',type=Path)
    a=ap.parse_args()
    cfg=json.loads(a.config.read_text(encoding='utf-8'))
    ep=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    root=a.project_root or a.manifest.resolve().parent.parent
    source=Path(ep['sourceVideoPath'])
    clip=ep['selectedClip'];start=clip['sourceStartSeconds'];end=clip['sourceEndSeconds']
    x0,y0,x1,y1=cfg['cardLayout']['topVideoRectPx'];w=x1-x0;h=y1-y0
    left,top,right,bottom=cfg['qa']['replaySourceCropInsetsPx'];region=(left,top,w-right,h-bottom)
    assert region[0]<region[2] and region[1]<region[3]
    checks=[]
    for point in ep['knowledgePoints']:
        relstart=point['replayRelativeStartSeconds'];relend=point['replayRelativeEndSeconds']
        assert 0<=relstart<relend<=end-start+.001,point['id']
        for mode,speed,key in (('normal',1.0,'renderedNormalFile'),('slow',cfg['cutting']['slowReplaySpeed'],'renderedSlowFile')):
            sample=min(cfg['qa']['replaySourceSampleSeconds'],(relend-relstart)/speed*.55)
            source_time=start+relstart+sample*speed
            rendered=shot(a.ffmpeg,root/point[key],sample).crop((x0,y0,x1,y1)).crop(region)
            original=shot(a.ffmpeg,source,source_time).resize((w,h),Image.Resampling.BICUBIC).crop(region)
            diff=ImageStat.Stat(ImageChops.difference(rendered,original)).mean
            mae=sum(diff)/3
            checks.append({'point':point['id'],'mode':mode,'expectedSourceSeconds':round(source_time,3),'pixelMae':round(mae,1),'pass':mae<=cfg['qa']['replaySourceMatchMaxPixelMae']})
    result={'configVersion':cfg['configVersion'],'checks':checks,'allPass':all(c['pass'] for c in checks)}
    if a.report:a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['allPass']:raise SystemExit(1)

if __name__=='__main__':main()
