"""Make a contact sheet from images using Pillow when installed."""
import argparse
from pathlib import Path
from mac_tinker.common import add_output_args, emit

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); add_output_args(p); p.add_argument("folder"); p.add_argument("--output",default="contact_sheet.jpg"); p.add_argument("--columns",type=int,default=4); p.add_argument("--thumb",type=int,default=180); a=p.parse_args(argv)
    try: from PIL import Image,ImageDraw
    except ImportError: emit({"error":"Install Pillow to use this tool: python3 -m pip install Pillow"},a.json); return
    files=[x for x in Path(a.folder).iterdir() if x.suffix.lower() in {".jpg",".jpeg",".png",".gif",".webp"}]; rows=(len(files)+a.columns-1)//a.columns; sheet=Image.new("RGB",(a.columns*a.thumb,rows*a.thumb),(245,245,245)); draw=ImageDraw.Draw(sheet)
    for i,f in enumerate(files):
        try:
            im=Image.open(f).convert("RGB"); im.thumbnail((a.thumb-12,a.thumb-30)); x=(i%a.columns)*a.thumb+(a.thumb-im.width)//2; y=(i//a.columns)*a.thumb+5; sheet.paste(im,(x,y)); draw.text(((i%a.columns)*a.thumb+6,(i//a.columns+1)*a.thumb-22),f.name[:24],fill=(0,0,0))
        except Exception: pass
    sheet.save(a.output,quality=90); emit({"output":a.output,"images":len(files),"size":sheet.size},a.json)
if __name__=="__main__": main()
