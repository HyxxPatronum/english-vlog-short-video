"""Convert BorderStyle=3 subtitle panels into one vector rectangle per cue."""
import argparse
import json
import math
import re
from pathlib import Path
from PIL import ImageFont, ImageDraw, Image


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',required=True,type=Path)
    ap.add_argument('--input',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    sub=cfg['subtitle']; bg=sub['background']; boxes=sub['boxes']; text_cfg=sub['text']
    in_text=args.input.read_text(encoding='utf-8-sig')
    lines=in_text.splitlines()
    font_dir=Path(r'C:\Windows\Fonts')
    temp=Image.new('RGB',(8,8)); measure=ImageDraw.Draw(temp)
    output=[]; styles={}; box_events=[]; box_style_added=False
    for line in lines:
        if line.startswith('Style: '):
            parts=[v.strip() for v in line[len('Style: '):].split(',')]
            name=parts[0]
            if name in ('CN','EN'):
                styles[name]=parts
                parts[5]='&HFF000000'; parts[6]='&HFF000000'
                parts[15]='1'; parts[16]='0'; parts[17]='0'
                line='Style: '+','.join(parts)
            output.append(line)
            if name=='EN' and not box_style_added:
                color=f"&H{round((1-bg['opacity'])*255):02X}{bg['colorHex'][5:7]}{bg['colorHex'][3:5]}{bg['colorHex'][1:3]}".upper()
                box=['Box',text_cfg['chineseFont'],str(text_cfg['chineseFontSizePx']),color,color,'&HFF000000','&HFF000000','0','0','0','0','100','100','0','0','1','0','0','7','0','0','0','1']
                output.append('Style: '+','.join(box));box_style_added=True
            continue
        if line.startswith('Dialogue: '):
            f=line[len('Dialogue: '):].split(',',9)
            if len(f)==10 and f[3] in ('CN','EN'):
                layer,start,end,style,name=f[:5]
                event_text=f[9]
                pos=re.search(r'\\pos\((\d+),(\d+)\)',event_text)
                if not pos: raise ValueError(f'Missing positioned cue: {event_text}')
                cx,anchor_y=map(int,pos.groups())
                size_match=re.search(r'\\fs(\d+)',event_text)
                size=int(size_match.group(1)) if size_match else int(styles[style][2])
                font_name=text_cfg['chineseFont'] if style=='CN' else text_cfg['englishFont']
                bold=int(styles[style][7]) != 0
                file={'Microsoft YaHei':('msyhbd.ttc' if bold else 'msyh.ttc'),'Arial':('arialbd.ttf' if bold else 'arial.ttf')}[font_name]
                font=ImageFont.truetype(str(font_dir/file),size)
                clean=re.sub(r'\{.*?\}','',event_text)
                clean=clean.replace(r'\N','\n').replace(r'\n','\n').replace(r'\h',' ')
                rows=clean.split('\n')
                widths=[];heights=[]
                for row in rows:
                    b=measure.textbbox((0,0),row,font=font)
                    widths.append(measure.textlength(row,font=font));heights.append(b[3]-b[1])
                pad_x=boxes['chinesePaddingPx'] if style=='CN' else boxes['englishPaddingPx']
                pad_y=pad_x
                line_step=round(size*1.2)
                text_h=max(heights)+(len(rows)-1)*line_step
                width=math.ceil(max(widths)+2*pad_x)
                height=math.ceil(text_h+2*pad_y)
                x=round(cx-width/2);y=anchor_y-text_h-pad_y
                drawing=f'{{\\an7\\pos({x},{y})\\p1}}m 0 0 l {width} 0 l {width} {height} l 0 {height}{{\\p0}}'
                box_events.append(f'Dialogue: 0,{start},{end},Box,{style},0,0,0,,{drawing}')
            output.append(line)
            continue
        output.append(line)
    if not box_style_added or not styles.keys() >= {'CN','EN'}:
        raise ValueError('ASS must define CN and EN styles and an Events section')
    # Put all single-piece boxes immediately before the cue events; layer 0 keeps them behind text.
    ix=next(i for i,v in enumerate(output) if v.startswith('[Events]'))+1
    fmt_ix=next(i for i in range(ix,len(output)) if output[i].startswith('Format:'))+1
    output[fmt_ix:fmt_ix]=box_events
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(output)+'\n',encoding='utf-8-sig')
    print(f'{args.output}: one vector background per cue ({len(box_events)} boxes)')

if __name__=='__main__': main()
